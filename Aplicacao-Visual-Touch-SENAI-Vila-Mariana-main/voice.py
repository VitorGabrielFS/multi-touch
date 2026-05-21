from __future__ import annotations

# ── stdlib ────────────────────────────────────────────────────────────────────
import json
import logging
import os
import re
import subprocess
import threading
import time
import webbrowser
import ctypes
import ctypes.wintypes
from dataclasses import dataclass
from queue import Queue, Empty
from typing import Optional, Callable

# ── third-party ───────────────────────────────────────────────────────────────
import psutil
import requests
import speech_recognition as sr
import tkinter as tk
from tkinter import scrolledtext

# ── API KEY ───────────────────────────────────────────────────────────────────
API_KEY        = ""
WAKE_WORD      = "Bruna"
ASSISTANT_NAME = "bruna"
USER_NAME      = "gabriel"
WAKE_WORDS: list[str] = [WAKE_WORD, ASSISTANT_NAME]

# ── logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("assistente.log", encoding="utf-8"),
    ],
)
log = logging.getLogger("assistente")


# ── config ────────────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class Config:
    api_key:              str   = API_KEY
    wake_word:            str   = WAKE_WORD
    user_name:            str   = USER_NAME
    model:                str   = "llama-3.1-8b-instant"
    endpoint:             str   = "https://api.groq.com/openai/v1/chat/completions"
    cache_file:           str   = "apps_cache.json"
    tts_rate:             int   = 180
    api_timeout:          int   = 15
    api_retries:          int   = 3
    listen_timeout:       int   = 30
    tts_voice:            str   = "pt-BR-FranciscaNeural"
    sr_energy_threshold:  int   = 300
    sr_pause_threshold:   float = 0.6
    exe_search_max_depth: int   = 4
    exe_cache_ttl:        int   = 3600
    tts_voice:            str   = ""   # não usado pelo pyttsx3, mantido por compatibilidade


CFG = Config()


# ── prompts ───────────────────────────────────────────────────────────────────
COMMAND_PROMPT = """Você é um controlador de computador. Sua ÚNICA função é converter o que o usuário diz em comandos estruturados.

REGRA ABSOLUTA: qualquer pedido que envolva abrir, fechar, pesquisar, clicar, escrever ou pressionar teclas → responda SOMENTE o(s) comando(s), um por linha, nada mais.

COMANDOS DISPONÍVEIS:
abrir: NOME
fechar: NOME
pesquisar: TEXTO
mouse: clique|duplo|direito|rolar_cima|rolar_baixo
escrever: TEXTO
tecla: ATALHO

MÚLTIPLOS COMANDOS: Se o usuário pedir mais de uma ação, retorne uma por linha.
EXEMPLO:
usuário: "abre o youtube e pesquisa lo-fi"
→
abrir: youtube
pesquisar: lo-fi site:youtube.com

EXEMPLOS OBRIGATÓRIOS:
usuário: "abre o youtube"              → abrir: youtube
usuário: "youtube"                     → abrir: youtube
usuário: "pesquisa renato no youtube"  → pesquisar: renato site:youtube.com
usuário: "fecha o chrome"              → fechar: chrome
usuário: "pesquisa python"             → pesquisar: python
usuário: "clica"                       → mouse: clique
usuário: "escreva olá mundo"           → escrever: olá mundo
usuário: "execute control c"           → tecla: ctrl+c
usuário: "aperta enter"                → tecla: enter
usuário: "pressiona alt tab"           → tecla: alt+tab
usuário: "control v"                   → tecla: ctrl+v
usuário: "apaga tudo"                  → tecla: ctrl+a,delete
usuário: "voltar ação"                 → tecla: ctrl+z

USO DE CONTEXTO: Se o usuário disser "pesquisa isso" ou "pesquisa lá" após ter aberto um site,
inferir o site no contexto. Ex: último app = youtube → pesquisar: X site:youtube.com

Se a entrada for completamente ambígua (ex: "abre ele") → responda: AMBIGUO: especifique o que deseja abrir
Se não for possível executar → NO_COMMAND
"""

CHAT_PROMPT = """Você é uma assistente virtual chamada Bruna.
Responda de forma natural, amigável e objetiva.
Seja concisa — respostas curtas são preferíveis.
Não invente capacidades que não possui.
Você pode conversar, responder perguntas e dar informações gerais."""

CLASSIFY_PROMPT = """Classifique a intenção do usuário em UMA palavra: "comando" ou "conversa".

- "comando": o usuário quer executar uma ação no computador (abrir app, pesquisar, clicar, digitar, fechar, etc.)
- "conversa": o usuário quer conversar, perguntar algo, obter informação, ou a frase é ambígua sem ação clara.

Responda SOMENTE com: comando
ou: conversa

Frase: """


# ── mapas ─────────────────────────────────────────────────────────────────────
CMD_MAP: dict[str, str] = {
    "chrome":                   "start chrome",
    "google chrome":            "start chrome",
    "edge":                     "start msedge",
    "microsoft edge":           "start msedge",
    "firefox":                  "start firefox",
    "explorer":                 "explorer",
    "explorador":               "explorer",
    "explorador de arquivos":   "explorer",
    "explorador_de_arquivos":   "explorer",
    "gerenciador de arquivos":  "explorer",
    "gerenciador_de_arquivos":  "explorer",
    "files":                    "explorer",
    "notepad":                  "notepad",
    "bloco de notas":           "notepad",
    "bloco_de_notas":           "notepad",
    "calc":                     "calc",
    "calculadora":              "calc",
    "taskmgr":                  "taskmgr",
    "tarefas":                  "taskmgr",
    "gerenciador de tarefas":   "taskmgr",
    "gerenciador_de_tarefas":   "taskmgr",
    "terminal":                 "start cmd",
    "cmd":                      "start cmd",
    "prompt":                   "start cmd",
    "prompt de comando":        "start cmd",
    "prompt_de_comando":        "start cmd",
    "powershell":               "start powershell",
    "spotify":                  "start spotify",
    "vlc":                      "start vlc",
    "paint":                    "mspaint",
    "word":                     "start winword",
    "excel":                    "start excel",
    "powerpoint":               "start powerpnt",
    "teams":                    "start teams",
    "discord":                  "start discord",
    "zoom":                     "start zoom",
    "obs":                      "start obs64",
    "configuracoes":            "start ms-settings:",
    "settings":                 "start ms-settings:",
}

SITE_MAP: dict[str, str] = {
    "youtube":   "https://www.youtube.com",
    "google":    "https://www.google.com",
    "gmail":     "https://mail.google.com",
    "whatsapp":  "https://web.whatsapp.com",
    "instagram": "https://www.instagram.com",
    "twitter":   "https://www.twitter.com",
    "x":         "https://www.x.com",
    "facebook":  "https://www.facebook.com",
    "github":    "https://www.github.com",
    "netflix":   "https://www.netflix.com",
    "twitch":    "https://www.twitch.tv",
    "reddit":    "https://www.reddit.com",
    "linkedin":  "https://www.linkedin.com",
    "chatgpt":   "https://chat.openai.com",
    "spotify":   "https://www.spotify.com",
}

HOTKEY_MAP: dict[str, str] = {
    "control": "ctrl", "controle": "ctrl", "alt": "alt", "shift": "shift",
    "windows": "win",  "win": "win",
    "enter": "enter",     "confirma": "enter",   "confirmar": "enter",
    "escape": "escape",   "esc": "escape",        "cancela": "escape",
    "tab": "tab",         "backspace": "backspace", "apagar": "backspace",
    "delete": "delete",   "deletar": "delete",    "espaço": "space",
    "home": "home",       "end": "end",           "fim": "end",
    "page up": "pageup",  "page down": "pagedown",
    "seta cima": "up",    "seta baixo": "down",
    "seta esquerda": "left", "seta direita": "right",
    "cima": "up",         "baixo": "down",
    "control c": "ctrl+c",  "controle c": "ctrl+c",  "copiar": "ctrl+c",
    "control v": "ctrl+v",  "controle v": "ctrl+v",  "colar": "ctrl+v",
    "control x": "ctrl+x",  "controle x": "ctrl+x",  "recortar": "ctrl+x",
    "control z": "ctrl+z",  "controle z": "ctrl+z",  "desfazer": "ctrl+z",
    "control y": "ctrl+y",  "controle y": "ctrl+y",  "refazer": "ctrl+y",
    "control a": "ctrl+a",  "controle a": "ctrl+a",  "selecionar tudo": "ctrl+a",
    "control s": "ctrl+s",  "controle s": "ctrl+s",  "salvar": "ctrl+s",
    "control w": "ctrl+w",  "controle w": "ctrl+w",
    "control t": "ctrl+t",  "controle t": "ctrl+t",  "nova aba": "ctrl+t",
    "control f": "ctrl+f",  "controle f": "ctrl+f",  "pesquisar na página": "ctrl+f",
    "control r": "ctrl+r",  "controle r": "ctrl+r",  "atualizar": "ctrl+r",
    "control p": "ctrl+p",  "controle p": "ctrl+p",  "imprimir": "ctrl+p",
    "alt tab": "alt+tab",   "alt f4": "alt+f4",      "fechar janela": "alt+f4",
    "windows d": "win+d",   "win d": "win+d",        "mostrar desktop": "win+d",
    "windows l": "win+l",   "bloquear": "win+l",
    "print screen": "printscreen", "captura de tela": "printscreen", "screenshot": "printscreen",
    **{f"f{i}": f"f{i}" for i in range(1, 13)},
}

BLACKLIST: list[str] = [
    "shutdown", "restart", "reboot", "format c", "del ", "erase ", "rd ",
    "rmdir ", "shutdown.exe", "format.com", "diskpart", "rm -rf",
    "mkfs", "cipher", "bcdedit", "sc config", "net user", "net localgroup",
]

COMMAND_KEYWORDS: list[str] = [
    "abre", "abrir", "abre o", "open", "fecha", "fechar", "close",
    "pesquisa", "pesquisar", "busca", "buscar", "procura",
    "clica", "clicar", "clique", "digita", "digitar", "escreve", "escrever",
    "pressiona", "aperta", "execute", "tecla", "vai para", "acessa", "acessar",
    "mostra", "mostrar", "rola", "scroll", "minimiza", "maximiza",
]

CONVERSATION_KEYWORDS: list[str] = [
    "o que é", "o que são", "como", "por que", "porque", "quando",
    "quem", "onde", "quanto", "qual é", "quais são",
    "me conta", "me explica", "me fala", "você sabe",
    "pode me ajudar", "que horas", "que dia",
    "obrigado", "obrigada", "valeu", "tchau", "oi", "olá",
    "bom dia", "boa tarde", "boa noite",
    "me diga", "preciso saber", "você acha",
]


# ── helpers ───────────────────────────────────────────────────────────────────
def _get_desktop() -> str:
    try:
        buf = ctypes.create_unicode_buffer(ctypes.wintypes.MAX_PATH)
        ctypes.windll.shell32.SHGetFolderPathW(None, 0x0000, None, 0, buf)
        return buf.value
    except Exception:
        return ""


SEARCH_DIRS: list[str] = [p for p in [
    os.environ.get("PROGRAMFILES", ""),
    os.environ.get("PROGRAMFILES(X86)", ""),
    os.path.join(os.environ.get("USERPROFILE", ""), "AppData", "Local", "Microsoft", "WindowsApps"),
    os.path.join(os.environ.get("USERPROFILE", ""), "AppData", "Roaming"),
    os.path.join(os.environ.get("USERPROFILE", ""), "AppData", "Local"),
    _get_desktop(),
] if p]


def _is_blacklisted(text: str) -> bool:
    t = (text or "").lower()
    return any(b in t for b in BLACKLIST)


def _normalize_hotkey(raw: str) -> str:
    raw = raw.lower().strip()
    if raw in HOTKEY_MAP:
        return HOTKEY_MAP[raw]
    if "+" in raw:
        return "+".join(HOTKEY_MAP.get(p.strip(), p.strip()) for p in raw.split("+"))
    parts = raw.split()
    translated = [HOTKEY_MAP.get(w, w) for w in parts]
    return "+".join(translated) if len(translated) > 1 else HOTKEY_MAP.get(raw, raw)


# ── classificador de intenção ─────────────────────────────────────────────────
def classify_intent(text: str, llm: Optional["LLMClient"] = None) -> str:
    text_lower = text.lower().strip()

    for kw in COMMAND_KEYWORDS:
        if text_lower.startswith(kw) or f" {kw} " in text_lower:
            return "comando"
    for kw in CONVERSATION_KEYWORDS:
        if kw in text_lower:
            return "conversa"
    if "?" in text:
        return "conversa"
    if len(text_lower.split()) == 1 and text_lower in {**SITE_MAP, **CMD_MAP}:
        return "comando"
    if "site:" in text_lower:
        return "comando"

    if llm is not None:
        try:
            return llm.classify(text)
        except Exception as e:
            log.warning("classify_intent: LLM falhou (%s), fallback 'comando'", e)

    return "comando"


def detect_ambiguity(text: str) -> Optional[str]:
    patterns = [
        (r"\b(abre|abrir|fecha|fechar)\s+(ele|ela|isso|aquilo|aquele|aquela)\b",
         "Especifique o que deseja {verbo}."),
        (r"\b(pesquisa|busca|procura)\s+(isso|aquilo)\b",
         "Especifique o que deseja pesquisar."),
        (r"\b(vai para|acessa)\s+(lá|aqui|ali)\b",
         "Especifique para onde deseja ir."),
    ]
    for pattern, msg in patterns:
        m = re.search(pattern, text.lower().strip())
        if m:
            return msg.format(verbo=m.group(1) if m.lastindex else "executar")
    return None


def try_local_command(text: str, context: dict) -> Optional[str]:
    low = text.lower().strip()

    if len(low.split()) == 1 and low in {**SITE_MAP, **CMD_MAP}:
        return f"abrir: {low}"

    m = re.match(r"^(?:abre|abrir|open)\s+(?:o\s+|a\s+)?(.+)$", low)
    if m:
        return f"abrir: {m.group(1).strip()}"

    m = re.match(r"^(?:fecha|fechar|close)\s+(?:o\s+|a\s+)?(.+)$", low)
    if m:
        return f"fechar: {m.group(1).strip()}"

    m = re.match(r"^(?:pesquisa|pesquisar|busca|buscar|procura|procurar)\s+(.+)$", low)
    if m:
        termo = m.group(1).strip()
        site_match = re.search(r"\s+n[oa]\s+(\w+)\s*$", termo)
        site_suffix = ""
        if site_match:
            site_name = site_match.group(1)
            termo = termo[:site_match.start()].strip()
            if site_name in SITE_MAP:
                site_suffix = f" site:{site_name}.com"
        elif context.get("last_app") in SITE_MAP:
            last_app = context["last_app"]
            domain = SITE_MAP[last_app].replace("https://www.", "").replace("https://", "")
            site_suffix = f" site:{domain}"
        return f"pesquisar: {termo}{site_suffix}"

    return None


# ── cache de executáveis ──────────────────────────────────────────────────────
class ExeCache:
    def __init__(self, path: str, max_depth: int = CFG.exe_search_max_depth,
                 cache_ttl: int = CFG.exe_cache_ttl) -> None:
        self._path      = path
        self._max_depth = max_depth
        self._cache_ttl = cache_ttl
        self._lock      = threading.Lock()
        self._disk_data = self._load()
        self._mem_cache: dict[str, tuple[str, float]] = {}

    def _load(self) -> dict:
        try:
            if os.path.exists(self._path):
                with open(self._path, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception:
            pass
        return {}

    def _save(self) -> None:
        try:
            with open(self._path, "w", encoding="utf-8") as f:
                json.dump(self._disk_data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            log.warning("ExeCache: erro ao salvar: %s", e)

    def get(self, name: str) -> Optional[str]:
        key = name.lower()
        now = time.monotonic()

        with self._lock:
            if key in self._mem_cache:
                p, ts = self._mem_cache[key]
                if now - ts < self._cache_ttl and os.path.exists(p):
                    return p
            if key in self._disk_data and os.path.exists(self._disk_data[key]):
                p = self._disk_data[key]
                self._mem_cache[key] = (p, now)
                return p

        path = self._find(name)
        if path:
            with self._lock:
                self._disk_data[key] = path
                self._mem_cache[key] = (path, now)
                self._save()
        return path

    def _find(self, name: str) -> Optional[str]:
        exe = name if name.lower().endswith(".exe") else name + ".exe"
        try:
            out = subprocess.check_output(
                ["where", exe], text=True, stderr=subprocess.DEVNULL, timeout=2
            )
            if out.strip():
                return out.strip().splitlines()[0]
        except Exception:
            pass

        for base in SEARCH_DIRS:
            if not os.path.isdir(base):
                continue
            base_depth = base.rstrip(os.sep).count(os.sep)
            for root, dirs, files in os.walk(base):
                if root.count(os.sep) - base_depth >= self._max_depth:
                    dirs[:] = []
                    continue
                for f in files:
                    if f.lower() == exe.lower():
                        return os.path.join(root, f)
        return None


# ══════════════════════════════════════════════════════════════════════════════
# TTS ENGINE — pyttsx3 puro, sem dependências externas
# ══════════════════════════════════════════════════════════════════════════════
class TTSEngine:
    """
    TTS simples com pyttsx3.
    - Voz robotica nativa do Windows (SAPI5), zero instalação extra
    - Fila de textos processada em thread dedicada
    - stop() limpa a fila e interrompe a fala atual
    """

    def __init__(self, cfg: Config) -> None:
        self._cfg        = cfg
        self._queue:     Queue[Optional[str]] = Queue()
        self._stop_event = threading.Event()
        self._lock       = threading.Lock()
        self._engine     = self._init_engine()

        self._worker_thread = threading.Thread(
            target=self._worker, name="tts-worker", daemon=True
        )
        self._worker_thread.start()
        log.info("TTS iniciado com pyttsx3")

    def _init_engine(self):
        try:
            import pyttsx3
            engine = pyttsx3.init()
            # Tenta selecionar voz em português; se não houver, usa a padrão
            voices = engine.getProperty("voices")
            for v in voices:
                if "portuguese" in v.name.lower() or "maria" in v.name.lower():
                    engine.setProperty("voice", v.id)
                    break
            engine.setProperty("rate", self._cfg.tts_rate)
            return engine
        except Exception as e:
            log.error("pyttsx3 não pôde ser iniciado: %s", e)
            return None

    # ── API pública ───────────────────────────────────────────────────────────
    def speak(self, text: str) -> None:
        """Enfileira texto. Retorna imediatamente."""
        if text:
            self._queue.put(text)

    def stop(self) -> None:
        """Interrompe fala atual e descarta fila."""
        self._stop_event.set()
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
                self._queue.task_done()
            except Empty:
                break
        self._stop_event.clear()

    def shutdown(self) -> None:
        self._queue.put(None)
        self._worker_thread.join(timeout=3)

    # ── worker ────────────────────────────────────────────────────────────────
    def _worker(self) -> None:
        while True:
            try:
                text = self._queue.get(timeout=1)
            except Empty:
                continue

            if text is None:
                self._queue.task_done()
                break

            if not self._stop_event.is_set():
                self._falar(text)

            self._queue.task_done()

    def _falar(self, text: str) -> None:
        if self._engine is None:
            log.warning("TTS: engine não disponível, ignorando: %s", text[:40])
            return
        with self._lock:
            try:
                self._engine.say(text)
                self._engine.runAndWait()
            except RuntimeError as e:
                log.warning("pyttsx3 RuntimeError, reiniciando engine: %s", e)
                self._engine = self._init_engine()
            except Exception as e:
                log.warning("pyttsx3 erro: %s", e)


# ── cliente LLM ───────────────────────────────────────────────────────────────
class LLMClient:
    def __init__(self, cfg: Config) -> None:
        self._cfg = cfg
        self._session = requests.Session()
        self._session.headers.update({
            "Authorization": f"Bearer {cfg.api_key}",
            "Content-Type": "application/json",
        })

    def _call(self, messages: list[dict], max_tokens: int = 120, temperature: float = 0) -> str:
        payload = {
            "model":       self._cfg.model,
            "messages":    messages,
            "temperature": temperature,
            "max_tokens":  max_tokens,
        }
        last_err: Exception = RuntimeError("sem tentativas")
        for attempt in range(1, self._cfg.api_retries + 1):
            try:
                r = self._session.post(
                    self._cfg.endpoint, json=payload, timeout=self._cfg.api_timeout
                )
                r.raise_for_status()
                return r.json()["choices"][0]["message"]["content"].strip()
            except Exception as e:
                last_err = e
                log.warning("API tentativa %d/%d: %s", attempt, self._cfg.api_retries, e)
                if attempt < self._cfg.api_retries:
                    time.sleep(2 ** attempt)
        raise last_err

    def interpret_command(self, history: list[dict]) -> str:
        return self._call(
            [{"role": "system", "content": COMMAND_PROMPT}] + history,
            max_tokens=200, temperature=0
        )

    def interpret_chat(self, history: list[dict]) -> str:
        return self._call(
            [{"role": "system", "content": CHAT_PROMPT}] + history,
            max_tokens=300, temperature=0.7
        )

    def classify(self, text: str) -> str:
        result = self._call(
            [{"role": "user", "content": CLASSIFY_PROMPT + text}],
            max_tokens=5, temperature=0
        ).lower()
        return "comando" if "comando" in result else "conversa"

    # alias mantido para compatibilidade
    def interpret(self, history: list[dict]) -> str:
        return self.interpret_command(history)


# ── executor de comandos ──────────────────────────────────────────────────────
class CommandExecutor:
    def __init__(self, cache: ExeCache) -> None:
        self._cache = cache

    def run(self, resposta: str) -> tuple[str, dict]:
        if _is_blacklisted(resposta):
            return "Comando rejeitado por segurança.", {}

        linhas = [l.strip() for l in resposta.strip().splitlines() if l.strip()]
        if len(linhas) == 1:
            return self._run_single(linhas[0])

        resultados, ctx_total = [], {}
        for linha in linhas:
            res, ctx = self._run_single(linha)
            resultados.append(res)
            ctx_total.update(ctx)
        return " | ".join(resultados), ctx_total

    def _run_single(self, resposta: str) -> tuple[str, dict]:
        if _is_blacklisted(resposta):
            return "Comando rejeitado por segurança.", {}

        low = resposta.strip().lower()
        ctx: dict = {}

        if low in ("no_command", ""):
            return resposta, ctx

        if low.startswith("ambiguo:"):
            return resposta.split(":", 1)[1].strip(), ctx

        m = re.match(r"^abrir:\s*(.+)$", low)
        if m:
            app = m.group(1).strip()
            return self._open_app(app), {"last_app": app, "last_action": "abrir"}

        m = re.match(r"^fechar:\s*(.+)$", low)
        if m:
            return self._close_app(m.group(1).strip()), {"last_app": None, "last_action": "fechar"}

        m = re.match(r"^pesquisar:\s*(.+)$", low)
        if m:
            termo = resposta.split(":", 1)[1].strip()
            if "site:youtube.com" in termo or "youtube" in termo.lower():
                q = re.sub(r"site:youtube\.com", "", termo).strip().replace(" ", "+")
                webbrowser.open(f"https://www.youtube.com/results?search_query={q}")
            else:
                webbrowser.open(f"https://www.google.com/search?q={termo.replace(' ', '+')}")
            return f"Pesquisando: {termo}", {"last_action": "pesquisar", "last_search": termo}

        m = re.match(r"^mouse:\s*(.+)$", low)
        if m:
            return self._mouse_action(m.group(1).strip()), {"last_action": "mouse"}

        m = re.match(r"^escrever:\s*(.+)$", resposta.strip(), re.IGNORECASE)
        if m:
            return self._type_text(m.group(1).strip()), {"last_action": "escrever"}

        m = re.match(r"^tecla:\s*(.+)$", low)
        if m:
            return self._press_hotkey(m.group(1).strip()), {"last_action": "tecla"}

        return resposta, ctx

    def _open_app(self, name: str) -> str:
        aliases = [name, name.replace("_", " "), name.replace("-", " ")]
        for a in aliases:
            if a in SITE_MAP:
                webbrowser.open(SITE_MAP[a])
                return f"Abrindo {a} no navegador"
        for a in aliases:
            if a in CMD_MAP:
                subprocess.Popen(CMD_MAP[a], shell=True)
                return f"Abrindo {a}"
        found = self._cache.get(name)
        if found:
            os.startfile(found)
            return f"Abrindo {name}"
        if "." in name and " " not in name:
            url = name if name.startswith("http") else f"https://{name}"
            webbrowser.open(url)
            return f"Abrindo {url} no navegador"
        try:
            subprocess.Popen(f"start {name}", shell=True)
            return f"Tentando abrir {name}"
        except Exception:
            return f"Não encontrei '{name}'"

    def _close_app(self, name: str) -> str:
        exe = name if name.lower().endswith(".exe") else name + ".exe"
        killed = any(
            (proc.terminate() or True)
            for proc in psutil.process_iter(["name"])
            if proc.info["name"] and proc.info["name"].lower() == exe.lower()
        )
        return f"{'Fechando' if killed else 'Processo não encontrado:'} {name}"

    def _mouse_action(self, action: str) -> str:
        try:
            import pyautogui
            actions = {
                "clique":      pyautogui.click,
                "duplo":       pyautogui.doubleClick,
                "direito":     lambda: pyautogui.click(button="right"),
                "rolar_cima":  lambda: pyautogui.scroll(3),
                "rolar_baixo": lambda: pyautogui.scroll(-3),
            }
            fn = actions.get(action)
            if fn:
                fn()
                return f"Mouse: {action}"
            return f"Ação desconhecida: {action}"
        except ImportError:
            return "pyautogui não instalado"

    def _type_text(self, text: str) -> str:
        try:
            import pyautogui
            try:
                import pyperclip
                pyperclip.copy(text)
                pyautogui.hotkey("ctrl", "v")
            except ImportError:
                pyautogui.typewrite(text, interval=0.03)
            return f"Escrito: {text}"
        except ImportError:
            return "pyautogui não instalado"
        except Exception as e:
            return f"Erro ao escrever: {e}"

    def _press_hotkey(self, atalho: str) -> str:
        try:
            import pyautogui
            resultados = []
            for item in [s.strip() for s in atalho.split(",")]:
                norm = _normalize_hotkey(item)
                teclas = norm.split("+")
                pyautogui.hotkey(*teclas) if len(teclas) > 1 else pyautogui.press(teclas[0])
                resultados.append(norm)
            return f"Tecla(s): {', '.join(resultados)}"
        except ImportError:
            return "pyautogui não instalado"
        except Exception as e:
            return f"Erro ao pressionar tecla: {e}"


# ══════════════════════════════════════════════════════════════════════════════
# SESSION
# ══════════════════════════════════════════════════════════════════════════════
class Session:
    def __init__(self, llm: LLMClient, executor: CommandExecutor, tts: TTSEngine) -> None:
        self._llm      = llm
        self._executor = executor
        self._tts      = tts

        self._history:      list[dict] = []
        self._history_lock  = threading.Lock()
        self._cmd_history:  list[dict] = []
        self._chat_history: list[dict] = []

        self.context = {"last_app": None, "last_action": None, "last_search": None}
        self._context_lock = threading.Lock()

        self._cmd_queue: Queue[Optional[str]] = Queue()
        self._on_log: Optional[Callable] = None

        self._worker_thread = threading.Thread(
            target=self._process_worker, name="session-worker", daemon=True
        )
        self._worker_thread.start()

    def set_log_callback(self, cb: Callable) -> None:
        self._on_log = cb

    def _log(self, sender: str, msg: str, tag: str = "normal") -> None:
        log.info("[%s] %s", sender, msg)
        if self._on_log:
            self._on_log(sender, msg, tag)

    def _add_history(self, role: str, content: str) -> None:
        with self._history_lock:
            self._history.append({"role": role, "content": content})
            self._history = self._history[-20:]

    def _get_history(self) -> list[dict]:
        with self._history_lock:
            return list(self._history)

    def _update_context(self, updates: dict) -> None:
        with self._context_lock:
            for k, v in updates.items():
                if v is not None:
                    self.context[k] = v

    def _get_context(self) -> dict:
        with self._context_lock:
            return dict(self.context)

    def _enrich(self, user_input: str) -> str:
        low = user_input.lower()
        ctx = self._get_context()
        if (re.match(r"^(?:pesquisa|busca|procura)\s+", low)
                and ctx.get("last_app") in SITE_MAP
                and "site:" not in low and " no " not in low and " na " not in low):
            return f"{user_input} no {ctx['last_app']}"
        return user_input

    def process(self, user_input: str) -> None:
        self._cmd_queue.put(user_input)

    def _process_worker(self) -> None:
        while True:
            try:
                user_input = self._cmd_queue.get(timeout=0.5)
            except Empty:
                continue
            if user_input is None:
                self._cmd_queue.task_done()
                break
            try:
                self._process_impl(user_input)
            except Exception as e:
                log.error("Session worker erro: %s", e, exc_info=True)
                self._log("sistema", f"Erro interno: {e}", "status")
            finally:
                self._cmd_queue.task_done()

    def _process_impl(self, user_input: str) -> None:
        if _is_blacklisted(user_input):
            self._log("sistema", "Entrada rejeitada por segurança.", "status")
            return

        self._log("usuario", user_input, "user")

        msg = detect_ambiguity(user_input)
        if msg:
            self._log("assistente", msg, "bruna")
            self._tts.speak(msg)
            return

        self._log("sistema", "Processando...", "status")
        intent = classify_intent(user_input, self._llm)

        enriched = self._enrich(user_input)
        self._add_history("user", enriched)

        if intent == "comando":
            local_cmd = try_local_command(user_input, self._get_context())
            if local_cmd:
                resultado, ctx_up = self._executor.run(local_cmd)
                self._add_history("assistant", local_cmd)
                self._cmd_history.append({"input": user_input, "cmd": local_cmd})
            else:
                try:
                    resposta_llm = self._llm.interpret_command(self._get_history())
                except Exception as e:
                    self._log("sistema", f"Erro na API: {e}", "status")
                    self._tts.speak("Erro ao processar")
                    with self._history_lock:
                        if self._history:
                            self._history.pop()
                    return

                self._add_history("assistant", resposta_llm)

                if resposta_llm.strip().upper() == "NO_COMMAND":
                    try:
                        resposta_chat = self._llm.interpret_chat(self._get_history())
                    except Exception as e:
                        self._log("sistema", f"Erro na API (chat): {e}", "status")
                        self._tts.speak("Erro ao processar")
                        return
                    self._add_history("assistant", resposta_chat)
                    self._chat_history.append({"input": user_input, "response": resposta_chat})
                    self._log("assistente", resposta_chat, "bruna")
                    self._tts.speak(resposta_chat[:200])
                    return

                resultado, ctx_up = self._executor.run(resposta_llm)
                self._cmd_history.append({"input": user_input, "cmd": resposta_llm})

            self._update_context(ctx_up)
            self._log("assistente", resultado, "bruna")
            self._tts.speak(resultado[:120])

        else:
            try:
                resposta_chat = self._llm.interpret_chat(self._get_history())
            except Exception as e:
                self._log("sistema", f"Erro na API: {e}", "status")
                self._tts.speak("Erro ao processar")
                with self._history_lock:
                    if self._history:
                        self._history.pop()
                return
            self._add_history("assistant", resposta_chat)
            self._chat_history.append({"input": user_input, "response": resposta_chat})
            self._log("assistente", resposta_chat, "bruna")
            self._tts.speak(resposta_chat[:200])

    def reset(self) -> None:
        self._tts.stop()
        with self._history_lock:
            self._history.clear()
        with self._context_lock:
            self.context = {"last_app": None, "last_action": None, "last_search": None}
        self._cmd_history.clear()
        self._chat_history.clear()

    def shutdown(self) -> None:
        self._cmd_queue.put(None)
        self._worker_thread.join(timeout=5)


# ══════════════════════════════════════════════════════════════════════════════
# UI
# ══════════════════════════════════════════════════════════════════════════════
class AssistenteUI:
    def __init__(self, session: Session, wake_word: str) -> None:
        self._session   = session
        self._wake_word = wake_word
        self._window:    Optional[tk.Tk]                     = None
        self._text_area: Optional[scrolledtext.ScrolledText] = None
        self._input_var: Optional[tk.StringVar]              = None
        self._alive      = threading.Event()

    def start(self) -> None:
        threading.Thread(target=self._build, name="ui-thread", daemon=True).start()
        self._alive.wait(timeout=5)

    def _build(self) -> None:
        W, H = 420, 600
        self._window = tk.Tk()
        self._window.overrideredirect(True)
        self._window.attributes("-topmost", True)
        self._window.configure(bg="#0d0d1a")
        self._window.minsize(320, 400)
        self._window.update_idletasks()
        sh = self._window.winfo_screenheight()
        self._window.geometry(f"{W}x{H}+16+{sh - H - 48}")
        self._window.configure(highlightbackground="#2a2a4a", highlightthickness=1)

        header = tk.Frame(self._window, bg="#12122a", pady=10)
        header.pack(fill="x")

        dot_frame = tk.Frame(header, bg="#12122a")
        dot_frame.pack(side="left", padx=14)
        for color in ("#ff5f57", "#febc2e", "#28c840"):
            tk.Label(dot_frame, text="●", fg=color, bg="#12122a",
                     font=("Arial", 9)).pack(side="left", padx=2)

        tk.Label(header, text="Assistente IA", font=("Segoe UI", 11, "bold"),
                 bg="#12122a", fg="#e0e0ff").pack(side="left", padx=6)

        tk.Button(
            header, text="✕", command=self._on_close,
            bg="#12122a", fg="#555577", font=("Arial", 10),
            relief="flat", cursor="hand2", padx=6,
            activebackground="#3a0a0a", activeforeground="#ff5f57", bd=0,
        ).pack(side="right", padx=6)

        self._status_dot = tk.Label(header, text="●", fg="#00ff88",
                                    bg="#12122a", font=("Arial", 9))
        self._status_dot.pack(side="right", padx=4)
        tk.Label(header, text="ativa", fg="#555577", bg="#12122a",
                 font=("Segoe UI", 9)).pack(side="right")

        self._drag_x = self._drag_y = 0
        for widget in [header] + list(header.winfo_children()):
            widget.bind("<ButtonPress-1>", self._drag_start)
            widget.bind("<B1-Motion>",     self._drag_move)

        tk.Frame(self._window, bg="#1e1e3a", height=1).pack(fill="x")

        self._text_area = scrolledtext.ScrolledText(
            self._window, wrap=tk.WORD, bg="#0d0d1a", fg="#c8c8e8",
            font=("Segoe UI", 10), state=tk.DISABLED, relief="flat",
            padx=12, pady=8, spacing1=4, spacing3=4, cursor="arrow",
        )
        self._text_area.pack(fill="both", expand=True)

        for tag, fg, font in [
            ("user",   "#a0a8ff", ("Segoe UI", 10, "bold")),
            ("bruna",  "#00e676", ("Segoe UI", 10)),
            ("status", "#ffd740", ("Segoe UI", 9, "italic")),
        ]:
            self._text_area.tag_config(tag, foreground=fg, font=font,
                                       lmargin1=8, lmargin2=8)
        self._text_area.tag_config("timestamp", foreground="#383858",
                                   font=("Segoe UI", 8))

        tk.Frame(self._window, bg="#1e1e3a", height=1).pack(fill="x")

        input_bar = tk.Frame(self._window, bg="#12122a", pady=10, padx=10)
        input_bar.pack(fill="x")

        self._input_var = tk.StringVar()
        entry = tk.Entry(
            input_bar, textvariable=self._input_var, bg="#1e1e3a", fg="#e0e0ff",
            font=("Segoe UI", 10), insertbackground="#a0a8ff", relief="flat",
            highlightthickness=1, highlightcolor="#3a3a6a", highlightbackground="#252545",
        )
        entry.pack(side="left", fill="x", expand=True, ipady=7, padx=(0, 8))
        entry.bind("<Return>", lambda _: self._on_send())
        entry.focus_set()

        tk.Button(
            input_bar, text="↑", command=self._on_send,
            bg="#4a4aff", fg="white", font=("Arial", 13, "bold"),
            relief="flat", width=3, cursor="hand2",
            activebackground="#6666ff", activeforeground="white",
        ).pack(side="left", ipady=4)

        footer = tk.Frame(self._window, bg="#0a0a18", pady=6)
        footer.pack(fill="x")
        tk.Button(
            footer, text="⏻  Desativar", command=self._on_close,
            bg="#0a0a18", fg="#ff5f57", font=("Segoe UI", 9), relief="flat",
            cursor="hand2", activebackground="#1a0a0a", activeforeground="#ff5f57",
        ).pack(side="right", padx=12)
        tk.Label(footer, text="Groq · llama-3", fg="#2a2a4a",
                 bg="#0a0a18", font=("Segoe UI", 8)).pack(side="left", padx=12)

        self._window.protocol("WM_DELETE_WINDOW", self._on_close)
        self._session.set_log_callback(self.append_message)
        self._alive.set()
        self.append_message(self._wake_word, "Pronta. Diga ou digite um comando.", "status")
        self._window.mainloop()
        self._alive.clear()

    def append_message(self, sender: str, msg: str, tag: str = "normal") -> None:
        ts = time.strftime("%H:%M")
        if self._text_area and self._window:
            try:
                self._window.after(0, lambda: self._write(ts, sender, msg, tag))
            except tk.TclError:
                pass

    def _write(self, ts: str, sender: str, msg: str, tag: str) -> None:
        if not self._text_area:
            return
        label_map = {
            "user": "Você", "bruna": "Assistente",
            "assistente": "Assistente", "status": "Sistema",
        }
        try:
            self._text_area.config(state=tk.NORMAL)
            self._text_area.insert(tk.END, f"{ts}  ", "timestamp")
            label = label_map.get(tag, sender.capitalize())
            self._text_area.insert(tk.END, f"{label}: ", tag)
            self._text_area.insert(tk.END, f"{msg}\n", tag)
            self._text_area.config(state=tk.DISABLED)
            self._text_area.see(tk.END)
        except tk.TclError:
            pass

    def _drag_start(self, event) -> None:
        self._drag_x = event.x_root - self._window.winfo_x()
        self._drag_y = event.y_root - self._window.winfo_y()

    def _drag_move(self, event) -> None:
        self._window.geometry(f"+{event.x_root - self._drag_x}+{event.y_root - self._drag_y}")

    def _on_send(self) -> None:
        if not self._input_var:
            return
        text = self._input_var.get().strip()
        if text:
            self._input_var.set("")
            self._session.process(text)

    def _on_close(self) -> None:
        if self._window:
            try:
                self._window.quit()
                self._window.destroy()
            except tk.TclError:
                pass
            finally:
                self._window = None

    def is_alive(self) -> bool:
        return self._alive.is_set()


# ── controlador de voz ────────────────────────────────────────────────────────
class VoiceController:
    def __init__(self, cfg: Config, session: Session, tts: TTSEngine,
                 voice_event=None) -> None:
        self._cfg         = cfg
        self._session     = session
        self._tts         = tts
        self._active      = threading.Event()
        self._ui:         Optional[AssistenteUI] = None
        self._voice_event = voice_event or threading.Event()
        self._voice_event.set()

    def _get_ui(self) -> AssistenteUI:
        if not self._ui or not self._ui.is_alive():
            self._ui = AssistenteUI(self._session, self._cfg.wake_word)
            self._ui.start()
        return self._ui

    def run(self) -> None:
        rec = sr.Recognizer()
        rec.energy_threshold     = self._cfg.sr_energy_threshold
        rec.pause_threshold      = self._cfg.sr_pause_threshold
        rec.dynamic_energy_threshold = True

        log.info("Aguardando wake word: '%s'", self._cfg.wake_word)
        with sr.Microphone() as mic:
            rec.adjust_for_ambient_noise(mic, duration=1)
            while self._voice_event.is_set():
                try:
                    if self._active.is_set():
                        self._listen_command(rec, mic)
                    else:
                        self._listen_wake(rec, mic)
                except Exception as e:
                    log.error("Erro no loop de voz: %s", e)
        self._tts.stop()

    def _listen_wake(self, rec: sr.Recognizer, mic: sr.Microphone) -> None:
        try:
            audio = rec.listen(mic, phrase_time_limit=3)
            text  = rec.recognize_google(audio, language="pt-BR").lower()
            if any(w in text for w in WAKE_WORDS):
                self._active.set()
                self._tts.speak(f"Olá {self._cfg.user_name}")
                self._session.reset()
                self._get_ui()
        except (sr.WaitTimeoutError, sr.UnknownValueError):
            pass

    def _listen_command(self, rec: sr.Recognizer, mic: sr.Microphone) -> None:
        try:
            audio   = rec.listen(mic, timeout=self._cfg.listen_timeout, phrase_time_limit=25)
            comando = rec.recognize_google(audio, language="pt-BR")
            if any(p in comando.lower() for p in ["desativar", "desligar", "pare"]):
                self._tts.speak("Até logo")
                self._active.clear()
                if self._ui:
                    self._ui._on_close()
                return
            cmd = comando.strip()
            for w in WAKE_WORDS:
                cmd = re.sub(rf"^{re.escape(w)},?\s*", "", cmd, flags=re.IGNORECASE).strip()
            self._session.process(cmd)
        except sr.WaitTimeoutError:
            self._tts.speak("Desativando por inatividade")
            self._active.clear()
        except sr.UnknownValueError:
            self._tts.speak("Não entendi")


# ── factory ───────────────────────────────────────────────────────────────────
def build_app(cfg: Config = CFG) -> tuple[Session, TTSEngine]:
    tts      = TTSEngine(cfg)
    cache    = ExeCache(cfg.cache_file, max_depth=cfg.exe_search_max_depth,
                        cache_ttl=cfg.exe_cache_ttl)
    executor = CommandExecutor(cache)
    llm      = LLMClient(cfg)
    session  = Session(llm, executor, tts)
    return session, tts


# ── compatibilidade com rotas.py / Flask ──────────────────────────────────────
def reconhecimento_de_voz(voice_event, nome_usuario: str = CFG.user_name) -> None:
    session, tts = build_app(CFG)
    VoiceController(CFG, session, tts, voice_event).run()


def processar_comando(user_input: str) -> str:
    session, _ = build_app(CFG)
    resultado: list[str] = []
    session.set_log_callback(lambda s, m, t: resultado.append(m))
    session.process(user_input)
    session._cmd_queue.join()
    return resultado[-1] if resultado else ""


# ── main ──────────────────────────────────────────────────────────────────────
def main() -> None:
    import sys
    session, tts = build_app(CFG)

    if len(sys.argv) > 1 and sys.argv[1] == "--text":
        ui = AssistenteUI(session, CFG.wake_word)
        ui.start()
        while True:
            try:
                cmd = input(f"{CFG.user_name}: ").strip()
            except (EOFError, KeyboardInterrupt):
                break
            if cmd.lower() in ("sair", "exit", "quit"):
                break
            session.process(cmd)
    else:
        vc = VoiceController(CFG, session, tts)
        try:
            vc.run()
        finally:
            session.shutdown()
            tts.shutdown()


if __name__ == "__main__":
    main()
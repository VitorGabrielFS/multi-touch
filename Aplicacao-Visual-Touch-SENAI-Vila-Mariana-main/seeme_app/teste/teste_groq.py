import os
import requests
import json
import subprocess
import re
import webbrowser
import ctypes
import ctypes.wintypes

# opcional para controle do mouse
try:
    import pyautogui
except Exception:
    pyautogui = None

# ---------------- CONFIG ----------------

MODEL = "llama-3.1-8b-instant"
ENDPOINT = "https://api.groq.com/openai/v1/chat/completions"

CACHE_FILE = "apps_cache.json"

# ---------------- PASTAS COMUNS ----------------
def get_desktop_path():
    CSIDL_DESKTOP = 0x0000
    SHGFP_TYPE_CURRENT = 0
    buf = ctypes.create_unicode_buffer(ctypes.wintypes.MAX_PATH)
    ctypes.windll.shell32.SHGetFolderPathW(None, CSIDL_DESKTOP, None, SHGFP_TYPE_CURRENT, buf)
    return buf.value

pastas_comuns = [
    os.environ.get("PROGRAMFILES", ""),
    os.environ.get("PROGRAMFILES(X86)", ""),
    os.path.join(os.environ.get("USERPROFILE", ""), "AppData", "Local", "Microsoft", "WindowsApps"),
    os.path.join(os.environ.get("USERPROFILE", ""), "AppData", "Roaming"),
    os.path.join(os.environ.get("USERPROFILE", ""), "AppData", "Local"),
    get_desktop_path()
]

# ---------------- MAPS / BLACKLIST / SYSTEM PROMPT ----------------
CMD_MAP = {
    "chrome": "start chrome",
    "google chrome": "start chrome",
    "edge": "start msedge",
    "microsoft edge": "start msedge",
    "firefox": "start firefox",
    "notepad": "notepad",
    "bloco de notas": "notepad",
    "calc": "calc",
    "calculadora": "calc",
    "spotify": "start spotify",
    "vlc": "start vlc",
    "explorer": "explorer",
    "file explorer": "explorer",
    "terminal": "start cmd",
    "prompt de comando": "start cmd",
    "powershell": "start powershell",
    "tarefas": "taskmgr",
}

# Apps que precisam busca de executável (não funcionam com start)
# REMOVIDO - agora aprende qualquer app automaticamente

BLACKLIST = [
    "shutdown", "restart", "reboot", "format", "del ", "erase ", "rd ", "rmdir ",
    "shutdown.exe", "format.com", "diskpart", "clean", "remove", "rm -rf",
    "mkfs", "cipher", "bcdedit", "sc config", "net user", "net localgroup",
]

SYSTEM_PROMPT = (
    "Você é um assistente que interpreta comandos do usuário. "
    "Para ABRIR aplicativos, responda APENAS o nome do aplicativo (ex: 'chrome', 'whatsapp', 'spotify'). "
    "Para PESQUISAR, responda: 'pesquisar [termo]'. "
    "Para ações do mouse, responda: 'clicar', 'duplo clique', 'clique direito', 'rolar para baixo/cima'. "
    "Para FECHAR, responda: 'fechar [app]'. "
    "NÃO explique. Se inválido, responda: NO_COMMAND"
)

# ---------------- CACHE UTIL ----------------
def carregar_cache():
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def salvar_cache(cache):
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2, ensure_ascii=False)

# ---------------- GROQ CALL ----------------
def groq_interpret(prompt_text):
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt_text}
        ],
        "temperature": 0.0,
        "max_tokens": 80
    }
    headers = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}
    resp = requests.post(ENDPOINT, headers=headers, data=json.dumps(payload), timeout=15)
    if resp.status_code != 200:
        raise RuntimeError(f"Erro API ({resp.status_code}): {resp.text}")
    return resp.json()["choices"][0]["message"]["content"].strip()

# ---------------- UTILIDADES ----------------
def contains_blacklisted(text):
    t = (text or "").lower()
    for bad in BLACKLIST:
        if bad in t:
            return True
    return False

# ---------------- BUSCA DE EXECUTÁVEIS (do código de voz) ----------------
def procurar_exe(nome_exe):
    """
    Busca executável:
    1) Tenta 'where' primeiro (rápido)
    2) Busca manual nas pastas comuns
    """
    # Garante que tenha .exe
    if not nome_exe.lower().endswith('.exe'):
        nome_exe = nome_exe + '.exe'
    
    # 1) Tentativa rápida com 'where'
    try:
        resultado = subprocess.check_output(
            ['where', nome_exe], 
            shell=True, 
            text=True, 
            stderr=subprocess.DEVNULL,
            timeout=2
        )
        caminhos = resultado.strip().splitlines()
        if caminhos:
            print(f" [where] Encontrado: {caminhos[0]}")
            return caminhos[0]
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        pass

    # 2) Busca manual nas pastas comuns
    print(f" [Buscando manualmente] {nome_exe}...")
    for pasta in pastas_comuns:
        if not pasta or not os.path.exists(pasta):
            continue
        try:
            for root, _, files in os.walk(pasta):
                for f in files:
                    if f.lower() == nome_exe.lower():
                        caminho = os.path.join(root, f)
                        print(f" [manual] Encontrado: {caminho}")
                        return caminho
        except (PermissionError, OSError):
            continue
    
    return None

def procurar_exe_cacheado(nome):
    """Usa cache primeiro, depois busca"""
    cache = carregar_cache()
    key = nome.lower()
    
    # Verifica cache
    if key in cache and os.path.exists(cache[key]):
        print(f" [cache] Usando: {cache[key]}")
        return cache[key]

    # Busca
    caminho = procurar_exe(nome)
    if caminho:
        cache[key] = caminho
        salvar_cache(cache)
        print(f" [salvo] Adicionado ao cache!")
        return caminho
    return None

# ---------------- AÇÕES DE UI ----------------
def executar_pesquisa(texto):
    t = texto.lower()
    termo = re.sub(r"^(pesquisar|pesquisa)\s*", "", t).strip()
    if not termo:
        termo = texto
    
    # detectar o tipo de pesquisa
    if "youtube" in t or "no youtube" in t:
        # remover "youtube" e "no youtube" do termo
        termo = re.sub(r"\b(no\s+)?youtube\b", "", termo).strip()
        url = f"https://www.youtube.com/results?search_query={termo.replace(' ', '+')}"
    elif "edge" in t or "bing" in t:
        # remover "edge" e "bing" do termo
        termo = re.sub(r"\b(edge|bing)\b", "", termo).strip()
        url = f"https://www.bing.com/search?q={termo.replace(' ', '+')}"
    else:
        url = f"https://www.google.com/search?q={termo.replace(' ', '+')}"
    
    webbrowser.open(url)

def executar_click_coords(x, y):
    if not pyautogui:
        return False
    pyautogui.moveTo(x, y)
    pyautogui.click()
    return True

def executar_click_generic(texto):
    if not pyautogui:
        return False
    m_coords = re.search(r"(\d{1,4})[^\d]+(\d{1,4})", texto)
    if m_coords:
        x, y = int(m_coords.group(1)), int(m_coords.group(2))
        return executar_click_coords(x, y)
    pyautogui.click()
    return True

def executar_double_click():
    if not pyautogui:
        return False
    pyautogui.doubleClick()
    return True

def executar_right_click():
    if not pyautogui:
        return False
    pyautogui.click(button='right')
    return True

def executar_scroll(direction="down"):
    if not pyautogui:
        return False
    if direction == "up":
        pyautogui.scroll(500)
    else:
        pyautogui.scroll(-500)
    return True

def fechar_app_by_name(nome):
    nome_exe = nome if nome.lower().endswith('.exe') else nome + '.exe'
    comando = f'taskkill /F /IM {nome_exe} /T'
    try:
        subprocess.run(comando, shell=True, capture_output=True, text=True, timeout=10)
    except Exception:
        pass

# ---------------- EXECUÇÃO SEGURA ----------------
def safe_execute_command(command):
    if contains_blacklisted(command):
        raise RuntimeError("Comando contém palavra proibida.")
    if os.path.exists(command):
        try:
            os.startfile(command)
            return
        except Exception:
            pass
    subprocess.Popen(command, shell=True)

# ---------------- MAIN LOOP ----------------
if __name__ == "__main__":
    print("Groq -> exec (abrir/fechar/pesquisar/clicar/scroll). Digite 'sair' para encerrar.\n")

    while True:
        user_input = input("Você: ").strip()
        if not user_input:
            continue
        if user_input.lower() in ["sair", "exit", "quit"]:
            break

        # Chama Groq para interpretar
        try:
            resposta = groq_interpret(user_input)
        except Exception as e:
            print("Erro API:", e)
            continue

        # Segurança básica
        if contains_blacklisted(resposta):
            print("Resposta rejeitada.")
            continue

        low = resposta.lower()

        # 1) Primeiro tenta mapear comando conhecido do CMD_MAP (mais rápido)
        mapped = None
        for key in sorted(CMD_MAP.keys(), key=lambda x: -len(x)):
            if key in low:
                mapped = CMD_MAP[key]
                break

        if mapped:
            try:
                print("Executando:", mapped)
                safe_execute_command(mapped)
            except Exception as e:
                print("Erro ao executar:", e)
            continue

        # 2) Busca inteligente de apps (aprende e guarda no cache)
        # Ignora se for claramente um comando de pesquisa/UI
        if not any(palavra in low for palavra in ["pesquisar", "pesquisa", "search", "clicar", "click", "rolar", "scroll", "fechar", "close"]):
            # Extrai possível nome de app da resposta da Groq
            m_app = re.search(r"([\w\-\_]+\.exe)|\b([\w\-\_]{2,})\b", resposta, re.IGNORECASE)
            app_to_try = None
            if m_app:
                app_to_try = (m_app.group(1) or m_app.group(2) or "").strip()

            # Se não extraiu da resposta, tenta do input do usuário
            if not app_to_try or app_to_try.lower() in ["no", "command", "no_command", "abrir", "abre", "open"]:
                # Tenta extrair do input direto (ex: "abrir whatsapp" -> "whatsapp")
                m_user = re.search(r"(?:abrir|abre|open)\s+([a-zA-Z0-9\-\_]+)", user_input, re.IGNORECASE)
                if m_user:
                    app_to_try = m_user.group(1).strip()

            if app_to_try and app_to_try.lower() not in ["no", "command", "no_command", "abrir", "abre", "open"]:
                nome_clean = app_to_try.lower().replace('.exe', '')
                print(f"Procurando '{nome_clean}'...")
                
                # Busca com cache (aprende automaticamente)
                caminho = procurar_exe_cacheado(nome_clean)
                
                if caminho:
                    try:
                        print(f"✓ Encontrado e salvo: {caminho}")
                        try:
                            os.startfile(caminho)
                        except Exception:
                            subprocess.Popen([caminho], shell=False)
                        continue
                    except Exception as e:
                        print("Erro ao executar:", e)
                else:
                    # Não encontrou - tenta via start como fallback
                    tentativa_start = f"start {nome_clean}"
                    try:
                        if contains_blacklisted(tentativa_start):
                            print("Resposta rejeitada.")
                            continue
                        print(f"× Não encontrado localmente. Tentando via PATH: {tentativa_start}")
                        result = subprocess.run(tentativa_start, shell=True, capture_output=True, timeout=2)
                        if result.returncode == 0:
                            print("✓ Aberto via PATH")
                        else:
                            print(f"× '{nome_clean}' não encontrado no sistema.")
                        continue
                    except Exception:
                        print(f"× '{nome_clean}' não encontrado no sistema.")
                        continue

        # 3) Pesquisa
        if "pesquisar" in low or "pesquisa" in low or "youtube" in low or "google" in low:
            try:
                executar_pesquisa(resposta if "pesquisar" in low else user_input)
                print("Executando pesquisa.")
            except Exception as e:
                print("Erro pesquisa:", e)
            continue

        # 4) Ações de UI
        if any(k in low for k in ["clicar", "click", "duplo", "double click", "clique direito", "right click", "rolar", "scroll"]):
            try:
                if "duplo" in low or "double" in low:
                    ok = executar_double_click()
                    if ok: print("Executando: duplo clique")
                elif "direito" in low or "right click" in low or "clique direito" in low:
                    ok = executar_right_click()
                    if ok: print("Executando: clique direito")
                elif "rolar" in low or "scroll" in low:
                    if "para cima" in low or "up" in low:
                        executar_scroll("up")
                        print("Executando: rolar para cima")
                    else:
                        executar_scroll("down")
                        print("Executando: rolar para baixo")
                else:
                    ok = executar_click_generic(resposta if "clicar" in low else user_input)
                    if ok: print("Executando: clique")
            except Exception as e:
                print("Erro ação mouse:", e)
            continue

        # 5) Fechar app
        if any(w in low for w in ["fechar", "fecha", "close", "kill"]):
            m = re.search(r"(fechar|close)\s+([a-zA-Z0-9\-\_ ]+)", resposta, re.IGNORECASE)
            if not m:
                m = re.search(r"(fechar|close)\s+([a-zA-Z0-9\-\_ ]+)", user_input, re.IGNORECASE)
            if m:
                app = m.group(2).strip()
                app_key = app.lower().split()[0]
                fechar_app_by_name(app_key)
                print("Executando: fechar", app_key)
                continue

        # 6) Fallback: pesquisa no navegador
        print("Nenhum comando detectado — abrindo pesquisa no navegador.")
        try:
            webbrowser.open(f"https://www.google.com/search?q={user_input.replace(' ', '+')}")
        except Exception:
            pass


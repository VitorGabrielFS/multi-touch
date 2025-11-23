import os, json, subprocess, webbrowser, ctypes, ctypes.wintypes, threading, time, re
import requests
import speech_recognition as sr
import pyttsx3
import tkinter as tk
from tkinter import scrolledtext
from dotenv import load_dotenv
import os

# Procura o arquivo .env em diferentes locais
env_paths = ['.env', 'seeme_app/.env', '../.env']
for path in env_paths:
    if os.path.exists(path):
        load_dotenv(path)
        break
else:
    load_dotenv()  # Fallback para o padrão

# ---------------- CONFIG ----------------
API_KEY = os.getenv('API_KEY')
MODEL = "llama-3.1-8b-instant"
ENDPOINT = "https://api.groq.com/openai/v1/chat/completions"
CACHE_FILE = "apps_cache.json"
MYNAME = "gabriel"
WAKE_WORD = "teste"
assistente_ativa = False
popup_window = None
chat_text_area = None
chat_log = []

# ---------------- PASTAS COMUNS ----------------
def get_desktop_path():
    buf = ctypes.create_unicode_buffer(ctypes.wintypes.MAX_PATH)
    ctypes.windll.shell32.SHGetFolderPathW(None, 0x0000, None, 0, buf)
    return buf.value

PASTAS_COMUNS = [
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
    "edge": "start msedge",
    "firefox": "start firefox",
    "notepad": "notepad",
    "calc": "calc",
    "spotify": "start spotify",
    "vlc": "start vlc",
    "explorer": "explorer",
    "terminal": "start cmd",
    "powershell": "start powershell",
    "tarefas": "taskmgr",
}

BLACKLIST = [
    "shutdown", "restart", "reboot", "format", "del ", "erase ", "rd ", "rmdir ",
    "shutdown.exe", "format.com", "diskpart", "clean", "remove", "rm -rf",
    "mkfs", "cipher", "bcdedit", "sc config", "net user", "net localgroup",
]

SYSTEM_PROMPT = (
    "Você é um assistente que interpreta comandos do usuário. "
    "Para ABRIR aplicativos, responda APENAS o nome do aplicativo (ex: 'chrome'). "
    "Para PESQUISAR, responda: 'pesquisar [termo]'. "
    "Para ações do mouse, responda: 'clicar', 'duplo clique', 'clique direito', 'rolar para baixo/cima'. "
    "Para FECHAR, responda: 'fechar [app]'. "
    "NÃO explique. Se inválido, responda: NO_COMMAND"
)

# ---------------- UTILITÁRIOS ----------------
def carregar_cache(): 
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE,"r",encoding="utf-8") as f: return json.load(f)
        except: return {}
    return {}

def salvar_cache(cache):
    with open(CACHE_FILE,"w",encoding="utf-8") as f: json.dump(cache,f,indent=2,ensure_ascii=False)

def contains_blacklisted(text):
    return any(bad in (text or "").lower() for bad in BLACKLIST)

def safe_execute_command(cmd):
    if contains_blacklisted(cmd): raise RuntimeError("Comando proibido.")
    try:
        os.startfile(cmd) if os.path.exists(cmd) else subprocess.Popen(cmd, shell=True)
    except Exception as e:
        print(f"Erro ao executar: {e}")

def procurar_exe(nome_exe):
    if not nome_exe.lower().endswith('.exe'): nome_exe += '.exe'
    try:
        out = subprocess.check_output(['where', nome_exe], shell=True, text=True, stderr=subprocess.DEVNULL, timeout=2)
        if out.strip(): return out.strip().splitlines()[0]
    except: pass
    for pasta in PASTAS_COMUNS:
        if not pasta or not os.path.exists(pasta): continue
        for root, _, files in os.walk(pasta):
            for f in files:
                if f.lower() == nome_exe.lower(): return os.path.join(root, f)
    return None

def procurar_exe_cacheado(nome):
    cache = carregar_cache()
    key = nome.lower()
    if key in cache and os.path.exists(cache[key]): return cache[key]
    caminho = procurar_exe(nome)
    if caminho: cache[key]=caminho; salvar_cache(cache)
    return caminho

def executar_pesquisa(termo):
    url = "https://www.google.com/search?q=" + termo.replace(" ","+")
    webbrowser.open(url)

# ---------------- TTS ----------------
def falar(texto):
    try:
        engine = pyttsx3.init()
        for voice in engine.getProperty('voices'):
            if "portuguese" in voice.name.lower() or "maria" in voice.name.lower():
                engine.setProperty('voice', voice.id)
                break
        engine.setProperty('rate', 180)
        engine.say(texto); engine.runAndWait()
    except: pass

# ---------------- POPUP ----------------
def log_mensagem(remetente, msg, tag='normal'):
    global chat_log, chat_text_area, popup_window
    timestamp = time.strftime("%H:%M:%S")
    entry = f"[{timestamp}] {remetente.capitalize()}: {msg}\n"
    chat_log.append(entry)
    if chat_text_area and popup_window:
        popup_window.after(0, lambda: [
            chat_text_area.config(state=tk.NORMAL),
            chat_text_area.insert(tk.END, entry, tag),
            chat_text_area.config(state=tk.DISABLED),
            chat_text_area.see(tk.END)
        ])

def criar_popup():
    global popup_window, chat_text_area
    popup_window = tk.Tk(); popup_window.title("Assistente Bruna")
    popup_window.geometry("300x500"); popup_window.attributes("-topmost", True)
    frame = tk.Frame(popup_window, bg="#1a1a2e"); frame.pack(expand=True, fill="both", padx=10, pady=10)
    status_label = tk.Label(frame, text="🎤 Assistente Ativa 🎤", font=("Arial",14,"bold"), bg="#1a1a2e", fg="#00ff88")
    status_label.pack(pady=(0,10))
    chat_frame = tk.Frame(frame, bg="#2a2a44"); chat_frame.pack(fill="both",expand=True,pady=5)
    chat_text_area = scrolledtext.ScrolledText(chat_frame, wrap=tk.WORD, bg="#2a2a44", fg="#fff", font=("Consolas",10), state=tk.DISABLED)
    chat_text_area.pack(fill="both", expand=True)
    chat_text_area.tag_config('user', foreground='#ccc', font=('Consolas',10,'bold'))
    chat_text_area.tag_config('bruna', foreground='#0f0', font=('Consolas',10,'italic'))
    chat_text_area.tag_config('status', foreground='#ff0')
    log_mensagem(WAKE_WORD, "Estou pronta. Diga um comando.", 'status')
    close_btn = tk.Button(frame, text="Desativar", command=desativar_assistente, bg="#ff4444", fg="white", font=("Arial",10,"bold"), relief="flat")
    close_btn.pack(pady=10)
    popup_window.protocol("WM_DELETE_WINDOW", desativar_assistente)
    popup_window.mainloop()

def mostrar_popup(): threading.Thread(target=criar_popup, daemon=True).start()
def fechar_popup():
    global popup_window
    if popup_window: popup_window.quit(); popup_window.destroy(); popup_window=None
def desativar_assistente():
    global assistente_ativa; assistente_ativa=False; fechar_popup(); print("❌ Assistente desativada")

# ---------------- GROQ API ----------------
def groq_interpret(prompt_text):
    payload = {"model":MODEL,"messages":[{"role":"system","content":SYSTEM_PROMPT},{"role":"user","content":prompt_text}],"temperature":0,"max_tokens":80}
    headers={"Authorization":f"Bearer {API_KEY}","Content-Type":"application/json"}
    r = requests.post(ENDPOINT, headers=headers, data=json.dumps(payload), timeout=15)
    if r.status_code!=200: raise RuntimeError(f"Erro API ({r.status_code}): {r.text}")
    return r.json()["choices"][0]["message"]["content"].strip()

# ---------------- COMANDO ----------------
def processar_comando(user_input):
    log_mensagem(MYNAME, user_input,'user'); log_mensagem(WAKE_WORD,"Processando...",'status')
    try: resposta = groq_interpret(user_input)
    except Exception as e: falar("Erro ao processar"); log_mensagem(WAKE_WORD,"Erro na API",'status'); return
    if contains_blacklisted(resposta): falar("Comando rejeitado"); log_mensagem(WAKE_WORD,"Comando rejeitado",'status'); return
    low=resposta.lower()

    # 1) CMD_MAP
    for key in sorted(CMD_MAP.keys(), key=lambda x:-len(x)):
        if key in low: safe_execute_command(CMD_MAP[key]); falar(f"Executando {key}"); log_mensagem(WAKE_WORD,f"Executando {key}",'bruna'); return

    # 2) Abrir app
    if not any(k in low for k in ["pesquisar","click","scroll","fechar"]):
        m = re.search(r"([\w\-\_]+\.exe)|\b([\w\-\_]{2,})\b", resposta, re.I)
        if m:
            nome = (m.group(1) or m.group(2)).replace(".exe","").lower()
            caminho = procurar_exe_cacheado(nome)
            if caminho: safe_execute_command(caminho); falar(f"Abrindo {nome}"); log_mensagem(WAKE_WORD,f"Abrindo {nome}",'bruna'); return
            try: safe_execute_command(f"start {nome}"); falar(f"Tentando abrir {nome}"); log_mensagem(WAKE_WORD,f"Tentando abrir {nome}",'bruna'); return
            except: falar(f"Não encontrei {nome}"); log_mensagem(WAKE_WORD,f"Não encontrei {nome}",'status'); return

    # 3) Pesquisa
    if any(k in low for k in ["pesquisar","youtube","google"]): executar_pesquisa(user_input); falar("Pesquisando"); log_mensagem(WAKE_WORD,"Pesquisa executada",'bruna'); return

    # 4) Fallback
    webbrowser.open(f"https://www.google.com/search?q={user_input.replace(' ','+')}")
    falar("Pesquisando no navegador"); log_mensagem(WAKE_WORD,"Fallback pesquisa",'bruna')

# ---------------- VOZ ----------------
def reconhecimento_de_voz(nome_usuario):
    global assistente_ativa
    rec = sr.Recognizer()
    with sr.Microphone() as mic:
        while True:
            try:
                if assistente_ativa:
                    log_mensagem(WAKE_WORD,"Ouvindo...",'status')
                    try:
                        audio = rec.listen(mic, timeout=30, phrase_time_limit=10)
                        comando = rec.recognize_google(audio, language="pt-BR")
                        if any(p in comando.lower() for p in ["desativar","desligar"]): falar("Até logo"); desativar_assistente(); continue
                        processar_comando(comando)
                    except sr.WaitTimeoutError: falar("Desativando por inatividade"); desativar_assistente()
                    except sr.UnknownValueError: falar("Não entendi")
                else:
                    audio = rec.listen(mic, phrase_time_limit=3)
                    try: text = rec.recognize_google(audio, language="pt-BR").lower()
                    except: continue
                    if WAKE_WORD in text: assistente_ativa=True; falar(f"Olá {nome_usuario}"); mostrar_popup()
            except KeyboardInterrupt: desativar_assistente(); falar("Até logo"); break
            except Exception as e: print("Erro:",e)

# ---------------- MAIN ----------------
if __name__=="__main__":
    import sys
    if len(sys.argv)>1 and sys.argv[1]=="--text":
        assistente_ativa=True; mostrar_popup()
        while True:
            cmd=input(f"{MYNAME}: ").strip()
            if cmd.lower() in ["sair","exit","quit"]: desativar_assistente(); break
            processar_comando(cmd)
    else: reconhecimento_de_voz()

import os
import requests
import json
import subprocess
import re
import webbrowser
import ctypes
import ctypes.wintypes
import speech_recognition as sr
import pyttsx3
import tkinter as tk
from tkinter import ttk, scrolledtext # Importação de scrolledtext para o histórico
import threading
import time # Para adicionar timestamp nas mensagens
from dotenv import load_dotenv
load_dotenv()
# opcional para controle do mouse
try:
    import pyautogui
except Exception:
    pyautogui = None

# ---------------- CONFIG ----------------
API_KEY = os.getenv("API_KEY")
MODEL = "llama-3.1-8b-instant"
ENDPOINT = "https://api.groq.com/openai/v1/chat/completions"

CACHE_FILE = "apps_cache.json"
MYNAME = "gabriel"
WAKE_WORD = "bruna"

# Estado global da assistente
assistente_ativa = False
popup_window = None
chat_text_area = None # Novo: Área de texto para o chat
chat_log = [] # Novo: Histórico de chat

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

# ---------------- POPUP ----------------
def log_mensagem(remetente, mensagem, tag='normal'):
    """Adiciona uma mensagem ao histórico de chat e atualiza o widget de texto."""
    global chat_log, chat_text_area, popup_window
    
    timestamp = time.strftime("%H:%M:%S")
    
    # Mensagem formatada para o log
    log_entry = f"[{timestamp}] {remetente.capitalize()}: {mensagem}\n"
    chat_log.append(log_entry)
    
    if chat_text_area and popup_window:
        # Garante que a atualização ocorra na thread principal do Tkinter
        popup_window.after(0, lambda: [
            chat_text_area.config(state=tk.NORMAL), # Habilita edição temporariamente
            chat_text_area.insert(tk.END, log_entry, tag),
            chat_text_area.config(state=tk.DISABLED), # Desabilita edição
            chat_text_area.see(tk.END) # Rola para o final
        ])

def atualizar_chat(user_text, bruna_text):
    """Logs o comando do usuário e a resposta da Bruna."""
    # Log da fala do usuário
    log_mensagem(MYNAME, user_text, 'user')
    
    # Log da resposta da Bruna
    log_mensagem(WAKE_WORD, bruna_text, 'bruna')
    

def criar_popup():
    """Cria popup visual indicando que a assistente está ativa"""
    global popup_window, chat_text_area
    
    popup_window = tk.Tk()
    popup_window.title("Assistente Bruna")
    popup_window.attributes('-topmost', True)
    popup_window.geometry("300x500") # Janela retangular alta
    popup_window.configure(bg='#1a1a2e')
    
    # Centralizar na tela (mantendo na parte superior)
    popup_window.update_idletasks()
    x = (popup_window.winfo_screenwidth() // 2) - (300 // 2)
    y = 50
    popup_window.geometry(f"300x500+{x}+{y}")
    
    # Conteúdo principal
    frame = tk.Frame(popup_window, bg='#1a1a2e')
    frame.pack(expand=True, fill='both', padx=10, pady=10)
    
    # Título/Status
    status_label = tk.Label(
        frame, 
        text="🎤 Assistente Ativa 🎤", 
        font=("Arial", 14, "bold"),
        bg='#1a1a2e',
        fg='#00ff88'
    )
    status_label.pack(pady=(0, 10))

    # --- Área do Chat Scrollável ---
    chat_frame = tk.Frame(frame, bg='#2a2a44')
    chat_frame.pack(fill='both', expand=True, pady=5)
    
    chat_text_area = scrolledtext.ScrolledText(
        chat_frame,
        wrap=tk.WORD,
        font=("Consolas", 10),
        bg='#2a2a44',
        fg='#ffffff',
        relief=tk.FLAT,
        state=tk.DISABLED # Começa desabilitado para não ser editável
    )
    chat_text_area.pack(fill='both', expand=True)

    # Configuração de tags de cor para melhor visualização
    chat_text_area.tag_config('user', foreground='#cccccc', font=('Consolas', 10, 'bold'))
    chat_text_area.tag_config('bruna', foreground='#00ff88', font=('Consolas', 10, 'italic'))
    chat_text_area.tag_config('status', foreground='#ffcc00')
    
    # Mensagem inicial da Bruna
    log_mensagem(WAKE_WORD, "Estou pronta. Diga um comando.", tag='status')
    
    # --- Fim Área do Chat ---
    
    # Botão fechar
    close_btn = tk.Button(
        frame,
        text="Desativar",
        command=desativar_assistente,
        bg='#ff4444',
        fg='white',
        font=("Arial", 10, "bold"),
        relief='flat',
        cursor='hand2'
    )
    close_btn.pack(pady=10)
    
    popup_window.protocol("WM_DELETE_WINDOW", desativar_assistente)
    popup_window.mainloop()

def mostrar_popup():
    """Mostra o popup em uma thread separada"""
    thread = threading.Thread(target=criar_popup, daemon=True)
    thread.start()

def fechar_popup():
    """Fecha o popup"""
    global popup_window
    if popup_window:
        try:
            popup_window.quit()
            popup_window.destroy()
            popup_window = None
        except Exception:
            pass

def desativar_assistente():
    """Desativa a assistente e fecha o popup"""
    global assistente_ativa
    assistente_ativa = False
    fechar_popup()
    print("❌ Assistente desativada\n")

# ---------------- VOZ ----------------
def falar(texto):
    """Text-to-speech em português"""
    try:
        engine = pyttsx3.init()
        voices = engine.getProperty('voices')
        for voice in voices:
            if "portuguese" in voice.name.lower() or "maria" in voice.name.lower():
                engine.setProperty('voice', voice.id)
                break
        engine.setProperty('rate', 180)
        engine.say(texto)
        engine.runAndWait()
    except Exception as e:
        print(f"Erro ao falar: {e}")

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

# ---------------- BUSCA DE EXECUTÁVEIS ----------------
def procurar_exe(nome_exe):
    """Busca executável: 1) where, 2) manual"""
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

    # 2) Busca manual
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
    
    if key in cache and os.path.exists(cache[key]):
        print(f" [cache] Usando: {cache[key]}")
        return cache[key]

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
    
    if "youtube" in t or "no youtube" in t:
        termo = re.sub(r"\b(no\s+)?youtube\b", "", termo).strip()
        url = f"https://www.youtube.com/results?search_query={termo.replace(' ', '+')}"
    elif "edge" in t or "bing" in t:
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
        resultado = subprocess.run(comando, shell=True, capture_output=True, text=True, timeout=10)
        if "SUCCESS" in resultado.stdout:
            print(f"✓ '{nome_exe}' fechado com sucesso.")
            falar(f"Aplicativo {nome} fechado.")
        else:
            print(f"× Não foi possível fechar '{nome_exe}'.")
            falar(f"Não consegui fechar {nome}.")
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

# ---------------- PROCESSAMENTO DE COMANDO ----------------
def processar_comando(user_input):
    """Processa comando (texto ou voz) via Groq"""
    
    # Logs o que o usuário disse
    log_mensagem(MYNAME, user_input, 'user')
    log_mensagem(WAKE_WORD, "Processando...", 'status')
    
    bruna_response = "Desculpe, não entendi o que você quer." # Resposta padrão
    
    # Chama Groq para interpretar
    try:
        resposta = groq_interpret(user_input)
    except Exception as e:
        print("Erro API:", e)
        falar("Erro ao processar comando.")
        log_mensagem(WAKE_WORD, "Erro na API de processamento.", 'status')
        return

    # Segurança básica
    if contains_blacklisted(resposta):
        print("Resposta rejeitada.")
        falar("Comando rejeitado por segurança.")
        log_mensagem(WAKE_WORD, "Comando rejeitado por segurança.", 'status')
        return

    low = resposta.lower()
    
    # 1) Tenta mapear comando conhecido do CMD_MAP
    mapped = None
    for key in sorted(CMD_MAP.keys(), key=lambda x: -len(x)):
        if key in low:
            mapped = CMD_MAP[key]
            bruna_response = f"Executando {key}..."
            break

    if mapped:
        try:
            print("Executando:", mapped)
            safe_execute_command(mapped)
            falar("Comando executado.")
        except Exception as e:
            print("Erro ao executar:", e)
            falar("Erro ao executar.")
            bruna_response = "Erro ao executar o comando no sistema."
        log_mensagem(WAKE_WORD, bruna_response, 'bruna')
        return

    # 2) Busca inteligente de apps
    if not any(palavra in low for palavra in ["pesquisar", "pesquisa", "search", "clicar", "click", "rolar", "scroll", "fechar", "close"]):
        m_app = re.search(r"([\w\-\_]+\.exe)|\b([\w\-\_]{2,})\b", resposta, re.IGNORECASE)
        app_to_try = None
        if m_app:
            app_to_try = (m_app.group(1) or m_app.group(2) or "").strip()

        if not app_to_try or app_to_try.lower() in ["no", "command", "no_command", "abrir", "abre", "open"]:
            m_user = re.search(r"(?:abrir|abre|open)\s+([a-zA-Z0-9\-\_]+)", user_input, re.IGNORECASE)
            if m_user:
                app_to_try = m_user.group(1).strip()

        if app_to_try and app_to_try.lower() not in ["no", "command", "no_command", "abrir", "abre", "open"]:
            nome_clean = app_to_try.lower().replace('.exe', '')
            print(f"Procurando '{nome_clean}'...")
            
            caminho = procurar_exe_cacheado(nome_clean)
            
            if caminho:
                try:
                    print(f"✓ Encontrado: {caminho}")
                    try:
                        os.startfile(caminho)
                    except Exception:
                        subprocess.Popen([caminho], shell=False)
                    falar(f"Abrindo {nome_clean}.")
                    bruna_response = f"Abrindo {nome_clean}."
                    log_mensagem(WAKE_WORD, bruna_response, 'bruna')
                    return
                except Exception as e:
                    print("Erro ao executar:", e)
                    falar("Erro ao abrir aplicativo.")
                    bruna_response = "Erro ao abrir aplicativo."
                    log_mensagem(WAKE_WORD, bruna_response, 'status')
                    return
            else:
                tentativa_start = f"start {nome_clean}"
                try:
                    if contains_blacklisted(tentativa_start):
                        print("Resposta rejeitada.")
                        bruna_response = "Comando rejeitado por segurança."
                        log_mensagem(WAKE_WORD, bruna_response, 'status')
                        return
                    print(f"× Não encontrado. Tentando via PATH: {tentativa_start}")
                    result = subprocess.run(tentativa_start, shell=True, capture_output=True, timeout=2)
                    if result.returncode == 0:
                        print("✓ Aberto via PATH")
                        falar(f"Abrindo {nome_clean}.")
                        bruna_response = f"Abrindo {nome_clean} via PATH."
                        log_mensagem(WAKE_WORD, bruna_response, 'bruna')
                        return
                    else:
                        print(f"× '{nome_clean}' não encontrado.")
                        falar(f"Não encontrei {nome_clean}.")
                        bruna_response = f"Não encontrei {nome_clean}."
                        log_mensagem(WAKE_WORD, bruna_response, 'status')
                        return
                except Exception:
                    print(f"× '{nome_clean}' não encontrado.")
                    falar(f"Não encontrei {nome_clean}.")
                    bruna_response = f"Não encontrei {nome_clean}."
                    log_mensagem(WAKE_WORD, bruna_response, 'status')
                    return

    # 3) Pesquisa
    if "pesquisar" in low or "pesquisa" in low or "youtube" in low or "google" in low:
        try:
            executar_pesquisa(resposta if "pesquisar" in low else user_input)
            print("Executando pesquisa.")
            falar("Pesquisando.")
            bruna_response = "Pesquisando no navegador."
        except Exception as e:
            print("Erro pesquisa:", e)
            falar("Erro ao pesquisar.")
            bruna_response = "Erro ao pesquisar."
        log_mensagem(WAKE_WORD, bruna_response, 'bruna')
        return

    # 4) Ações de UI
    if any(k in low for k in ["clicar", "click", "duplo", "double click", "clique direito", "right click", "rolar", "scroll"]):
        try:
            if "duplo" in low or "double" in low:
                ok = executar_double_click()
                if ok: 
                    print("Executando: duplo clique")
                    falar("Duplo clique.")
                    bruna_response = "Duplo clique realizado."
            elif "direito" in low or "right click" in low or "clique direito" in low:
                ok = executar_right_click()
                if ok: 
                    print("Executando: clique direito")
                    falar("Clique direito.")
                    bruna_response = "Clique direito realizado."
            elif "rolar" in low or "scroll" in low:
                if "para cima" in low or "up" in low:
                    executar_scroll("up")
                    print("Executando: rolar para cima")
                    falar("Rolando para cima.")
                    bruna_response = "Rolando para cima."
                else:
                    executar_scroll("down")
                    print("Executando: rolar para baixo")
                    falar("Rolando para baixo.")
                    bruna_response = "Rolando para baixo."
            else:
                ok = executar_click_generic(resposta if "clicar" in low else user_input)
                if ok: 
                    print("Executando: clique")
                    falar("Clique.")
                    bruna_response = "Clique realizado."
        except Exception as e:
            print("Erro ação mouse:", e)
            falar("Erro ao executar ação.")
            bruna_response = "Erro ao executar ação do mouse."
        log_mensagem(WAKE_WORD, bruna_response, 'bruna')
        return

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
            bruna_response = f"Fechando {app_key}."
            log_mensagem(WAKE_WORD, bruna_response, 'bruna')
            return

    # 6) Fallback: pesquisa no navegador
    print("Nenhum comando detectado — abrindo pesquisa no navegador.")
    try:
        webbrowser.open(f"https://www.google.com/search?q={user_input.replace(' ', '+')}")
        falar("Pesquisando no navegador.")
        bruna_response = "Comando não reconhecido. Pesquisando no Google."
    except Exception:
        bruna_response = "Comando não reconhecido. Falha ao pesquisar."
    log_mensagem(WAKE_WORD, bruna_response, 'bruna')


# ---------------- RECONHECIMENTO DE VOZ ----------------
def reconhecimento_de_voz():
    """Loop principal de reconhecimento de voz"""
    global assistente_ativa
    
    reconhecedor = sr.Recognizer()
    
    print(f"=== Assistente de Voz com Groq IA ===")
    print(f"Diga '{WAKE_WORD}' para ativar (apenas uma vez até desativar)\n")
    
    with sr.Microphone() as mic:
        while True:
            try:
                # Se já está ativa, aguarda comandos diretos
                if assistente_ativa:
                    print(f"🎤 Assistente ativa - aguardando comando...")
                    
                    # Loga o estado de escuta no chat
                    log_mensagem(WAKE_WORD, f"Ouvindo {MYNAME}...", 'status')
                    
                    try:
                        audio = reconhecedor.listen(mic, timeout=30, phrase_time_limit=10)
                        comando = reconhecedor.recognize_google(audio, language='pt-BR')
                        
                        # Verifica se quer desativar
                        if any(palavra in comando.lower() for palavra in ["desativar", "desligar", "tchau", "até logo"]):
                            falar("Desativando. Até logo.")
                            log_mensagem(MYNAME, comando, 'user')
                            log_mensagem(WAKE_WORD, "Desativando. Até logo.", 'status')
                            desativar_assistente()
                            continue
                        
                        # Processa o comando via Groq
                        processar_comando(comando)
                        
                    except sr.WaitTimeoutError:
                        print("⏱️ Sem comando por 30s - desativando.")
                        falar("Desativando por inatividade.")
                        log_mensagem(WAKE_WORD, "Desativando por inatividade.", 'status')
                        desativar_assistente()
                        continue
                    except sr.UnknownValueError:
                        print("❓ Não entendi o comando.")
                        falar("Não entendi.")
                        log_mensagem(MYNAME, "Não compreendido.", 'user')
                        log_mensagem(WAKE_WORD, "Não entendi o comando. Tente novamente.", 'status')
                    except sr.RequestError:
                        print("❌ Erro no serviço de voz.")
                        falar("Erro no serviço de voz.")
                        log_mensagem(WAKE_WORD, "Erro no serviço de voz.", 'status')
                    
                # Se não está ativa, aguarda wake word
                else:
                    print(f"😴 Aguardando '{WAKE_WORD}' para ativar...")
                    
                    try:
                        audio = reconhecedor.listen(mic, timeout=None, phrase_time_limit=3)
                    except sr.WaitTimeoutError:
                        continue
                    
                    try:
                        ativador = reconhecedor.recognize_google(audio, language='pt-BR').lower()
                    except sr.UnknownValueError:
                        continue
                    except sr.RequestError:
                        print("❌ Erro no serviço de voz.")
                        continue
                    
                    # Ativa apenas se detectar a wake word
                    if WAKE_WORD in ativador:
                        assistente_ativa = True
                        falar(f"Olá, senhor {MYNAME}. Estou pronta.")
                        print(f"✅ Assistente ativada!\n")
                        mostrar_popup()
                    
            except KeyboardInterrupt:
                print("\n👋 Encerrando assistente...")
                if assistente_ativa:
                    desativar_assistente()
                falar("Até logo.")
                break
            except Exception as e:
                print(f"❌ Erro: {e}")

# ---------------- MAIN ----------------
if __name__ == "__main__":
    import sys
    
    # Modo texto (para testes)
    if len(sys.argv) > 1 and sys.argv[1] == "--text":
        print("=== Modo Texto (para testes) ===")
        print("Digite comandos ou 'sair' para encerrar.\n")
        
        # Simula a assistente ativa e o popup para teste
        assistente_ativa = True
        mostrar_popup() 
        
        while True:
            user_input = input(f"{MYNAME}: ").strip()
            if not user_input:
                continue
            if user_input.lower() in ["sair", "exit", "quit"]:
                log_mensagem(MYNAME, user_input, 'user')
                log_mensagem(WAKE_WORD, "Encerrando modo texto.", 'status')
                desativar_assistente()
                break
            
            processar_comando(user_input)
            print()
    
    # Modo voz (padrão)
    else:
        reconhecimento_de_voz()
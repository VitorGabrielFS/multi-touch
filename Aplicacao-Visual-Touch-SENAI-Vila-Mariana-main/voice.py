import speech_recognition as sr
import subprocess
import webbrowser
import os
import pyttsx3
import pyautogui
import ctypes.wintypes
from pathlib import Path

myname = "gabriel"

def click(x, y):
    pyautogui.moveTo(x, y)
    pyautogui.click()

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

def falar(texto):
    engine = pyttsx3.init()
    voices = engine.getProperty('voices')
    for voice in voices:
        if "portuguese" in voice.name.lower() or "maria" in voice.name.lower():
            engine.setProperty('voice', voice.id)
            break
    engine.setProperty('rate', 180)
    engine.say(texto)
    engine.runAndWait()

def perguntar_site_ou_app(nome, reconhecedor, mic):
    print(f" Você quer abrir o site ou o aplicativo de '{nome}'?")
    print(" Diga apenas: site ou aplicativo")
    try:
        audio = reconhecedor.listen(mic, timeout=5)
        resposta = reconhecedor.recognize_google(audio, language='pt-BR').lower()
        print(f" Resposta detectada: {resposta}")
        return resposta
    except sr.WaitTimeoutError:
        print(" Tempo esgotado para resposta.")
    except sr.UnknownValueError:
        print(" Não entendi sua resposta.")
    except sr.RequestError:
        print(" Erro ao acessar serviço de voz.")
    return None

def procurar_exe(nome_exe):
    try:
        resultado = subprocess.check_output(['where', nome_exe], shell=True, text=True, stderr=subprocess.DEVNULL)
        caminhos = resultado.strip().splitlines()
        if caminhos:
            return caminhos[0]
    except subprocess.CalledProcessError:
        print(" [DEBUG] 'where' não encontrou o executável, procurando manualmente...")

    for pasta in pastas_comuns:
        if not pasta or not os.path.exists(pasta):
            continue
        for root, _, files in os.walk(pasta):
            for f in files:
                if f.lower() == nome_exe.lower():
                    print(f" [DEBUG] Encontrado manualmente em: {os.path.join(root, f)}")
                    return os.path.join(root, f)
    return None

def executar_pesquisa(comando):
    comando = comando.lower()
    if "youtube" in comando:
        termo = comando.replace("pesquisar", "").replace("no youtube", "").strip()
        url = f"https://www.youtube.com/results?search_query={termo.replace(' ', '+')}"
        print(f" Pesquisando no YouTube: {termo}")
        webbrowser.open(url)
    elif "google" in comando:
        termo = comando.replace("pesquisar", "").replace("no google", "").strip()
        url = f"https://www.google.com/search?q={termo.replace(' ', '+')}"
        print(f" Pesquisando no Google: {termo}")
        webbrowser.open(url)
    elif "navegador 2" in comando or "edge" in comando:
        termo = comando.replace("pesquisar", "") \
                       .replace("no edge", "") \
                       .replace("no navegador 2", "") \
                       .strip()
        url = f"https://www.bing.com/search?q={termo.replace(' ', '+')}"
        print(f" Pesquisando no Edge (Bing): {termo}")
        edge_path = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
        if os.path.exists(edge_path):
            webbrowser.register('edge', None, webbrowser.BackgroundBrowser(edge_path))
            webbrowser.get('edge').open(url)
        else:
            print(" Navegador Edge não encontrado, abrindo no navegador padrão...")
            webbrowser.open(url)
    else:
        termo = comando.replace("pesquisar", "").strip()
        url = f"https://www.google.com/search?q={termo.replace(' ', '+')}"
        print(f" Pesquisando: {termo}")
        webbrowser.open(url)

def fechar_app(nome):
    nome_exe = nome if nome.lower().endswith('.exe') else nome + '.exe'
    comando = f'taskkill /F /IM {nome_exe} /T'
    try:
        resultado = subprocess.run(comando, shell=True, capture_output=True, text=True)
        if "SUCCESS" in resultado.stdout:
            print(f"Aplicativo '{nome_exe}' fechado com sucesso.")
            falar(f"Aplicativo {nome} fechado.")
        else:
            print(f"Não foi possível fechar o aplicativo '{nome_exe}'. Talvez não esteja aberto.")
            falar(f"Não consegui fechar o aplicativo {nome}.")
    except Exception as e:
        print(f"Erro ao tentar fechar o aplicativo: {e}")
        falar("Ocorreu um erro ao tentar fechar o aplicativo.")

def executar_com_voz(comando, reconhecedor, mic):
    comando = comando.lower()

    if "clicar" in comando or "click" in comando:
        pyautogui.click()
        print(" Clique do mouse realizado.")
        falar("Clique realizado.")
        return

    if "duplo clique" in comando or "double click" in comando:
        pyautogui.doubleClick()
        print(" Duplo clique do mouse realizado.")
        falar("Duplo clique realizado.")
        return

    if "rolar para cima" in comando or "scroll up" in comando or "escrolar para cima" in comando:
        pyautogui.scroll(500)
        print(" Rolagem para cima realizada.")
        falar("Rolando para cima.")
        return

    if "rolar para baixo" in comando or "scroll down" in comando or "escrolar para baixo" in comando:
        pyautogui.scroll(-500)
        print(" Rolagem para baixo realizada.")
        falar("Rolando para baixo.")
        return

    if "clique direito" in comando or "click direito" in comando or "botão direito" in comando:
        pyautogui.click(button='right')
        print(" Clique direito realizado.")
        falar("Clique direito realizado.")
        return

    if comando.startswith("abrir"):
        nome = comando.replace("abrir", "").strip()
        escolha = perguntar_site_ou_app(nome, reconhecedor, mic)
        if escolha is None:
            print(" Cancelado por falta de resposta.")
            return
        if "site" in escolha:
            url = f"https://{nome}.com"
            print(f" Abrindo site: {url}")
            webbrowser.open(url)
        elif "aplicativo" in escolha or "app" in escolha:
            nome_exe = nome + ".exe"
            caminho = procurar_exe(nome_exe)
            if caminho:
                print(f" Abrindo app: {caminho}")
                subprocess.Popen(caminho, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            else:
                print(f" Aplicativo '{nome_exe}' não encontrado.")
        return

    if comando.startswith("fechar"):
        nome = comando.replace("fechar", "").strip()
        fechar_app(nome)
        return

    if comando.startswith("pesquisar"):
        executar_pesquisa(comando)

def reconhecimento_de_voz():
    reconhecedor = sr.Recognizer()
    with sr.Microphone() as mic:
        while True:
            try:
                print(" Diga 'bruna' para ativar a assistente...")
                try:
                    audio = reconhecedor.listen(mic)
                except sr.WaitTimeoutError:
                    continue
                try:
                    ativador = reconhecedor.recognize_google(audio, language='pt-BR').lower()
                except sr.UnknownValueError:
                    continue
                except sr.RequestError:
                    print(" Erro no serviço de voz.")   
                    continue
                if 'bruna' in ativador:
                    falar(f"Olá, senhor {myname}.?")
                    print(f"Olá, sr {myname}.")
                    try:
                        audio = reconhecedor.listen(mic, timeout=10)
                        comando = reconhecedor.recognize_google(audio, language='pt-BR').lower()
                        print(f" Você disse: {comando}")
                        executar_com_voz(comando, reconhecedor, mic)
                    except sr.WaitTimeoutError:
                        print(" Tempo esgotado para comando.")
                    except sr.UnknownValueError:
                        print(" Não entendi o comando.")
                    except sr.RequestError:
                        print(" Erro no serviço de voz.")
            except Exception as e:
                print(f" Erro: {e}")

if __name__ == "__main__":
    reconhecimento_de_voz()

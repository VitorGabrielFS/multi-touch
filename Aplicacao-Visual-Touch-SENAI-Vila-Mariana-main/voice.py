import speech_recognition as sr
import subprocess
import webbrowser
import os
import pyttsx3

myname = "Gab"
# Pastas comuns para procurar .exe no Windows
pastas_comuns = [
    os.environ.get("PROGRAMFILES", ""),
    os.environ.get("PROGRAMFILES(X86)", ""),
    os.path.join(os.environ.get("USERPROFILE", ""), "AppData", "Local"),
    os.path.join(os.environ.get("USERPROFILE", ""), "Área de Trabalho"),
    os.path.join(os.environ.get("USERPROFILE", ""), "AppData", "Local", "Microsoft", "WindowsApps")
]

def procurar_exe(nome_exe):
    for pasta in pastas_comuns:
        if not pasta:
            continue
        for root, dirs, files in os.walk(pasta):
            if nome_exe.lower() in (f.lower() for f in files):
                return os.path.join(root, nome_exe)
    return None

def falar(texto):
    engine = pyttsx3.init()
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

    else:
        termo = comando.replace("pesquisar", "").strip()
        url = f"https://www.google.com/search?q={termo.replace(' ', '+')}"
        print(f" Pesquisando: {termo}")
        webbrowser.open(url)

def executar_com_voz(comando, reconhecedor, mic):
    comando = comando.lower()

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

    elif comando.startswith("pesquisar"):
        executar_pesquisa(comando)

def reconhecimento_de_voz():
    reconhecedor = sr.Recognizer()

    with sr.Microphone() as mic:
        while True:
            try:
                print(" Diga 'selene' para ativar a assistente...")
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

                if 'selene' in ativador:
                    falar(f"Olá, senhor {myname}. Preparado para compartilhar sua sabedoria com o mundo?")
                    print(f"Olá, sr {myname}. Preparado para compartilhar sua sabedoria com o mundo?")
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

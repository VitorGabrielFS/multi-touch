import speech_recognition as sr
import subprocess
import webbrowser
import os

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


def executar_com_voz(comando, reconhecedor, mic):
    nome = comando.replace("abrir", "").strip().lower()

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


def reconhecimento_de_voz():
    reconhecedor = sr.Recognizer()

    with sr.Microphone() as mic:
        print(" Diga algo como: 'abrir Netflix', 'abrir YouTube', etc...")

        while True:
            try:
                print(" Ouvindo...")
                audio = reconhecedor.listen(mic, timeout=5)
                comando = reconhecedor.recognize_google(audio, language='pt-BR').lower()
                print(f" Você disse: {comando}")

                if comando.startswith("abrir"):
                    executar_com_voz(comando, reconhecedor, mic)

            except sr.WaitTimeoutError:
                print(" Esperando voz...")
            except sr.UnknownValueError:
                print(" Não entendi.")
            except sr.RequestError:
                print(" Erro no serviço de voz.")
            except Exception as e:
                print(f" Erro: {e}")

if __name__ == "__main__":
    reconhecimento_de_voz()

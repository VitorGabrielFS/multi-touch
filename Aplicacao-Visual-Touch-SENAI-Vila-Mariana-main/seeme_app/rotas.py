from flask import Flask, render_template, Blueprint, Response
import threading
from flask_login import login_user, logout_user, login_required
from flask_login import current_user
from .control import voice_active_event, gestos_active_event, eye_tracking_active_event, resource_manager
from voice import reconhecimento_de_voz
from .eye import eye_tracking, set_tracking, cam
from .exec_mao import GestureController
from .modelos import Configuracoes
import webbrowser
import time
import subprocess
from flask import jsonify
import pyautogui
import threading
from plyer import notification
import win32clipboard
from io import BytesIO
import os
from flask import render_template, redirect, url_for, flash, request
from .modelos import Usuario
from .extensoes import db, bcrypt
from .modelos import Atalho

main = Blueprint('main', __name__)

@main.route('/', methods=['GET', 'POST'])
def index():
    return render_template('index.html')

@main.route('/home', methods=['GET', 'POST'])
@login_required
def home():
    return render_template('indexHome.html', title="Home")

@main.route('/cadastrarUsuario')
def cadastrar_usuario():
    return render_template('registrar.html', title="Cadastrar Usuário")

@main.route('/landing')
def landing():
    return render_template('landing.html')

@main.route('/ajustes')
@login_required
def ajustes():
    atalhos_usuario = current_user.atalhos
    try:
        if current_user.config is None:
            nova_config = Configuracoes(usuario=current_user)
            db.session.add(nova_config)
            db.session.commit()
            print(f"Objeto de configuração padrão criado para o usuário {current_user.id}")
            db.session.refresh(current_user)
    except Exception as e:
        db.session.rollback()
        flash(f"Erro ao criar configuração padrão: {e}", "danger")
    return render_template('ajustes.html', title="Ajustes e Atalhos", lista_atalhos=atalhos_usuario)

@main.route('/cadastroAtalho', methods=['GET', 'POST'])
@login_required
def cadastro_atalho():
    if request.method == 'POST':
        tipo_formulario = request.form.get('form_type')
        if tipo_formulario == "cadastrar_site":
            letra = request.form.get('letraNumero')
            if letra:
                letra = letra.upper()
                atalho_existente = Atalho.query.filter_by(
                    usuario_id=current_user.id,
                    letra_relacionada=letra
                ).first()
                if atalho_existente:
                    flash(f"A letra/número {letra} já está sendo usada por {atalho_existente.nome}", "danger")
                    return redirect(url_for("main.cadastro_atalho"))
            nome_site = request.form.get('nomeSite')
            url_site = request.form.get('entradaUrl')
            imagem_site = request.files.get('entradaImagem')
            novo_atalho = Atalho(nome=nome_site, tipo='site', caminho=url_site, usuario_id=current_user.id,
                                 dados_imagem=imagem_site.read() if imagem_site else None,
                                 letra_relacionada=request.form.get('letraNumero'))
            db.session.add(novo_atalho)
            db.session.commit()
            flash(f'Site "{nome_site}" cadastrado com sucesso!', 'success')
            return redirect(url_for('main.ajustes'))

        elif tipo_formulario == "cadastrar_acao":
            nome_acao = request.form.get('nomeAcao')
            tipo_acao = request.form.get('tipoAcao')
            match(tipo_acao):
                case "1": caminho_acao = "print_tela"
                case "2": caminho_acao = "encerrar_audio"
                case "3": caminho_acao = "fechar_camera"
                case "4": caminho_acao = "captura"
            novo_atalho = Atalho(nome=nome_acao, tipo='acao', caminho=caminho_acao,
                                 usuario_id=current_user.id,
                                 letra_relacionada=request.form.get('letraNumeroAcao'))
            db.session.add(novo_atalho)
            db.session.commit()
            flash(f'Ação "{nome_acao}" cadastrada com sucesso!', 'success')
            return redirect(url_for('main.ajustes'))

        elif tipo_formulario == "cadastrar_programa":
            nome_programa = request.form.get('nomePrograma')
            selecao_programa = request.form.get('selecaoPrograma')
            match(selecao_programa):
                case "1": caminho_programa = "C:\\Windows\\System32\\calc.exe"
                case "2": caminho_programa = "C:\\Windows\\System32\\notepad.exe"
                case "3": caminho_programa = "explorer"
                case "4": caminho_programa = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe"
                case _:   caminho_programa = ""
            novo_atalho = Atalho(nome=nome_programa, tipo='programa', caminho=caminho_programa,
                                 usuario_id=current_user.id,
                                 letra_relacionada=request.form.get('letraNumeroPrograma'))
            db.session.add(novo_atalho)
            db.session.commit()
            flash(f'Programa "{nome_programa}" cadastrado com sucesso!', 'success')
            return redirect(url_for('main.ajustes'))
        else:
            print("Tipo de formulário desconhecido.")
        return redirect(url_for('main.ajustes'))
    return render_template('cadastroAtalho.html', title="Cadastro de Atalhos")


@main.route('/excluir-atalho/<int:atalho_id>', methods=['POST'])
@login_required
def excluir_atalho(atalho_id):
    atalho_para_excluir = Atalho.query.get_or_404(atalho_id)
    if atalho_para_excluir.autor != current_user:       
        flash('Você não tem permissão para excluir este atalho.', 'danger')
        return redirect(url_for('main.ajustes'))
    try:
        db.session.delete(atalho_para_excluir)
        db.session.commit()
        flash('Atalho excluído com sucesso!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao excluir o atalho: {e}', 'danger')
    return redirect(url_for('main.ajustes'))


@main.route('/salvar_ajustes_olhos', methods=['POST'])
def salvar_ajustes_olhos():
    try:
        nova_sensibilidade = float(request.form.get('sensibilidadeInput'))
        nova_deadzone = float(request.form.get('deadzoneInput'))
        current_user.config.eye_sensitivity = nova_sensibilidade
        current_user.config.eye_deadzone = nova_deadzone
        db.session.commit()
        flash('Configurações oculares salvas com sucesso!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao salvar as configurações: {e}', 'danger')
    return redirect(url_for('main.ajustes'))


@main.route('/atalho-imagem/<int:atalho_id>')
@login_required
def get_atalho_imagem(atalho_id):
    atalho = Atalho.query.get_or_404(atalho_id)
    if atalho.autor != current_user:
        return "Acesso negado", 403
    if not atalho.dados_imagem:
        return "Imagem não encontrada", 404
    return Response(atalho.dados_imagem, mimetype='image/jpeg')


@main.route('/start-tracking')
def start_tracking():
    if not resource_manager.is_resource_active('eye_tracking'):
        if resource_manager.start_resource('eye_tracking'):
            configuracoes_usuario = current_user.config
            set_tracking(True)
            t = threading.Thread(target=eye_tracking,
                                 args=(eye_tracking_active_event, configuracoes_usuario,),
                                 daemon=True)
            t.start()
            eye_tracking.is_running = True
            return "Rastreamento ocular iniciado."
    return "Rastreamento ocular já está em andamento."


@main.route('/stop-tracking')
def stop_tracking():
    if resource_manager.is_resource_active('eye_tracking'):
        resource_manager.stop_resource('eye_tracking')
        set_tracking(False)
        eye_tracking.is_running = False
        resource_manager.release_shared_camera()
        return "Rastreamento ocular parado."
    return "Rastreamento ocular já está inativo."


@main.route('/start-voice')
def start_voice():
    if not resource_manager.is_resource_active('voice'):
        if resource_manager.start_resource('voice'):
            voice_active_event.set()
            threading.Thread(
            target=reconhecimento_de_voz,
            args=(voice_active_event, current_user.nome),
            daemon=True
        ).start()
            return "Reconhecimento de voz iniciado. Fale 'Bruna' para começar."
    return "Reconhecimento de voz já está em andamento."


@main.route('/stop-voice')
def stop_voice():
    if resource_manager.is_resource_active('voice'):
        resource_manager.stop_resource('voice')
        voice_active_event.clear()
        return "Reconhecimento de voz parado."
    return "Reconhecimento de voz já está inativo."


# ── GestureController global ──────────────────────────────────────────────────
controller = GestureController(
    tempo_minimo_gesto=1.0,
    intervalo_antiloop=2.0,
    espelhar_imagem=True
)

def _loop_gestos():
    """Thread que consome os frames do GestureController em background."""
    print("[GESTOS] thread iniciada, aguardando evento...")
    gestos_active_event.wait()  # espera o evento ser setado
    print("[GESTOS] evento recebido, abrindo câmera...")

    cap = resource_manager.get_shared_camera()
    print(f"[GESTOS] câmera obtida: {cap} | aberta: {cap.isOpened() if cap else 'N/A'}")

    if not cap or not cap.isOpened():
        print("[GESTOS] ERRO: câmera não disponível. Abortando thread.")
        resource_manager.stop_resource('gestos')
        gestos_active_event.clear()
        return

    # consome os frames (isso mantém o MediaPipe processando)
    for _ in controller.gerar_frames():
        if not gestos_active_event.is_set():
            break

    print("[GESTOS] thread encerrada.")


@main.route('/start-gestos')
@login_required
def start_gestos():
    if not resource_manager.is_resource_active('gestos'):
        if resource_manager.start_resource('gestos'):
            # Carrega atalhos do usuário e registra ações dinamicamente
            try:
                atalhos = Atalho.query.filter_by(usuario_id=current_user.id).order_by(Atalho.id).all()
                controller.acoes.clear()

                for atalho in atalhos:
                    letra = (atalho.letra_relacionada or '').strip()
                    if not letra:
                        print(f"Ignorando atalho '{atalho.nome}' sem 'letra_relacionada'.")
                        continue
                    try:
                        num_dedos = int(letra)
                    except ValueError:
                        print(f"Valor inválido em 'letra_relacionada' para atalho '{atalho.nome}': {letra}")
                        continue
                    if num_dedos < 0 or num_dedos > 5:
                        print(f"Número de dedos fora da faixa (0-5) para atalho '{atalho.nome}': {num_dedos}")
                        continue

                    if atalho.tipo == 'site':
                        def _open_site(a=atalho):
                            try:
                                webbrowser.open(a.caminho)
                            except Exception as e:
                                print('Erro ao abrir site do atalho:', e)
                        controller.registrar_acao(num_dedos, _open_site)

                    elif atalho.tipo == 'programa':
                        def _start_program(a=atalho):
                            try:
                                subprocess.Popen(a.caminho, shell=True)
                            except Exception as e:
                                print('Erro ao iniciar programa do atalho:', e)
                        controller.registrar_acao(num_dedos, _start_program)

                    elif atalho.tipo == 'acao':
                        match(atalho.caminho):
                            case "captura":
                                def _print_screen(a=atalho):
                                    try:
                                        pyautogui.press('printscreen')
                                    except Exception as e:
                                        print('Erro ao executar ação de print screen:', e)
                                controller.registrar_acao(num_dedos, _print_screen)

                            case "encerrar_audio":
                                def _stop_audio(a=atalho):
                                    try:
                                        voice_active_event.clear()
                                    except Exception as e:
                                        print('Erro ao executar ação de encerrar áudio:', e)
                                controller.registrar_acao(num_dedos, _stop_audio)

                            case "fechar_camera":
                                def _stop_gestos(a=atalho):
                                    try:
                                        if resource_manager.is_resource_active('gestos'):
                                            resource_manager.stop_resource('gestos')
                                            gestos_active_event.clear()
                                            resource_manager.release_shared_camera()
                                            print("Rastreamento de gestos finalizado via atalho.")
                                    except Exception as e:
                                        print('Erro ao executar ação de fechar câmera:', e)
                                controller.registrar_acao(num_dedos, _stop_gestos)

                            case "print_tela":
                                def _print_screen(a=atalho):
                                    try:
                                        foto = pyautogui.screenshot()
                                        caminho = os.path.join(os.path.expanduser("~"), "Pictures", "Screenshots")
                                        os.makedirs(caminho, exist_ok=True)
                                        filename = f"screenshot_{int(time.time())}.png"
                                        foto.save(os.path.join(caminho, filename))
                                        print(f'Screenshot salva em {os.path.join(caminho, filename)}')
                                        screenshot_to_clipboard(foto)
                                        notificaoes("Screenshot Capturada e Copiada",
                                                    f"Sua screenshot foi salva em {os.path.join(caminho, filename)}")
                                    except Exception as e:
                                        print('Erro ao executar print_tela:', e)
                                controller.registrar_acao(num_dedos, _print_screen)

                            case _:
                                print(f"Ação desconhecida para atalho '{atalho.nome}': {atalho.caminho}")
                    else:
                        def _noop(a=atalho):
                            print(f"Atalho '{a.nome}' (tipo={a.tipo}) acionado, mas nenhuma ação definida.")
                        controller.registrar_acao(num_dedos, _noop)

            except Exception as e:
                print('Erro ao carregar atalhos para gestos:', e)

            # Seta o evento E inicia a thread que processa a câmera
            gestos_active_event.set()
            threading.Thread(target=_loop_gestos, daemon=True).start()

            return "Rastreamento de gestos iniciado."
    return "Rastreamento de gestos já está em andamento."


@main.route('/rastreio-gestos')
def rastreio_gestos():
    if resource_manager.is_resource_active('gestos'):
        return Response(controller.gerar_frames(),
                        mimetype='multipart/x-mixed-replace; boundary=frame')
    return "Rastreamento não está ativo."


@main.route('/parar-rastreio-gestos')
@login_required
def stop_gestos():
    if resource_manager.is_resource_active('gestos'):
        resource_manager.stop_resource('gestos')
        gestos_active_event.clear()
        resource_manager.release_shared_camera()
        return "Rastreamento de gestos parado."
    return "Rastreamento de gestos já está inativo."


@main.route('/status-recursos')
def status_recursos():
    active = resource_manager.get_active_resources()
    status = {
        'eye_tracking': 'eye_tracking' in active,
        'voice': 'voice' in active,
        'gestos': 'gestos' in active,
        'total_active': len(active)
    }
    return status


@main.route('/registrar', methods=['GET', 'POST'])
def registrar():
    if current_user.is_authenticated:
        return redirect(url_for('main.home'))
    if request.method == 'POST':
        nome = request.form.get('entradaNome')
        email = request.form.get('entradaEmail')
        senha = request.form.get('entradaSenha')
        confirm_senha = request.form.get('confirmacaoSenha')
        if senha != confirm_senha:
            flash('As senhas não coincidem. Por favor, tente novamente.', 'danger')
            return redirect(url_for('main.registrar'))
        usuario_existente = Usuario.query.filter_by(email=email).first()
        if usuario_existente:
            flash('Email já cadastrado. Por favor, use outro email.', 'danger')
            return redirect(url_for('main.registrar'))
        senha_criptografada = bcrypt.generate_password_hash(senha).decode('utf-8')
        novo_usuario = Usuario(nome=nome, email=email, password_hash=senha_criptografada)
        db.session.add(novo_usuario)
        db.session.commit()
        flash('Sua conta foi criada com sucesso! Agora você pode fazer o login.', 'success')
        return redirect(url_for('main.login'))
    return render_template('registrar.html', title='Cadastro')


@main.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.home'))
    if request.method == 'POST':
        email = request.form.get('entradaEmail')
        senha = request.form.get('entradaSenha')
        usuario = Usuario.query.filter_by(email=email).first()
        if usuario and bcrypt.check_password_hash(usuario.password_hash, senha):
            login_user(usuario, remember=True)
            flash('Login realizado com sucesso!', 'success')
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('main.home'))
        else:
            flash('Login falhou. Verifique seu email e senha.', 'danger')
    return render_template('login.html', title='Login')


def screenshot_to_clipboard(imagem):
    image = imagem
    output = BytesIO()
    image.convert("RGB").save(output, "BMP")
    data = output.getvalue()[14:]
    output.close()
    win32clipboard.OpenClipboard()
    win32clipboard.EmptyClipboard()
    win32clipboard.SetClipboardData(win32clipboard.CF_DIB, data)
    win32clipboard.CloseClipboard()
    print("Print copiado para a área de transferência!")


@main.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('main.login'))


def notificaoes(titulo, mensagem):
    """Envia notificação nativa em thread separada para não travar o Flask."""
    def _notificar():
        try:
            notification.notify(
                title=titulo,
                message=mensagem,
                app_name='SeeMe',
                timeout=3
            )
        except Exception as e:
            print(f"Erro ao enviar notificação: {e}")
    threading.Thread(target=_notificar, daemon=True).start()
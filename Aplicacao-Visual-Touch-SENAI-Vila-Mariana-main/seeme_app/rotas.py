from flask import Flask, render_template, Blueprint, Response
import threading
from flask_login import login_user, logout_user, login_required
from flask_login import current_user
#se for rodar no senai, so comentar da linha 4 ate a 6 e da 21 ate 52
from .control import voice_active_event, gestos_active_event, eye_tracking_active_event, resource_manager
from voice import reconhecimento_de_voz
from .eye import eye_tracking, set_tracking, cam
from .exec_mao import GestureController
from .modelos import Configuracoes
import subprocess
from flask import jsonify

import os
from flask import render_template, redirect, url_for, flash, request
from .modelos import Usuario # Importa o modelo Usuario
from .extensoes import db, bcrypt # Importa o db e o bcrypt
from .modelos import Atalho

main = Blueprint('main', __name__)

@main.route('/', methods=['GET', 'POST'])
def index():
    return render_template('index.html')

@main.route('/home', methods=['GET', 'POST'])
@login_required
def home():
    return render_template('indexHome.html', title="Home")

"""
@main.route('/login')
def login():
    return render_template('login.html', title="Login")
"""


@main.route('/cadastrarUsuario')
def cadastrar_usuario():
    return render_template('registrar.html', title="Cadastrar Usuário")

@main.route('/landing')
def landing():
    return render_template('landing.html')

@main.route('/ajustes')
@login_required
def ajustes():
    #Pegar dados relacionados aos atalhos do usuário logado
    atalhos_usuario = current_user.atalhos  # Supondo que haja um relacionamento definido no modelo Usuario 
    
    try:
        if current_user.config is None:
            nova_config = Configuracoes(usuario=current_user)
            db.session.add(nova_config)
            db.session.commit()

            print(f"Objeto de configuração padrão criado para o usuário {current_user.id}")
            # Damos um 'refresh' para garantir que o current_user seja atualizado na sessão
            db.session.refresh(current_user) 

    except Exception as e:
        db.session.rollback()
        flash(f"Erro ao criar configuração padrão: {e}", "danger")

    return render_template('ajustes.html', title="Ajustes e Atalhos", lista_atalhos=atalhos_usuario)

@main.route('/cadastroAtalho', methods=['GET', 'POST'])
@login_required
def cadastro_atalho():
    if request.method == 'POST':

        # Identificar o tipo de formulário enviado
        tipo_formulario = request.form.get('form_type')
        if tipo_formulario == "cadastrar_site":
            letra = request.form.get('letraNumero')
            
            if letra:
                letra = letra.upper()
                #consultar no banco de dados se é a mesma letra
                atalho_existente = Atalho.query.filter_by(
                    usuario_id = current_user.id,
                    letra_relacionada = letra
                ).first()

                #Se letra/número já está sendo usado
                if atalho_existente:
                    flash(f"A letra/número {letra} já está sendo usada por {atalho_existente.nome}", "danger")
                    return redirect(url_for("main.cadastro_atalho"))

            nome_site = request.form.get('nomeSite')
            url_site = request.form.get('entradaUrl')
            imagem_site = request.files.get('entradaImagem')
            # Processar o cadastro do site aqui
            # Exemplo: salvar no banco de dados
            novo_atalho = Atalho(nome=nome_site, tipo='site', caminho=url_site, usuario_id=current_user.id, 
                                 dados_imagem=imagem_site.read() if imagem_site else None, letra_relacionada=request.form.get('letraNumero'))
            db.session.add(novo_atalho)
            db.session.commit()
            flash(f'Site "{nome_site}" cadastrado com sucesso!', 'success')

            return redirect(url_for('main.ajustes'))
        
        elif tipo_formulario == "cadastrar_acao":
            nome_acao = request.form.get('nomeAcao')
            tipo_acao = request.form.get('tipoAcao')
            # Processar o cadastro da ação aqui
            # Exemplo: salvar no banco de dados
            flash(f'Ação "{nome_acao}" cadastrada com sucesso!', 'success')
            return redirect(url_for('main.ajustes'))
        
        elif tipo_formulario == "cadastrar_programa":
            nome_programa = request.form.get('nomePrograma')
            selecao_programa = request.form.get('selecaoPrograma')
            # Processar o cadastro do programa aqui
            # Exemplo: salvar no banco de dados
            flash(f'Programa "{nome_programa}" cadastrado com sucesso!', 'success')
            return redirect(url_for('main.ajustes'))
        
        else:
            print("Tipo de formulário desconhecido.")
        # Aqui você pode processar os dados recebidos, como salvar no banco de dados
        # ou realizar outras ações necessárias.

        # Após processar os dados, você pode redirecionar ou renderizar uma página de sucesso.
        return redirect(url_for('main.ajustes'))

    return render_template('cadastroAtalho.html', title="Cadastro de Atalhos")

# seeme_app/rotas.py

@main.route('/excluir-atalho/<int:atalho_id>', methods=['POST']) # Usar POST é mais seguro para exclusões
@login_required
def excluir_atalho(atalho_id):
    # 1. Encontra o atalho no banco de dados ou retorna um erro 404 se não existir.
    atalho_para_excluir = Atalho.query.get_or_404(atalho_id)

    # 2. Medida de segurança: Garante que o usuário só pode excluir seus próprios atalhos.
    if atalho_para_excluir.autor != current_user:
        flash('Você não tem permissão para excluir este atalho.', 'danger')
        return redirect(url_for('main.ajustes'))

    try:
        # 3. O COMANDO FÁCIL: Marque o objeto para ser deletado e confirme.
        db.session.delete(atalho_para_excluir)
        db.session.commit()
        flash('Atalho excluído com sucesso!', 'success')
    except Exception as e:
        # Em caso de erro no banco, desfaz a operação e informa o usuário.
        db.session.rollback()
        flash(f'Erro ao excluir o atalho: {e}', 'danger')

    # 4. Redireciona o usuário de volta para a página de ajustes.
    return redirect(url_for('main.ajustes'))

@main.route('/salvar_ajustes_olhos', methods=['POST'])
def salvar_ajustes_olhos():
    try:
        #Pega os dados do formulário
        nova_sensibilidade = float(request.form.get('sensibilidadeInput'))
        nova_deadzone = float(request.form.get('deadzoneInput'))

        #Atualiza as configurações do usuário atual
        current_user.config.eye_sensitivity = nova_sensibilidade
        current_user.config.eye_deadzone = nova_deadzone

        db.session.commit()
        flash('Configurações oculares salvas com sucesso!', 'success')

    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao salvar as configurações: {e}', 'danger')
        # desfazemos a operação para não corromper o banco.
        db.session.rollback()
    return redirect(url_for('main.ajustes'))

@main.route('/atalho-imagem/<int:atalho_id>')
@login_required
def get_atalho_imagem(atalho_id):
        # Busca o atalho pelo ID
    atalho = Atalho.query.get_or_404(atalho_id)

    # Verificação de segurança: garante que o usuário só pode ver suas próprias imagens
    if atalho.autor != current_user:
        return "Acesso negado", 403

    # Se não houver imagem, retorna um erro (ou uma imagem padrão)
    if not atalho.dados_imagem:
        return "Imagem não encontrada", 404

    # Cria uma resposta HTTP com os dados da imagem e o tipo de conteúdo correto
    return Response(atalho.dados_imagem, mimetype='image/jpeg')

@main.route('/start-tracking')
def start_tracking():
    if not resource_manager.is_resource_active('eye_tracking'):
        if resource_manager.start_resource('eye_tracking'):
            configuracoes_usuario = current_user.config
            # Atualiza as configurações do eye.py com as do usuário
            set_tracking(True)
            t = threading.Thread(target=eye_tracking, args=(eye_tracking_active_event, 
                                                            configuracoes_usuario, ), daemon=True)
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
        # Libera a câmera compartilhada se não há mais recursos usando
        resource_manager.release_shared_camera()
        return "Rastreamento ocular parado."
    return "Rastreamento ocular já está inativo."

@main.route('/start-voice')
def start_voice():
    if not resource_manager.is_resource_active('voice'):
        if resource_manager.start_resource('voice'):
            voice_active_event.set()
            threading.Thread(target=reconhecimento_de_voz,args=(current_user.nome,), daemon=True).start()
            return "Reconhecimento de voz iniciado. Fale 'Bruna' para começar."
    return "Reconhecimento de voz já está em andamento."

@main.route('/stop-voice')
def stop_voice():
    if resource_manager.is_resource_active('voice'):
        resource_manager.stop_resource('voice')
        voice_active_event.clear()
        return "Reconhecimento de voz parado."
    return "Reconhecimento de voz já está inativo."
    voice_active_event.clear()
    return "Reconhecimento de voz parado."


controller = GestureController(
    tempo_minimo_gesto=1.0,  # segundos
    intervalo_antiloop=2.0,  # segundos
    espelhar_imagem=True     # Espelha a imagem como um espelho
)
controller.registrar_acao(1, lambda: subprocess.Popen("start chrome", shell=True))
controller.registrar_acao(2, lambda: subprocess.Popen("start notepad", shell=True))

@main.route('/start-gestos')
def start_gestos():
    if not resource_manager.is_resource_active('gestos'):
        if resource_manager.start_resource('gestos'):
            gestos_active_event.set()
            return "Rastreamento de gestos iniciado."
    return "Rastreamento de gestos já está em andamento."

@main.route('/rastreio-gestos')
def rastreio_gestos():
    # Se já estiver em execução, retorna mensagem informando isso
    if resource_manager.is_resource_active('gestos'):
        return Response(controller.gerar_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')
    return "Rastreamento não está ativo."



@main.route('/parar-rastreio-gestos')
@login_required
def stop_gestos():
    if resource_manager.is_resource_active('gestos'):
        resource_manager.stop_resource('gestos')
        gestos_active_event.clear()
        # Libera a câmera compartilhada se não há mais recursos usando
        resource_manager.release_shared_camera()
        return "Rastreamento de gestos parado."
    return "Rastreamento de gestos já está inativo."

@main.route('/status-recursos')
def status_recursos():
    """Retorna o status de todos os recursos"""
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
    # Se o usuário já estiver logado, redireciona para a home
    if current_user.is_authenticated:
        return redirect(url_for('main.home'))
    
    # Se o método for POST, significa que o formulário foi enviado
    if request.method == 'POST':
        # 1. PEGAR OS DADOS DO FORMULÁRIO
        nome = request.form.get('entradaNome')
        email = request.form.get('entradaEmail')
        senha = request.form.get('entradaSenha')
        confirm_senha = request.form.get('confirmacaoSenha')

    #Verifica se as senhas são iguais
        if senha != confirm_senha:
            flash('As senhas não coincidem. Por favor, tente novamente.', 'danger')
            return redirect(url_for('main.registrar'))
        
        # Verifica se o email já está cadastrado
        usuario_existente = Usuario.query.filter_by(email=email).first()
        if usuario_existente:
            flash('Email já cadastrado. Por favor, use outro email.', 'danger')
            return redirect(url_for('main.registrar'))
        
        #Criptografar a senha
        senha_criptografada = bcrypt.generate_password_hash(senha).decode('utf-8')
    
        # 2. CRIAR UM NOVO USUÁRIO
        novo_usuario = Usuario(nome = nome, email=email, password_hash=senha_criptografada)
        db.session.add(novo_usuario)
        db.session.commit()

        # 5. DAR FEEDBACK E REDIRECIONAR
        flash('Sua conta foi criada com sucesso! Agora você pode fazer o login.', 'success')
        return redirect(url_for('main.login'))

    # Se o método for GET, apenas exibe a página de registro
    return render_template('registrar.html', title='Cadastro')

@main.route('/login', methods=['GET', 'POST'])
def login():
    # Se o usuário já estiver logado, redireciona para a home
    if current_user.is_authenticated:
        return redirect(url_for('main.home'))
    
    if request.method == 'POST':
        # 1. PEGAR OS DADOS DO FORMULÁRIO
        email = request.form.get('entradaEmail')
        senha = request.form.get('entradaSenha')

        # 2. VERIFICAR SE O USUÁRIO EXISTE
        usuario = Usuario.query.filter_by(email=email).first()
        if usuario and bcrypt.check_password_hash(usuario.password_hash, senha):
            # 3. LOGAR O USUÁRIO
            
            login_user(usuario, remember=True) # Lembre-se do usuário
            flash('Login realizado com sucesso!', 'success')
            # Redireciona para a página que o usuário tentava acessar antes de ser
            # enviado para o login, ou para a home se não houver.
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('main.home'))
        else:
            flash('Login falhou. Verifique seu email e senha.', 'danger')

    return render_template('login.html', title='Login')

@main.route('/logout')
def logout():
    logout_user() # Função mágica do Flask-Login que encerra a sessão
    return redirect(url_for('main.login'))
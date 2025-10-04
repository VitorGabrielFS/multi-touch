from flask import Flask, render_template, Blueprint
import threading
from flask_login import login_user, logout_user, login_required
from flask_login import current_user
#se for rodar no senai, so comentar da linha 4 ate a 6 e da 21 ate 52
from .control import voice_active_event
from voice import reconhecimento_de_voz
from .eye import eye_tracking, set_tracking, cam
import os
from flask import render_template, redirect, url_for, flash, request
from .modelos import Usuario # Importa o modelo Usuario
from .extensoes import db, bcrypt # Importa o db e o bcrypt

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
    return render_template('ajustes.html', title="Ajustes e Atalhos")

@main.route('/cadastroAtalho')
def cadastro_atalho():
    return render_template('cadastroAtalho.html', title="Cadastro de Atalhos")

@main.route('/start-tracking')
def start_tracking():
    if not getattr(eye_tracking, 'is_running', False):
        set_tracking(True)
        t = threading.Thread(target=eye_tracking, daemon=True)
        t.start()
        eye_tracking.is_running = True
        return "Rastreamento iniciado."
    return "Rastreamento já está em andamento."

@main.route('/stop-tracking')
def stop_tracking():
    set_tracking(False)
    if cam is not None:
        cam.release()
    eye_tracking.is_running = False
    return "Rastreamento parado."

@main.route('/start-voice')
def start_voice():
    if not voice_active_event.is_set():
        voice_active_event.set()
        threading.Thread(target=reconhecimento_de_voz, daemon=True).start()
        return "Reconhecimento de voz iniciado."
    return "Reconhecimento de voz já está em andamento."

@main.route('/stop-voice')
def stop_voice():
    voice_active_event.clear()
    return "Reconhecimento de voz parado."

@main.route('/registrar', methods=['GET', 'POST'])
def registrar():
    # Se o usuário já estiver logado, redireciona para a home
    if current_user.is_authenticated:
        return redirect(url_for('main.home'))
    
    # Se o método for POST, significa que o formulário foi enviado
    if request.method == 'POST':
        # 1. PEGAR OS DADOS DO FORMULÁRIO
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
        novo_usuario = Usuario(email=email, password_hash=senha_criptografada)
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
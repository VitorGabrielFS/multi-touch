# seeme_app/__init__.py
from flask import Flask
from config import Config

# Importa as instâncias das extensões
from .extensoes import db, bcrypt, login_manager

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Inicializa as extensões com a aplicação
    db.init_app(app)
    bcrypt.init_app(app)
    login_manager.init_app(app)

    # Registra o Blueprint das rotas
    from .rotas import main as main_blueprint
    app.register_blueprint(main_blueprint)
    
    # É importante criar o contexto da aplicação para criar o banco
    with app.app_context():
        db.create_all() # Cria as tabelas do banco de dados se não existirem

    return app
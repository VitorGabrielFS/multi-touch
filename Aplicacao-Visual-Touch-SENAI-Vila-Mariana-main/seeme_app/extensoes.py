# seeme_app/extensions.py
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_login import LoginManager

db = SQLAlchemy()
bcrypt = Bcrypt()
login_manager = LoginManager()
login_manager.login_view = 'main.login' # 'main' é o nome do nosso Blueprint (veremos em routes.py)
# E esta é a mensagem que ele vai exibir
login_manager.login_message = "Por favor, faça o login para acessar esta página."
login_manager.login_message_category = 'info'

@login_manager.user_loader
def load_user(user_id):
    from .modelos import Usuario    # importe dentro da função para evitar ciclos
    return Usuario.query.get(int(user_id))
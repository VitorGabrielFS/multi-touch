# seeme_app/extensions.py
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_login import LoginManager

db = SQLAlchemy()
bcrypt = Bcrypt()
login_manager = LoginManager()
login_manager.login_view = 'main.login' # 'main' é o nome do nosso Blueprint (veremos em routes.py)
login_manager.login_message_category = 'info'
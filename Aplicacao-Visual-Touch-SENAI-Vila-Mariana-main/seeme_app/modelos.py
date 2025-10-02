# seeme_app/models.py
from .extensoes import db  # Importa a instância do db
from flask_login import UserMixin

# A função user_loader precisa estar aqui para acessar o modelo User
from .extensoes import login_manager 

class Usuario(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)

    def __repr__(self):
        return f'<Usuario {self.email}>'
    
@login_manager.user_loader
def load_user(user_id):
    return Usuario.query.get(int(user_id))
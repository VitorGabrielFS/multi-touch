# seeme_app/models.py
from .extensoes import db  # Importa a instância do db
from flask_login import UserMixin

# A função user_loader precisa estar aqui para acessar o modelo User
from .extensoes import login_manager 

class Usuario(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    atalhos = db.relationship('Atalho', backref='autor', lazy=True)
    # Itens relacionados ao usuário

    def __repr__(self):
        return f'<Usuario {self.email}>'
    
@login_manager.user_loader
def load_user(user_id):
    return Usuario.query.get(int(user_id))

class Atalho(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    letra_relacionada = db.Column(db.String(1), nullable=True)  # Letra associada ao atalho
    tipo = db.Column(db.String(50), nullable=False)
    caminho = db.Column(db.String(200), nullable=False)
    dados_imagem = db.Column(db.LargeBinary, nullable=True) # Armazena a imagem como dados binários
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)


    def __repr__(self):
        return f'<Item {self.nome}>'
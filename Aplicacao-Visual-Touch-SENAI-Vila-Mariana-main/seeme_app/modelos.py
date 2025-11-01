# seeme_app/models.py
from .extensoes import db  # Importa a instância do db
from flask_login import UserMixin
from sqlalchemy import UniqueConstraint

# A função user_loader precisa estar aqui para acessar o modelo User
from .extensoes import login_manager 

class Usuario(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    atalhos = db.relationship('Atalho', backref='autor', lazy=True)
    # Itens relacionados ao usuário
    # Ela cria o atributo 'current_user.config'
    # ====================================================================
    config = db.relationship('Configuracoes', backref='usuario', uselist=False, cascade="all, delete-orphan")

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

    # e 'letra_relacionada' DEVE ser única em toda esta tabela."
    __table_args__ = (
        UniqueConstraint('usuario_id', 'letra_relacionada', name='_usuario_letra_uc'),
    )

    def __repr__(self):
        return f'<Item {self.nome}>'
    
class Configuracoes(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    # --- Configurações Oculares ---
    # Usamos os valores padrão do seu 'eye.py'
    eye_sensitivity = db.Column(db.Float, nullable=False, default=2.0)
    eye_deadzone = db.Column(db.Integer, nullable=False, default=20)
    
    # --- Configurações de Voz (Exemplo Futuro) ---
    voice_keyword = db.Column(db.String(50), nullable=False, default="bruna")
    voice_timeout = db.Column(db.Integer, nullable=False, default=5)

    # --- O Link de volta para o Usuário ---
    # 'unique=True' é o que garante que será Um-para-Um
    # (um usuário não pode ter duas linhas de configuração)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), unique=True, nullable=False)
    # =============================================================
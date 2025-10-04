# config.py
import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'q9$!7z@1Lw#e2^pR8sT0vB6xC3mN4jK5hG'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///site.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
# SeeMe

Sistema de acessibilidade desenvolvido para permitir que usuários controlem o computador utilizando visão computacional, rastreamento ocular, gestos, voz e reconhecimento de LIBRAS, reduzindo a dependência de teclado e mouse convencionais.

Projeto desenvolvido durante o **Samsung Innovation Campus 2025** em parceria com o **SENAI Vila Mariana**, com foco em inclusão digital e acessibilidade.

---

## Tecnologias

![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)
![OpenCV](https://img.shields.io/badge/OpenCV-5C3EE8?style=for-the-badge&logo=opencv&logoColor=white)
![MediaPipe](https://img.shields.io/badge/MediaPipe-FF6F00?style=for-the-badge)
![Flask](https://img.shields.io/badge/Flask-000000?style=for-the-badge&logo=flask)
![SQLite](https://img.shields.io/badge/SQLite-003B57?style=for-the-badge&logo=sqlite)
![PyAutoGUI](https://img.shields.io/badge/PyAutoGUI-2E8B57?style=for-the-badge)
![Computer Vision](https://img.shields.io/badge/Computer%20Vision-008080?style=for-the-badge)

---

## Sobre o Projeto

O **SeeMe** foi criado para oferecer formas alternativas de interação com computadores utilizando apenas uma webcam comum.

A plataforma integra múltiplos módulos de acessibilidade em uma única aplicação:

- Controle do cursor pelos olhos e movimentos faciais
- Comandos por gestos das mãos
- Reconhecimento de voz
- Sistema de atalhos personalizados
- Painel web para gerenciamento
- Reconhecimento de sinais em LIBRAS utilizando redes neurais convolucionais (CNN)

O objetivo é proporcionar maior autonomia para pessoas com deficiência, mobilidade reduzida ou dificuldades de interação com dispositivos tradicionais.

---

## Funcionalidades

### Rastreamento Ocular

- Controle do cursor em tempo real
- Suavização de movimento
- Deadzone configurável
- Filtro anti-tremor
- Calibração de sensibilidade
- Piscadas para clique

### Controle por Gestos

- Reconhecimento de dedos levantados
- Execução de atalhos personalizados
- Abertura de programas
- Abertura de sites
- Comandos automatizados

### Reconhecimento de Voz

- Captura de comandos falados
- Integração com ações do sistema
- Controle sem teclado

### Reconhecimento de LIBRAS

- CNN treinada para reconhecimento de sinais
- Processamento em tempo real
- Base para tradução assistida

### Painel Web

- Cadastro de usuários
- Login seguro
- Configuração de preferências
- Gerenciamento dos atalhos

---

## Arquitetura Simplificada

```text
Webcam
   │
   ▼
MediaPipe / OpenCV
   │
   ├── Eye Tracking
   ├── Hand Tracking
   └── Face Mesh
   │
   ▼
Controlador Principal
   │
   ├── PyAutoGUI
   ├── Voice Commands
   ├── Atalhos
   └── Interface Flask
   │
   ▼
Sistema Operacional
```

---

## Estrutura do Projeto

```text
multi-touch/
│
├── README.md
├── requirements.txt
├── requirementslab.txt
│
└── Aplicacao-Visual-Touch-SENAI-Vila-Mariana-main/
    │
    ├── run.py
    ├── config.py
    ├── voice.py
    │
    ├── seeme_app/
    │   ├── app.py
    │   ├── rotas.py
    │   ├── eye.py
    │   ├── exec_mao.py
    │   ├── control.py
    │   ├── modelos.py
    │   ├── templates/
    │   └── static/
    │
    ├── libras/
    │   ├── train.py
    │   ├── cnn/
    │   └── app_64x64x3.py
    │
    ├── models/
    ├── dataset/
    └── demo/
```

---

## Desafios Técnicos

Durante o desenvolvimento do projeto, alguns dos principais desafios foram:

- Rastreamento ocular utilizando apenas webcam convencional
- Redução de ruído e tremores no movimento do cursor
- Detecção confiável de piscadas para cliques
- Integração simultânea entre OpenCV, MediaPipe e Flask
- Processamento em tempo real sem hardware especializado
- Treinamento de CNN para reconhecimento de sinais em LIBRAS
- Execução de ações do sistema operacional de forma segura

---

## Resultados

- Mais de 100 commits no desenvolvimento
- Múltiplos módulos integrados em uma única plataforma
- Controle em tempo real utilizando visão computacional
- Interface web para gerenciamento do sistema
- Projeto apresentado durante o Samsung Innovation Campus 2025

---

## Melhorias Futuras

- Aplicativo desktop dedicado
- Instalador para Windows
- Sistema avançado de calibração ocular
- Tradução completa de LIBRAS
- Dashboard com estatísticas de uso
- Treinamento de modelos mais robustos
- Arquitetura modular baseada em serviços
- Documentação técnica completa

---

## Autor

**Vitor Gabriel**

Desenvolvedor focado em Python, Inteligência Artificial, Visão Computacional e Desenvolvimento de Sistemas.

GitHub:
https://github.com/VitorGabrielFS

---

## Licença

Este projeto foi desenvolvido para fins educacionais e de pesquisa em acessibilidade digital.
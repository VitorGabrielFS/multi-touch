from flask import Flask, render_template
import threading
import cv2
import mediapipe as mp
import pyautogui
from voice import reconhecimento_de_voz
import os
import speech_recognition as sr
from collections import deque


# configuração
screen_w, screen_h = pyautogui.size()
pyautogui.FAILSAFE = False

# variáveis globais de controle
tracking = False
cam = None

# Sensibilidade/controle finos (padrões razoáveis)
# sensitivity: multiplicador aplicado ao movimento detectado (1.0 = padrão)
# smoothing: alpha para EMA (0.0 -> sem suavização, 0.9 -> muito suave)
# deadzone: pixels a partir do centro onde pequenos movimentos são ignorados
sensitivity = 2
smoothing_alpha = 0.6
deadzone = 20

def set_tracking(value):
    global tracking
    tracking = value

def set_sensitivity(value: float):
    """Define a sensibilidade (multiplicador). Valores >1 amplificam o movimento."""
    global sensitivity
    try:
        sensitivity = float(value)
    except Exception:
        pass

def set_smoothing(alpha: float):
    """Define o alpha da suavização exponencial (0.0 - sem suavização, 0.0<alpha<1.0)."""
    global smoothing_alpha
    if alpha is None:
        return
    try:
        a = float(alpha)
        # limitar entre 0 e 0.99
        smoothing_alpha = max(0.0, min(0.99, a))
    except Exception:
        pass

def set_deadzone(px: int):
    """Define a zona morta em pixels ao redor do centro onde movimentos pequenos são ignorados."""
    global deadzone
    try:
        deadzone = int(px)
    except Exception:
        pass

def eye_tracking():
    global tracking, cam, sensitivity, smoothing_alpha, deadzone

    with mp.solutions.face_mesh.FaceMesh(refine_landmarks=True, static_image_mode=False) as face_mesh:
        cam = cv2.VideoCapture(0)

        base_nose_x, base_nose_y = None, None
        # virtual area que mapeia para a tela; quanto menor, maior o ganho por padrão
        virtual_width = screen_w * 0.2
        virtual_height = screen_h * 0.2

        # variáveis para suavização (EMA)
        smoothed_x = None
        smoothed_y = None

        center_x = screen_w / 2
        center_y = screen_h / 2

        while tracking:
            ret, frame = cam.read()
            if not ret:
                break

            frame = cv2.flip(frame, 1)
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            output = face_mesh.process(rgb_frame)
            landmark_points = output.multi_face_landmarks

            if landmark_points:
                landmarks = landmark_points[0].landmark

                # usar o ponto do nariz como referência (pode-se trocar para outros pontos)
                nose = landmarks[1]
                nose_x = int(nose.x * screen_w)
                nose_y = int(nose.y * screen_h)

                if base_nose_x is None and base_nose_y is None:
                    base_nose_x = nose_x
                    base_nose_y = nose_y

                # cálculo relativo ao ponto inicial
                relative_x = nose_x - base_nose_x
                relative_y = nose_y - base_nose_y

                # aplica sensibilidade: multiplicador sobre o deslocamento relativo
                adjusted_x = relative_x * sensitivity
                adjusted_y = relative_y * sensitivity

                # mapeamento para a tela real (mantemos virtual_* para normalização)
                screen_x_raw = (adjusted_x / virtual_width) * screen_w + center_x
                screen_y_raw = (adjusted_y / virtual_height) * screen_h + center_y

                # restrição para não sair da tela
                screen_x_raw = max(0, min(screen_w - 1, screen_x_raw))
                screen_y_raw = max(0, min(screen_h - 1, screen_y_raw))

                # aplica zona morta em relação ao centro (evita jitter quando o usuário está em posição neutra)
                dx = screen_x_raw - center_x
                dy = screen_y_raw - center_y
                if abs(dx) < deadzone:
                    screen_x_raw = center_x
                if abs(dy) < deadzone:
                    screen_y_raw = center_y

                # suavização exponencial (EMA)
                if smoothed_x is None or smoothed_y is None:
                    smoothed_x = screen_x_raw
                    smoothed_y = screen_y_raw
                else:
                    # smoothing_alpha próximo de 1 -> mais suave (mais peso no histórico)
                    smoothed_x = (smoothing_alpha * smoothed_x) + ((1 - smoothing_alpha) * screen_x_raw)
                    smoothed_y = (smoothing_alpha * smoothed_y) + ((1 - smoothing_alpha) * screen_y_raw)

                # mover o cursor para a posição suavizada
                pyautogui.moveTo(smoothed_x, smoothed_y, duration=0)

            cv2.imshow('Nose Controlled Cursor', frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

        cam.release()
        cv2.destroyAllWindows()

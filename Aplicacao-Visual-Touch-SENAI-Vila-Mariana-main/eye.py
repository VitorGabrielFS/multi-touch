from flask import Flask, render_template
import threading
import cv2
import mediapipe as mp
import pyautogui
from voice import reconhecimento_de_voz
import os
import speech_recognition as sr
from collections import deque


# Configurações iniciais
screen_w, screen_h = pyautogui.size()
pyautogui.FAILSAFE = False

# Variáveis globais
tracking = False
cam = None

def set_tracking(value):
    global tracking
    tracking = value

def eye_tracking():
    global tracking, cam

    with mp.solutions.face_mesh.FaceMesh(refine_landmarks=True, static_image_mode=False) as face_mesh:
        cam = cv2.VideoCapture(0)

        base_nose_x, base_nose_y = None, None
        virtual_width = screen_w * 0.2
        virtual_height = screen_h * 0.2

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

                # Pega o nariz
                nose = landmarks[1]  # (você pode testar com 4 também se quiser)
                nose_x = int(nose.x * screen_w)
                nose_y = int(nose.y * screen_h)

                if base_nose_x is None and base_nose_y is None:
                    # Primeira vez: define a base do nariz
                    base_nose_x = nose_x
                    base_nose_y = nose_y

                # Cálculo relativo ao ponto inicial
                relative_x = nose_x - base_nose_x
                relative_y = nose_y - base_nose_y

                # Mapeamento para a tela real
                screen_x = (relative_x / virtual_width) * screen_w + (screen_w / 2)
                screen_y = (relative_y / virtual_height) * screen_h + (screen_h / 2)

                # Restringe para não sair da tela
                screen_x = max(0, min(screen_w - 1, screen_x))
                screen_y = max(0, min(screen_h - 1, screen_y))

                pyautogui.moveTo(screen_x, screen_y, duration=0)

            cv2.imshow('Nose Controlled Cursor', frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

        cam.release()
        cv2.destroyAllWindows()

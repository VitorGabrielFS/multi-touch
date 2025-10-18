import cv2
import mediapipe as mp
import pyautogui
import time
import math
from .control import resource_manager

# --- CONFIGURAÇÕES GLOBAIS ---
screen_w, screen_h = pyautogui.size()
pyautogui.FAILSAFE = False

tracking = False  # Controlado pelo Flask
cam = None  # Acesso global pra liberar no stopp

# Sensibilidade e suavização
sensitivity = 2.0
smoothing_alpha = 0.6
deadzone = 20
FPS_TARGET = 30.0
FRAME_INTERVAL = 1.0 / FPS_TARGET
MOUSE_MOVE_DURATION = 0.005

# Piscar e cliques
BLINK_THRESHOLD = 0.20
OPEN_THRESHOLD = 0.30
DRAG_HOLD_TIME = 0.40
ACTION_DEBOUNCE_TIME = 0.40

# Estados
is_dragging = False
drag_start_time = None
last_action_time = 0.0
left_eye_state = 'READY'
right_eye_state = 'READY'

# Pontos dos olhos
RIGHT_EYE_POINTS = [386, 374, 362, 263]
LEFT_EYE_POINTS = [159, 145, 133, 33]

# --- Funções auxiliares ---
def set_tracking(state: bool):
    global tracking
    tracking = state


def euclid_dist(p1, p2):
    return math.sqrt((p1.x - p2.x) ** 2 + (p1.y - p2.y) ** 2)


def calculate_ear(landmarks, points_indices):
    p_vert_sup = landmarks[points_indices[0]]
    p_vert_inf = landmarks[points_indices[1]]
    p_horiz_ext = landmarks[points_indices[2]]
    p_horiz_int = landmarks[points_indices[3]]

    dist_vert = euclid_dist(p_vert_sup, p_vert_inf)
    dist_horiz = euclid_dist(p_horiz_ext, p_horiz_int)
    return dist_vert / (dist_horiz + 1e-6)


# --- Função principal ---
def eye_tracking():
    global cam, tracking, is_dragging, drag_start_time, last_action_time
    global left_eye_state, right_eye_state

    mp_face = mp.solutions.face_mesh
    with mp_face.FaceMesh(max_num_faces=1, refine_landmarks=True) as face_mesh:
        # Usa a câmera compartilhada do ResourceManager
        cam = resource_manager.get_shared_camera()

        base_nose_x = base_nose_y = None
        smoothed_x = smoothed_y = None
        center_x, center_y = screen_w / 2, screen_h / 2
        virtual_width = screen_w * 0.2
        virtual_height = screen_h * 0.2

        while tracking:
            ret, frame = cam.read()
            if not ret:
                break

            frame = cv2.flip(frame, 1)
            frame_h, frame_w, _ = frame.shape
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = face_mesh.process(rgb)

            if not results.multi_face_landmarks:
                cv2.imshow("Controle por Visão", frame)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    tracking = False
                    break
                continue

            landmarks = results.multi_face_landmarks[0].landmark

            # === Movimento ===
            nose = landmarks[1]
            nose_x, nose_y = int(nose.x * frame_w), int(nose.y * frame_h)
            if base_nose_x is None:
                base_nose_x, base_nose_y = nose_x, nose_y

            rel_x = nose_x - base_nose_x
            rel_y = nose_y - base_nose_y
            adj_x = rel_x * sensitivity
            adj_y = rel_y * sensitivity
            screen_x = (adj_x / virtual_width) * screen_w + center_x
            screen_y = (adj_y / virtual_height) * screen_h + center_y

            dx = screen_x - center_x
            dy = screen_y - center_y
            if abs(dx) < deadzone:
                screen_x = center_x
            if abs(dy) < deadzone:
                screen_y = center_y

            if smoothed_x is None:
                smoothed_x, smoothed_y = screen_x, screen_y
            else:
                smoothed_x = (smoothing_alpha * smoothed_x) + ((1 - smoothing_alpha) * screen_x)
                smoothed_y = (smoothing_alpha * smoothed_y) + ((1 - smoothing_alpha) * screen_y)

            pyautogui.moveTo(smoothed_x, smoothed_y, duration=MOUSE_MOVE_DURATION)

            # === Cliques ===
            ear_left = calculate_ear(landmarks, LEFT_EYE_POINTS)
            ear_right = calculate_ear(landmarks, RIGHT_EYE_POINTS)
            current_time = time.time()

            # Clique esquerdo
            global left_eye_state, right_eye_state, drag_start_time, is_dragging, last_action_time

            if left_eye_state == 'READY' and ear_left < BLINK_THRESHOLD:
                left_eye_state = 'CLOSED'
                drag_start_time = current_time
            elif left_eye_state == 'CLOSED' and ear_left > OPEN_THRESHOLD:
                if is_dragging:
                    pyautogui.mouseUp(button='left')
                    is_dragging = False
                    print("ARRASTO FINALIZADO")
                elif drag_start_time and (current_time - drag_start_time) < DRAG_HOLD_TIME:
                    if current_time - last_action_time > ACTION_DEBOUNCE_TIME:
                        pyautogui.click(button='left')
                        last_action_time = current_time
                        print("CLIQUE ESQUERDO")
                left_eye_state = 'READY'
                drag_start_time = None

            if left_eye_state == 'CLOSED' and not is_dragging:
                if drag_start_time and (current_time - drag_start_time) >= DRAG_HOLD_TIME:
                    if current_time - last_action_time > ACTION_DEBOUNCE_TIME:
                        pyautogui.mouseDown(button='left')
                        is_dragging = True
                        last_action_time = current_time
                        print("ARRASTO INICIADO")

            # Clique direito
            if right_eye_state == 'READY' and ear_right < BLINK_THRESHOLD:
                right_eye_state = 'CLOSED'
            elif right_eye_state == 'CLOSED' and ear_right > OPEN_THRESHOLD:
                if current_time - last_action_time > ACTION_DEBOUNCE_TIME:
                    pyautogui.click(button='right')
                    last_action_time = current_time
                    print("CLIQUE DIREITO")
                right_eye_state = 'READY'

            cv2.imshow("Controle por Visão", frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                tracking = False
                break

        # Não libera a câmera aqui, deixa o ResourceManager gerenciar
        cv2.destroyAllWindows()
        tracking = False
        print("Rastreamento ocular finalizado.")

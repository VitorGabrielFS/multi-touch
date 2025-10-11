import cv2
import mediapipe as mp
import pyautogui
import time
import math
# from collections import deque # Não é mais necessário

# --- CONFIGURAÇÃO E VARIÁVEIS GLOBAIS ---
screen_w, screen_h = pyautogui.size()
pyautogui.FAILSAFE = False # Desativa o failsafe

# VARIÁVEIS DE CONTROLE DO CURSOR
sensitivity = 2.0
smoothing_alpha = 0.6 # Alpha mais alto (ex: 0.8) = mais suave, mas mais atraso
deadzone = 20
tracking = True

# VARIÁVEIS DE CONTROLE DE CLIQUE/ARRASTO (mantidas)
BLINK_THRESHOLD = 0.20 
OPEN_THRESHOLD = 0.30 
DRAG_HOLD_TIME = 0.40
ACTION_DEBOUNCE_TIME = 0.40 

# Estados de controle
is_dragging = False
drag_start_time = None
last_action_time = 0.0
left_eye_state = 'READY' 
right_eye_state = 'READY' 

# Variáveis de Otimização de Performance
last_frame_time = time.time()
FPS_TARGET = 30.0 # Define a taxa de FPS desejada para o rastreamento (limita a câmera)
FRAME_INTERVAL = 1.0 / FPS_TARGET
# Parâmetro de movimento do PyAutoGUI: Reduza o 'duration' para 0 (instantâneo) ou um valor muito pequeno.
MOUSE_MOVE_DURATION = 0.005 # Tempo em segundos para o movimento. Um valor pequeno pode suavizar o movimento sem EMA.

# Constantes dos landmarks dos olhos (mantidas)
RIGHT_EYE_POINTS = [386, 374, 362, 263]
LEFT_EYE_POINTS = [159, 145, 133, 33] 

# --- FUNÇÕES AUXILIARES DE CLIQUE ---
def euclid_dist(p1, p2):
    return math.sqrt((p1.x - p2.x)**2 + (p1.y - p2.y)**2)

def calculate_ear(landmarks, points_indices):
    p_vert_sup = landmarks[points_indices[0]] 
    p_vert_inf = landmarks[points_indices[1]] 
    p_horiz_ext = landmarks[points_indices[2]] 
    p_horiz_int = landmarks[points_indices[3]]

    dist_vert = euclid_dist(p_vert_sup, p_vert_inf)
    dist_horiz = euclid_dist(p_horiz_ext, p_horiz_int)
    
    ear = dist_vert / (dist_horiz + 1e-6)
    return ear

# --- FUNÇÃO PRINCIPAL DE RASTREAMENTO ---

def eye_tracking():
    global tracking, sensitivity, smoothing_alpha, deadzone
    global is_dragging, drag_start_time, last_action_time
    global left_eye_state, right_eye_state, MOUSE_MOVE_DURATION
    global last_frame_time, FRAME_INTERVAL

    # Use max_num_faces=1 para evitar overhead e garantir suavização
    with mp.solutions.face_mesh.FaceMesh(
        max_num_faces=1, 
        refine_landmarks=True, 
        static_image_mode=False) as face_mesh:
        
        # Tenta configurar o FPS da câmera (pode não ser suportado por todas as câmeras)
        cam = cv2.VideoCapture(0)
        # cam.set(cv2.CAP_PROP_FPS, FPS_TARGET) # Tenta forçar o FPS da câmera
        
        base_nose_x, base_nose_y = None, None
        virtual_width = screen_w * 0.2
        virtual_height = screen_h * 0.2
        smoothed_x = None
        smoothed_y = None
        center_x = screen_w / 2
        center_y = screen_h / 2
        
        while tracking:
            # --- Controle de FPS (Aplica um limite para o loop principal) ---
            time_to_wait = FRAME_INTERVAL - (time.time() - last_frame_time)
            if time_to_wait > 0:
                time.sleep(time_to_wait)
            
            last_frame_time = time.time()
            current_time = last_frame_time

            ret, frame = cam.read()
            if not ret:
                break

            # Processamento do Frame
            frame = cv2.flip(frame, 1)
            frame_h, frame_w, _ = frame.shape
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            output = face_mesh.process(rgb_frame)
            landmark_points = output.multi_face_landmarks

            if landmark_points:
                landmarks = landmark_points[0].landmark

                # --- 1. RASTREAMENTO DO CURSOR (Nariz) ---
                nose = landmarks[1]
                
                nose_x = int(nose.x * frame_w)
                nose_y = int(nose.y * frame_h)

                if base_nose_x is None:
                    base_nose_x = nose_x
                    base_nose_y = nose_y

                relative_x = nose_x - base_nose_x
                relative_y = nose_y - base_nose_y

                adjusted_x = relative_x * sensitivity
                adjusted_y = relative_y * sensitivity
                
                # Posição Mapeada: (Essa é a posição final do mouse, antes da suavização)
                screen_x_raw = (adjusted_x / virtual_width) * screen_w + center_x
                screen_y_raw = (adjusted_y / virtual_height) * screen_h + center_y

                screen_x_raw = max(0, min(screen_w - 1, screen_x_raw))
                screen_y_raw = max(0, min(screen_h - 1, screen_y_raw))
                
                dx = screen_x_raw - center_x
                dy = screen_y_raw - center_y
                if abs(dx) < deadzone:
                    screen_x_raw = center_x
                if abs(dy) < deadzone:
                    screen_y_raw = center_y

                # Suavização Aprimorada (EMA)
                if smoothed_x is None:
                    smoothed_x, smoothed_y = screen_x_raw, screen_y_raw
                else:
                    # Usa o 'smoothing_alpha' (ex: 0.6) para manter a fluidez
                    smoothed_x = (smoothing_alpha * smoothed_x) + ((1 - smoothing_alpha) * screen_x_raw)
                    smoothed_y = (smoothing_alpha * smoothed_y) + ((1 - smoothing_alpha) * screen_y_raw)

                # MOVIMENTO OTIMIZADO: Usa uma duração mínima para que o PyAutoGUI
                # faça a interpolação entre a posição atual e a nova,
                # mesmo se o seu loop de MediaPipe estiver lento.
                # Se duration=0, o movimento é instantâneo (teleporte).
                # Um valor pequeno (0.005) permite uma "mini-suavização" do pyautogui.
                pyautogui.moveTo(smoothed_x, smoothed_y, duration=MOUSE_MOVE_DURATION)
                
                # --- 2. CLIQUE E ARRASTO (Olhos - Mantido Inalterado) ---
                
                ear_left = calculate_ear(landmarks, LEFT_EYE_POINTS)
                ear_right = calculate_ear(landmarks, RIGHT_EYE_POINTS)
                
                cv2.putText(frame, f"FPS: {1.0/(time.time() - last_frame_time):.1f}", (50, frame_h - 50), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
                cv2.putText(frame, f"Esq: {ear_left:.2f}", (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                cv2.putText(frame, f"Dir: {ear_right:.2f}", (50, 100), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)


                # =========================
                #  LÓGICA DE CLIQUE (mantida)
                # =========================

                # Olho Esquerdo (Clique / Arrastar)
                if left_eye_state == 'READY' and ear_left < BLINK_THRESHOLD:
                    left_eye_state = 'CLOSED'
                    drag_start_time = current_time 
                elif left_eye_state == 'CLOSED' and ear_left > OPEN_THRESHOLD:
                    # Verifica se foi um Arrastar
                    if is_dragging:
                        pyautogui.mouseUp(button='left')
                        is_dragging = False
                        print("ARRANQUE ESQUERDO FINALIZADO")
                    
                    # Verifica se foi um Clique Rápido
                    elif drag_start_time and (current_time - drag_start_time) < DRAG_HOLD_TIME:
                        if current_time - last_action_time > ACTION_DEBOUNCE_TIME:
                            pyautogui.click(button='left')
                            last_action_time = current_time
                            print("CLIQUE ESQUERDO")
                            
                    left_eye_state = 'READY'
                    drag_start_time = None
                
                # Iniciar Arrastar (Hold)
                if left_eye_state == 'CLOSED' and not is_dragging:
                    if drag_start_time and current_time - drag_start_time >= DRAG_HOLD_TIME:
                        if current_time - last_action_time > ACTION_DEBOUNCE_TIME:
                            pyautogui.mouseDown(button='left')
                            is_dragging = True
                            last_action_time = current_time
                            print("ARRANQUE ESQUERDO INICIADO")

                # Olho Direito (Clique Direito)
                if right_eye_state == 'READY' and ear_right < BLINK_THRESHOLD:
                    right_eye_state = 'CLOSED'
                elif right_eye_state == 'CLOSED' and ear_right > OPEN_THRESHOLD:
                    if current_time - last_action_time > ACTION_DEBOUNCE_TIME:
                        pyautogui.click(button='right')
                        last_action_time = current_time
                        print("CLIQUE DIREITO")
                    right_eye_state = 'READY'
            
            # Exibição do Frame
            cv2.imshow('Controle por Visao', frame)
            
            # Condição para parar (pressione 'q')
            if cv2.waitKey(1) & 0xFF == ord('q'):
                tracking = False
                break

        # Limpeza
        cam.release()
        cv2.destroyAllWindows()


if __name__ == '__main__':
    # ... (Mensagens de inicialização - omitidas) ...
    try:
        eye_tracking()
    except Exception as e:
        print(f"Ocorreu um erro: {e}")
    
    print("Rastreamento finalizado.")
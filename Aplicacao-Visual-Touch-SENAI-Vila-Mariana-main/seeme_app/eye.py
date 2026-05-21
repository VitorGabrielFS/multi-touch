import cv2
import mediapipe as mp
import pyautogui
import time
import math
import ctypes
from collections import deque
from ctypes import wintypes
from .control import resource_manager

# ─────────────────────────────────────────────
#  OTIMIZAÇÕES GLOBAIS
# ─────────────────────────────────────────────
screen_w, screen_h = pyautogui.size()
pyautogui.FAILSAFE = False
pyautogui.PAUSE = 0

# Windows API para movimento raw (sem overhead do pyautogui)
user32 = ctypes.windll.user32
SetCursorPos = user32.SetCursorPos
SetCursorPos.argtypes = [wintypes.INT, wintypes.INT]
SetCursorPos.restype = wintypes.BOOL

# ─────────────────────────────────────────────
#  CONFIGURAÇÕES DE TIMING / FPS
# ─────────────────────────────────────────────
FPS_TARGET        = 120.0
FRAME_INTERVAL    = 1.0 / FPS_TARGET

# ─────────────────────────────────────────────
#  CONFIGURAÇÕES DE PISCADA
#  A lógica de filtragem funciona assim:
#    - olho fecha  → registra t_close
#    - olho abre   → calcula duração = t_open - t_close
#    - se duração < MIN_BLINK_DURATION  → piscada NATURAL, ignorada
#    - se duração ≤ MAX_CLICK_DURATION  → piscada INTENCIONAL → clique
#    - se duração > MAX_CLICK_DURATION  → era drag, executa mouseUp
#  Valores em segundos:
# ─────────────────────────────────────────────
BLINK_THRESHOLD         = 0.18   # EAR abaixo → olho fechado
OPEN_THRESHOLD          = 0.30   # EAR acima  → olho aberto
MIN_BLINK_DURATION      = 0.10    #< 100 ms   = piscada natural → ignorar
MAX_CLICK_DURATION      = 0.45   # 80–450 ms = clique intencional
DRAG_HOLD_TIME          = 0.45   # ≥ 450 ms  = drag (mouseDown)
ACTION_DEBOUNCE_TIME    = 0.25   # tempo mínimo entre ações consecutivas

# ─────────────────────────────────────────────
#  CONFIGURAÇÕES DE SUAVIZAÇÃO / ANTI-TREMOR
# ─────────────────────────────────────────────
VELOCITY_SMOOTH_FACTOR  = 0.6    # peso do histórico na suavização adaptativa
JITTER_THRESHOLD        = 4.0    # px — micro-movimentos abaixo disso são suprimidos
MOVING_AVG_WINDOW       = 5      # janela do filtro de média móvel (frames)

# ─────────────────────────────────────────────
#  ÍNDICES DOS LANDMARKS (MediaPipe FaceMesh)
# ─────────────────────────────────────────────
RIGHT_EYE_POINTS = [386, 374, 362, 263]
LEFT_EYE_POINTS  = [159, 145, 133, 33]

# ─────────────────────────────────────────────
#  ESTADO GLOBAL
# ─────────────────────────────────────────────
tracking         = False
cam              = None
is_dragging      = False
last_action_time = 0.0
left_eye_state   = 'READY'
right_eye_state  = 'READY'

# Configurações ajustáveis pelo usuário
sensitivity      = 2.0
smoothing_alpha  = 0.75
deadzone         = 15


# ─────────────────────────────────────────────
#  UTILITÁRIOS MATEMÁTICOS
# ─────────────────────────────────────────────
def euclid_dist(p1, p2) -> float:
    """Distância euclidiana entre dois landmarks MediaPipe."""
    dx = p1.x - p2.x
    dy = p1.y - p2.y
    return math.sqrt(dx * dx + dy * dy)


def calculate_ear(landmarks, pts) -> float:
    """
    Eye Aspect Ratio: razão entre abertura vertical e largura horizontal.
    Quanto menor, mais fechado o olho.
    """
    p1, p2, p3, p4 = landmarks[pts[0]], landmarks[pts[1]], \
                     landmarks[pts[2]], landmarks[pts[3]]
    return euclid_dist(p1, p2) / (euclid_dist(p3, p4) + 1e-6)


def move_mouse_raw(x: float, y: float):
    """Move o cursor diretamente via WinAPI — sem overhead do pyautogui."""
    SetCursorPos(int(x), int(y))


# ─────────────────────────────────────────────
#  API PÚBLICA
# ─────────────────────────────────────────────
def set_tracking(state: bool):
    global tracking
    tracking = state


# ─────────────────────────────────────────────
#  CLASSE: FILTRO DE CURSOR (ANTI-TREMOR)
# ─────────────────────────────────────────────
class CursorFilter:
    """
    Combina três técnicas para eliminar jitter mantendo responsividade:

    1. Média móvel (janela deslizante)  — suaviza oscilações de alta frequência
    2. EMA adaptativa baseada em velocidade — mais suave quando parado,
       mais responsivo quando há movimento rápido intencional
    3. Threshold de micro-movimento (jitter gate) — suprime deslocamentos
       abaixo de JITTER_THRESHOLD pixels

    Resultado: cursor "trackpad premium" — estável em repouso, fluido em movimento.
    """

    def __init__(self, init_x: float, init_y: float):
        self.smoothed_x = init_x
        self.smoothed_y = init_y
        self.prev_raw_x = init_x
        self.prev_raw_y = init_y

        # Buffers da média móvel
        self._buf_x: deque = deque([init_x] * MOVING_AVG_WINDOW,
                                   maxlen=MOVING_AVG_WINDOW)
        self._buf_y: deque = deque([init_y] * MOVING_AVG_WINDOW,
                                   maxlen=MOVING_AVG_WINDOW)

        self._inv_window = 1.0 / MOVING_AVG_WINDOW  # evita divisão no loop

    def update(self, target_x: float, target_y: float) -> tuple[float, float]:
        # ── 1. Jitter gate: ignora micro-movimentos ──────────────────────────
        dx = target_x - self.prev_raw_x
        dy = target_y - self.prev_raw_y
        dist = math.sqrt(dx * dx + dy * dy)

        if dist < JITTER_THRESHOLD:
            # Movimento muito pequeno — mantém posição anterior sem alimentar
            # os filtros, evitando "deriva por ruído"
            target_x = self.prev_raw_x
            target_y = self.prev_raw_y
        else:
            self.prev_raw_x = target_x
            self.prev_raw_y = target_y

        # ── 2. Média móvel (suavização de alta frequência) ───────────────────
        self._buf_x.append(target_x)
        self._buf_y.append(target_y)
        avg_x = sum(self._buf_x) * self._inv_window
        avg_y = sum(self._buf_y) * self._inv_window

        # ── 3. EMA adaptativa baseada em velocidade ──────────────────────────
        #   velocidade alta  → alpha mais baixo (mais suavização)
        #   velocidade baixa → alpha mais alto  (mais responsivo)
        #   Isso elimina o trade-off clássico entre lag e estabilidade.
        velocity = dist  # px por frame
        adaptive_alpha = smoothing_alpha * (1.0 - VELOCITY_SMOOTH_FACTOR) \
                       + (1.0 - min(velocity / 80.0, 1.0)) \
                       * smoothing_alpha * VELOCITY_SMOOTH_FACTOR

        self.smoothed_x = adaptive_alpha * self.smoothed_x + (1.0 - adaptive_alpha) * avg_x
        self.smoothed_y = adaptive_alpha * self.smoothed_y + (1.0 - adaptive_alpha) * avg_y

        return self.smoothed_x, self.smoothed_y


# ─────────────────────────────────────────────
#  CLASSE: DETECTOR DE PISCADA (ANTI-FALSO POSITIVO)
# ─────────────────────────────────────────────
class BlinkDetector:
    """
    Máquina de estados para detectar piscadas intencionais vs naturais.

    Estados:
        READY   → esperando fechamento
        CLOSED  → olho fechado, medindo duração
        BLOCKED → debounce pós-ação (ignora reaberturas espúrias)

    Filtragem por duração:
        < MIN_BLINK_DURATION      → piscada natural, descartada silenciosamente
        MIN ≤ duração ≤ MAX_CLICK → clique intencional
        > MAX_CLICK (DRAG_HOLD)   → inicia drag enquanto fechado
    """

    def __init__(self, side: str):
        self.side   = side            # 'left' ou 'right' — apenas para debug
        self.state  = 'READY'
        self.t_close: float | None = None   # timestamp do fechamento

    def process(self, ear: float, current_time: float,
                is_dragging_ref: list) -> str:
        """
        Processa o EAR atual e retorna a ação detectada:
            'click'      — clique simples
            'drag_start' — início de drag (mouseDown)
            'drag_end'   — fim de drag (mouseUp)
            'none'       — nenhuma ação
        """
        action = 'none'

        if self.state == 'READY':
            if ear < BLINK_THRESHOLD:
                # Olho acabou de fechar
                self.state   = 'CLOSED'
                self.t_close = current_time

        elif self.state == 'CLOSED':
            duration = current_time - self.t_close  # segundos com olho fechado

            if ear > OPEN_THRESHOLD:
                # Olho abriu — avalia duração para decidir ação
                if duration < MIN_BLINK_DURATION:
                    # ──────────────────────────────────────────────────────────
                    # ANTI-FALSO POSITIVO: piscada natural (< 80 ms)
                    # Simplesmente descartada, sem gerar nenhuma ação.
                    # ──────────────────────────────────────────────────────────
                    pass

                elif is_dragging_ref[0]:
                    # Estava em drag → libera o botão
                    action = 'drag_end'
                    is_dragging_ref[0] = False

                elif duration <= MAX_CLICK_DURATION:
                    # Piscada intencional dentro da janela de clique
                    action = 'click'

                # Se duration > MAX_CLICK_DURATION mas não estava em drag,
                # é um segurar sem arrastar — apenas ignora na abertura.

                self.state   = 'READY'
                self.t_close = None

            elif not is_dragging_ref[0] and duration >= DRAG_HOLD_TIME:
                # Olho ainda fechado por tempo suficiente → inicia drag
                action = 'drag_start'
                is_dragging_ref[0] = True

        return action


# ─────────────────────────────────────────────
#  LOOP PRINCIPAL
# ─────────────────────────────────────────────
def eye_tracking(active_event, configuracoes_usuario):
    global cam, tracking, is_dragging, last_action_time
    global sensitivity, deadzone, smoothing_alpha

    # ── Carrega config do usuário ────────────────────────────────────────────
    sensitivity     = getattr(configuracoes_usuario, 'eye_sensitivity',  2.0)
    deadzone        = getattr(configuracoes_usuario, 'eye_deadzone',      15)
    smoothing_alpha = getattr(configuracoes_usuario, 'smoothing_alpha',   0.75)

    print(f"Eye Tracking v2 | Sens={sensitivity} | DZ={deadzone} | Alpha={smoothing_alpha}")

    # ── MediaPipe ────────────────────────────────────────────────────────────
    mp_face   = mp.solutions.face_mesh
    face_mesh = mp_face.FaceMesh(
        max_num_faces         = 1,
        refine_landmarks      = True,
        min_detection_confidence = 0.7,
        min_tracking_confidence  = 0.7,
    )

    cam = resource_manager.get_shared_camera()

    # ── Estado de posição ────────────────────────────────────────────────────
    center_x      = screen_w / 2.0
    center_y      = screen_h / 2.0
    virtual_width  = screen_w * 0.25
    virtual_height = screen_h * 0.25
    base_nose_x   = 0.0
    base_nose_y   = 0.0

    # ── Filtro de cursor ─────────────────────────────────────────────────────
    cursor = CursorFilter(center_x, center_y)

    # ── Detectores de piscada ────────────────────────────────────────────────
    # is_dragging precisa ser mutável por referência dentro do BlinkDetector
    is_dragging_ref = [False]
    left_detector   = BlinkDetector('left')
    right_detector  = BlinkDetector('right')

    # ── Calibração: captura posição neutra do nariz ──────────────────────────
    ret, frame = cam.read()
    if ret:
        frame = cv2.flip(frame, 1)
        rgb   = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        res   = face_mesh.process(rgb)
        if res.multi_face_landmarks:
            lm = res.multi_face_landmarks[0].landmark
            h, w = frame.shape[:2]
            base_nose_x = lm[1].x * w
            base_nose_y = lm[1].y * h

    # ── Cache de constantes usadas no loop ───────────────────────────────────
    # Evita re-lookup de atributos globais a cada frame
    _sensitivity     = sensitivity
    _deadzone        = deadzone
    _virtual_width   = virtual_width
    _virtual_height  = virtual_height
    _center_x        = center_x
    _center_y        = center_y
    _screen_w_m1     = float(screen_w - 1)
    _screen_h_m1     = float(screen_h - 1)

    while tracking:
        frame_start = time.perf_counter()

        ret, frame = cam.read()
        if not ret:
            break

        # ── Pré-processamento de frame ───────────────────────────────────────
        frame        = cv2.flip(frame, 1)
        frame_h, frame_w = frame.shape[:2]
        rgb          = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results      = face_mesh.process(rgb)

        if not results.multi_face_landmarks:
            # Sem rosto detectado — mantém posição atual, não congela
            sx, sy = cursor.smoothed_x, cursor.smoothed_y
            move_mouse_raw(sx, sy)
            time.sleep(max(0.0, FRAME_INTERVAL - (time.perf_counter() - frame_start)))
            continue

        landmarks    = results.multi_face_landmarks[0].landmark
        current_time = time.time()

        # ── MOVIMENTO: nariz como joystick ───────────────────────────────────
        nose   = landmarks[1]
        nose_x = nose.x * frame_w
        nose_y = nose.y * frame_h

        # Deslocamento relativo à posição neutra calibrada
        rel_x = (nose_x - base_nose_x) * _sensitivity
        rel_y = (nose_y - base_nose_y) * _sensitivity

        # Mapeia para coordenadas de tela
        raw_x = (rel_x / _virtual_width)  * screen_w + _center_x
        raw_y = (rel_y / _virtual_height) * screen_h + _center_y

        # Deadzone: ignora movimentos mínimos em torno do centro
        if abs(raw_x - _center_x) < _deadzone:
            raw_x = _center_x
        if abs(raw_y - _center_y) < _deadzone:
            raw_y = _center_y

        # Filtro anti-tremor (média móvel + EMA adaptativa + jitter gate)
        smooth_x, smooth_y = cursor.update(raw_x, raw_y)

        # Clamp e movimento
        cx = max(0.0, min(smooth_x, _screen_w_m1))
        cy = max(0.0, min(smooth_y, _screen_h_m1))
        move_mouse_raw(cx, cy)

        # ── CLIQUES: detecção de piscada ─────────────────────────────────────
        # Calcula EAR apenas uma vez por olho por frame
        ear_left  = calculate_ear(landmarks, LEFT_EYE_POINTS)
        ear_right = calculate_ear(landmarks, RIGHT_EYE_POINTS)

        # Olho esquerdo → clique/drag esquerdo
        action_left = left_detector.process(ear_left, current_time, is_dragging_ref)
        if action_left != 'none' and (current_time - last_action_time > ACTION_DEBOUNCE_TIME):
            if action_left == 'click':
                pyautogui.click(button='left')
                last_action_time = current_time
            elif action_left == 'drag_start':
                pyautogui.mouseDown(button='left')
                last_action_time = current_time
            elif action_left == 'drag_end':
                pyautogui.mouseUp(button='left')
                last_action_time = current_time

        # Olho direito → clique direito
        action_right = right_detector.process(ear_right, current_time, is_dragging_ref)
        if action_right == 'click' and (current_time - last_action_time > ACTION_DEBOUNCE_TIME):
            pyautogui.click(button='right')
            last_action_time = current_time

        # ── Debug visual ─────────────────────────────────────────────────────
        cv2.imshow("Eye Control v2", frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

        # ── FPS control ──────────────────────────────────────────────────────
        elapsed = time.perf_counter() - frame_start
        sleep_t = FRAME_INTERVAL - elapsed
        if sleep_t > 0.0:
            time.sleep(sleep_t)

    # ── Cleanup ──────────────────────────────────────────────────────────────
    if is_dragging_ref[0]:
        pyautogui.mouseUp(button='left')

    cv2.destroyAllWindows()
    tracking = False
    print("✅ Eye tracking v2 finalizado!")
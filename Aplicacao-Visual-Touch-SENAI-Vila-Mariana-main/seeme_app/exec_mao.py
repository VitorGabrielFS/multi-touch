import cv2
import mediapipe as mp
import pyautogui
import subprocess
import time
import os

# --- Configuração do MediaPipe ---
mp_hands = mp.solutions.hands
mp_drawing = mp.solutions.drawing_utils

# Inicia o detector de mãos
hands = mp_hands.Hands(
    static_image_mode=False,
    max_num_hands=1,
    min_detection_confidence=0.7,
    min_tracking_confidence=0.5
)

# Função pra contar dedos levantados
def contar_dedos(hand_landmarks):
    dedos = []

    # Pontos de referência dos dedos (dedão, indicador, médio, anelar, mindinho)
    tips_ids = [4, 8, 12, 16, 20]

    # Dedão (precisa de comparação diferente no eixo X)
    if hand_landmarks.landmark[tips_ids[0]].x < hand_landmarks.landmark[tips_ids[0] - 1].x:
        dedos.append(1)
    else:
        dedos.append(0)

    # Restante dos dedos (compara eixo Y)
    for id in range(1, 5):
        if hand_landmarks.landmark[tips_ids[id]].y < hand_landmarks.landmark[tips_ids[id] - 2].y:
            dedos.append(1)
        else:
            dedos.append(0)

    return sum(dedos)

# Controle de ação (pra evitar múltiplas execuções seguidas)
ultima_acao = None
ultimo_tempo = 0

# Tempo mínimo que o dedo precisa ficar levantado (em segundos)
TEMPO_MINIMO_GESTO = 1.0

# Variáveis para rastrear gestos mantidos
gesto_atual = None
tempo_inicio_gesto = 0

# --- Início da captura de vídeo ---
cap = cv2.VideoCapture(0)

print("Iniciando reconhecimento de gestos... (pressione 'q' para sair)")

while True:
    sucesso, frame = cap.read()
    if not sucesso:
        break

    frame = cv2.flip(frame, 1)
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    resultado = hands.process(rgb)

    if resultado.multi_hand_landmarks:
        for hand_landmarks in resultado.multi_hand_landmarks:
            mp_drawing.draw_landmarks(frame, hand_landmarks, mp_hands.HAND_CONNECTIONS)

            dedos_levantados = contar_dedos(hand_landmarks)
            cv2.putText(frame, f"Dedos: {dedos_levantados}", (10, 40), cv2.FONT_HERSHEY_SIMPLEX, 1, (0,255,0), 2)

            tempo_atual = time.time()
            
            # Verificar se o gesto mudou
            if dedos_levantados != gesto_atual:
                gesto_atual = dedos_levantados
                tempo_inicio_gesto = tempo_atual
            
            # Verificar se o gesto foi mantido por tempo suficiente
            tempo_gesto_mantido = tempo_atual - tempo_inicio_gesto
            
            # Anti-loop de execução (1 ação por 2 segundos)
            if tempo_atual - ultimo_tempo > 2:
                if (dedos_levantados == 1 and ultima_acao != 1 and 
                    tempo_gesto_mantido >= TEMPO_MINIMO_GESTO):
                    print("🖐️ Um dedo detectado e mantido -> abrindo Chrome...")
                    subprocess.Popen("start chrome", shell=True)
                    ultima_acao = 1
                    ultimo_tempo = tempo_atual

                elif (dedos_levantados == 2 and ultima_acao != 2 and 
                      tempo_gesto_mantido >= TEMPO_MINIMO_GESTO):
                    print("✌️ Dois dedos detectados e mantidos -> abrindo VSCode...")
                    subprocess.Popen("code", shell=True)
                    ultima_acao = 2
                    ultimo_tempo = tempo_atual
            
            # Mostrar informações na tela
            cv2.putText(frame, f"Tempo gesto: {tempo_gesto_mantido:.1f}s", (10, 80), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255,255,255), 2)
            if tempo_gesto_mantido < TEMPO_MINIMO_GESTO and dedos_levantados in [1, 2]:
                cv2.putText(frame, "Mantenha o gesto...", (10, 110), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0,255,255), 2)

    cv2.imshow("Controle por Gestos", frame)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()

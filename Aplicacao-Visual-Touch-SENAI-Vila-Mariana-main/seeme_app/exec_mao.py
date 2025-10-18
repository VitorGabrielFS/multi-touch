import cv2
import mediapipe as mp
import subprocess
import time
from typing import Callable, Dict

class GestureController:
    """
    Controlador de gestos com MediaPipe para detecção de mãos.
    Uso: Importe e use nos seus endpoints Flask.
    """
    
    def __init__(self, 
                 min_detection_confidence=0.7,
                 min_tracking_confidence=0.5,
                 tempo_minimo_gesto=1.0,
                 intervalo_antiloop=2.0):
        
        self.mp_hands = mp.solutions.hands
        self.mp_drawing = mp.solutions.drawing_utils
        
        self.hands = self.mp_hands.Hands(
            static_image_mode=False,
            max_num_hands=1,
            min_detection_confidence=min_detection_confidence,
            min_tracking_confidence=min_tracking_confidence
        )
        
        self.TEMPO_MINIMO_GESTO = tempo_minimo_gesto
        self.INTERVALO_ANTILOOP = intervalo_antiloop
        
        # Estado interno
        self.ultima_acao = None
        self.ultimo_tempo = 0
        self.gesto_atual = None
        self.tempo_inicio_gesto = 0
        
        # Mapeamento de ações por número de dedos
        self.acoes: Dict[int, Callable] = {}
        
    def contar_dedos(self, hand_landmarks):
        """Conta quantos dedos estão levantados."""
        dedos = []
        tips_ids = [4, 8, 12, 16, 20]
        
        # Dedão (comparação no eixo X)
        if hand_landmarks.landmark[tips_ids[0]].x < hand_landmarks.landmark[tips_ids[0] - 1].x:
            dedos.append(1)
        else:
            dedos.append(0)
        
        # Outros dedos (comparação no eixo Y)
        for id in range(1, 5):
            if hand_landmarks.landmark[tips_ids[id]].y < hand_landmarks.landmark[tips_ids[id] - 2].y:
                dedos.append(1)
            else:
                dedos.append(0)
        
        return sum(dedos)
    
    def registrar_acao(self, num_dedos: int, callback: Callable):
        """
        Registra uma ação para um número específico de dedos.
        
        Exemplo:
            controller.registrar_acao(1, lambda: subprocess.Popen("start chrome", shell=True))
            controller.registrar_acao(2, lambda: subprocess.Popen("code", shell=True))
        """
        self.acoes[num_dedos] = callback
    
    def processar_frame(self, frame):
        """Processa um frame e detecta gestos."""
        frame = cv2.flip(frame, 1)
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        resultado = self.hands.process(rgb)
        
        dedos_levantados = 0
        tempo_gesto_mantido = 0
        
        if resultado.multi_hand_landmarks:
            for hand_landmarks in resultado.multi_hand_landmarks:
                self.mp_drawing.draw_landmarks(
                    frame, 
                    hand_landmarks, 
                    self.mp_hands.HAND_CONNECTIONS
                )
                
                dedos_levantados = self.contar_dedos(hand_landmarks)
                tempo_atual = time.time()
                
                # Verificar se o gesto mudou
                if dedos_levantados != self.gesto_atual:
                    self.gesto_atual = dedos_levantados
                    self.tempo_inicio_gesto = tempo_atual
                
                # Calcular tempo que o gesto está mantido
                tempo_gesto_mantido = tempo_atual - self.tempo_inicio_gesto
                
                # Verificar se deve executar ação
                if (tempo_atual - self.ultimo_tempo > self.INTERVALO_ANTILOOP and
                    tempo_gesto_mantido >= self.TEMPO_MINIMO_GESTO and
                    dedos_levantados in self.acoes and
                    self.ultima_acao != dedos_levantados):
                    
                    print(f"🎯 Executando ação para {dedos_levantados} dedo(s)")
                    self.acoes[dedos_levantados]()
                    self.ultima_acao = dedos_levantados
                    self.ultimo_tempo = tempo_atual
                
                # Adicionar informações visuais
                cv2.putText(frame, f"Dedos: {dedos_levantados}", (10, 40), 
                           cv2.FONT_HERSHEY_SIMPLEX, 1, (0,255,0), 2)
                cv2.putText(frame, f"Tempo gesto: {tempo_gesto_mantido:.1f}s", (10, 80), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255,255,255), 2)
                
                if (tempo_gesto_mantido < self.TEMPO_MINIMO_GESTO and 
                    dedos_levantados in self.acoes):
                    cv2.putText(frame, "Mantenha o gesto...", (10, 110), 
                               cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0,255,255), 2)
        
        return frame
    
    def gerar_frames(self, camera_id=0):
        """
        Gerador de frames para streaming Flask.
        
        Use em uma rota Flask:
            @app.route('/video_feed')
            def video_feed():
                return Response(controller.gerar_frames(),
                              mimetype='multipart/x-mixed-replace; boundary=frame')
        """
        cap = cv2.VideoCapture(camera_id)
        
        try:
            while True:
                sucesso, frame = cap.read()
                if not sucesso:
                    break
                
                frame_processado = self.processar_frame(frame)
                
                # Encode frame para JPEG
                ret, buffer = cv2.imencode('.jpg', frame_processado)
                frame_bytes = buffer.tobytes()
                
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
        finally:
            cap.release()
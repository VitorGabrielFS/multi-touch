import cv2
import mediapipe as mp
import time
from seeme_app.control import gestos_active_event, resource_manager
from typing import Callable, Dict

class GestureController:
    """
    Controlador de gestos otimizado com MediaPipe.
    Reduz processamento desnecessário e melhora FPS.
    """
    
    def __init__(self, 
                 min_detection_confidence=0.7,
                 min_tracking_confidence=0.5,
                 tempo_minimo_gesto=1.0,
                 intervalo_antiloop=2.0,
                 mostrar_landmarks=False,  # Desabilitado por padrão
                 jpeg_quality=70,  # Qualidade menor = mais rápido
                 espelhar_imagem=True):  # Controla se a imagem deve ser espelhada
        
        self.mp_hands = mp.solutions.hands
        self.hands = self.mp_hands.Hands(
            static_image_mode=False,
            max_num_hands=1,
            min_detection_confidence=min_detection_confidence,
            min_tracking_confidence=min_tracking_confidence
        )
        
        # Configs
        self.TEMPO_MINIMO_GESTO = tempo_minimo_gesto
        self.INTERVALO_ANTILOOP = intervalo_antiloop
        self.mostrar_landmarks = mostrar_landmarks
        self.jpeg_quality = jpeg_quality
        self.espelhar_imagem = espelhar_imagem
        
        # Estado
        self.ultima_acao = None
        self.ultimo_tempo = 0
        self.gesto_atual = None
        self.tempo_inicio_gesto = 0
        self.acoes: Dict[int, Callable] = {}
        
        # Cache para desenho (se habilitado)
        if mostrar_landmarks:
            self.mp_drawing = mp.solutions.drawing_utils
    
    def contar_dedos(self, landmarks):
        """Conta dedos de forma otimizada."""
        l = landmarks.landmark
        
        # Dedão (eixo X)
        dedao = 1 if l[4].x < l[3].x else 0
        
        # Outros dedos (eixo Y) - loop otimizado
        outros = sum(1 for i in [8, 12, 16, 20] if l[i].y < l[i-2].y)
        
        return dedao + outros
    
    def registrar_acao(self, num_dedos: int, callback: Callable):
        """Registra ação para número de dedos."""
        self.acoes[num_dedos] = callback
    
    def processar_frame(self, frame):
        """Processa frame de forma otimizada."""
        # Aplica espelhamento se configurado
        if self.espelhar_imagem:
            frame = cv2.flip(frame, 1)  # Espelha horizontalmente (como um espelho)
        
        # Conversão RGB
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        resultado = self.hands.process(rgb)
        
        dedos = 0
        tempo_mantido = 0
        mostrar_aviso = False
        
        if resultado.multi_hand_landmarks:
            hand = resultado.multi_hand_landmarks[0]  # Só primeira mão
            dedos = self.contar_dedos(hand)
            tempo_atual = time.time()
            
            # Atualiza estado do gesto
            if dedos != self.gesto_atual:
                self.gesto_atual = dedos
                self.tempo_inicio_gesto = tempo_atual
            
            tempo_mantido = tempo_atual - self.tempo_inicio_gesto
            
            # Executa ação se necessário
            if (tempo_atual - self.ultimo_tempo > self.INTERVALO_ANTILOOP and
                tempo_mantido >= self.TEMPO_MINIMO_GESTO and
                dedos in self.acoes and
                self.ultima_acao != dedos):
                
                print(f"🎯 Ação executada: {dedos} dedo(s)")
                self.acoes[dedos]()
                self.ultima_acao = dedos
                self.ultimo_tempo = tempo_atual
            
            # Landmarks só se habilitado
            if self.mostrar_landmarks:
                self.mp_drawing.draw_landmarks(
                    frame, hand, self.mp_hands.HAND_CONNECTIONS
                )
            
            mostrar_aviso = (tempo_mantido < self.TEMPO_MINIMO_GESTO and 
                           dedos in self.acoes)
        
        # Texto otimizado: prepara tudo antes de desenhar
        font = cv2.FONT_HERSHEY_SIMPLEX
        cv2.putText(frame, f"Dedos: {dedos}", (10, 40), font, 1, (0,255,0), 2)
        
        if dedos > 0:
            cv2.putText(frame, f"Tempo: {tempo_mantido:.1f}s", (10, 80), 
                       font, 0.7, (255,255,255), 2)
        
        if mostrar_aviso:
            cv2.putText(frame, "Mantenha...", (10, 110), 
                       font, 0.7, (0,255,255), 2)
        
        return frame
    
    def gerar_frames(self):
        """
        Gerador otimizado de frames para Flask streaming usando câmera compartilhada.
        """
        # Usa a câmera compartilhada do ResourceManager
        cap = resource_manager.get_shared_camera()
        
        # Parâmetros de encode otimizados
        encode_params = [cv2.IMWRITE_JPEG_QUALITY, self.jpeg_quality]
        
        try:
            while gestos_active_event.is_set():
                sucesso, frame = cap.read()
                if not sucesso:
                    break
                
                frame_processado = self.processar_frame(frame)
                
                # Encode com qualidade ajustável
                _, buffer = cv2.imencode('.jpg', frame_processado, encode_params)
                
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + 
                       buffer.tobytes() + b'\r\n')
        finally:
            # Não libera a câmera aqui, deixa o ResourceManager gerenciar
            pass
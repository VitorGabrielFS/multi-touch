import threading
import cv2
from typing import Dict, Set, Optional

# Eventos individuais para cada recurso
voice_active_event = threading.Event()
gestos_active_event = threading.Event()
eye_tracking_active_event = threading.Event()

# Sistema de controle unificado
class ResourceManager:
    def __init__(self):
        self.active_resources: Set[str] = set()
        self.lock = threading.Lock()
        self.camera_lock = threading.Lock()
        self.camera_ref_count = 0
        self.shared_camera: Optional[cv2.VideoCapture] = None
        self.camera_frames: Optional[object] = None
        
    def start_resource(self, resource_name: str) -> bool:
        """Inicia um recurso se não estiver ativo"""
        with self.lock:
            if resource_name not in self.active_resources:
                self.active_resources.add(resource_name)
                return True
            return False
    
    def stop_resource(self, resource_name: str) -> bool:
        """Para um recurso específico"""
        with self.lock:
            if resource_name in self.active_resources:
                self.active_resources.remove(resource_name)
                return True
            return False
    
    def is_resource_active(self, resource_name: str) -> bool:
        """Verifica se um recurso está ativo"""
        with self.lock:
            return resource_name in self.active_resources
    
    def get_active_resources(self) -> Set[str]:
        """Retorna todos os recursos ativos"""
        with self.lock:
            return self.active_resources.copy()
    
    def get_shared_camera(self) -> cv2.VideoCapture:
        """Obtém ou cria a câmera compartilhada"""
        with self.camera_lock:
            if self.shared_camera is None or not self.shared_camera.isOpened():
                self.shared_camera = cv2.VideoCapture(0)
                self.shared_camera.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                print("🎥 Câmera compartilhada inicializada")
            return self.shared_camera
    
    def release_shared_camera(self):
        """Libera a câmera compartilhada se não há mais recursos usando"""
        with self.camera_lock:
            camera_users = sum(1 for resource in ['eye_tracking', 'gestos'] 
                             if resource in self.active_resources)
            if camera_users == 0 and self.shared_camera is not None:
                self.shared_camera.release()
                self.shared_camera = None
                print("🎥 Câmera compartilhada liberada")
    
    def acquire_camera(self) -> bool:
        """Adquire acesso à câmera"""
        with self.camera_lock:
            self.camera_ref_count += 1
            return True
    
    def release_camera(self) -> bool:
        """Libera acesso à câmera"""
        with self.camera_lock:
            if self.camera_ref_count > 0:
                self.camera_ref_count -= 1
                return self.camera_ref_count == 0
            return False

# Instância global do gerenciador
resource_manager = ResourceManager()
from flask import Flask, render_template
import threading
#se for rodar no senai, so comentar da linha 4 ate a 6 e da 21 ate 52
from control import voice_active_event
from voice import reconhecimento_de_voz
from eye import eye_tracking, set_tracking, cam
import os
app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/home')
def home():
    return render_template('indexHome.html')

@app.route('/landing')
def landing():
    return render_template('landing.html')

@app.route('/ajustes')
def ajustes():
    return render_template('ajustes.html')

@app.route('/start-tracking')
def start_tracking():
    if not getattr(eye_tracking, 'is_running', False):
        set_tracking(True)
        t = threading.Thread(target=eye_tracking, daemon=True)
        t.start()
        eye_tracking.is_running = True
        return "Rastreamento iniciado."
    return "Rastreamento já está em andamento."

@app.route('/stop-tracking')
def stop_tracking():
    set_tracking(False)
    if cam is not None:
        cam.release()
    eye_tracking.is_running = False
    return "Rastreamento parado."

@app.route('/start-voice')
def start_voice():
    if not voice_active_event.is_set():
        voice_active_event.set()
        threading.Thread(target=reconhecimento_de_voz, daemon=True).start()
        return "Reconhecimento de voz iniciado."
    return "Reconhecimento de voz já está em andamento."

@app.route('/stop-voice')
def stop_voice():
    voice_active_event.clear()
    return "Reconhecimento de voz parado."

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

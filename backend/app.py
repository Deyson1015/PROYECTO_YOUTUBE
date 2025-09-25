from flask import Flask, request, jsonify, send_file, render_template
from flask_cors import CORS
from dotenv import load_dotenv
import yt_dlp
import os
import json
import re
from urllib.parse import urlparse
import tempfile
import threading
import time
import logging
from datetime import datetime

# Cargar variables de entorno
load_dotenv()

# Configurar rutas relativas al directorio raíz del proyecto
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATE_DIR = os.path.join(BASE_DIR, 'frontend')
STATIC_DIR = os.path.join(BASE_DIR, 'frontend', 'static')

# Configuración de logging
log_level = os.getenv('LOG_LEVEL', 'INFO')
logging.basicConfig(
    level=getattr(logging, log_level),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__, template_folder=TEMPLATE_DIR, static_folder=STATIC_DIR, static_url_path='/static')

# Configuración de CORS
cors_origins = os.getenv('CORS_ORIGINS', '*')
if cors_origins != '*':
    cors_origins = cors_origins.split(',')
CORS(app, origins=cors_origins)

# Configuración de la aplicación
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-key-change-in-production')
app.config['MAX_CONTENT_LENGTH'] = int(os.getenv('MAX_FILE_SIZE', 52428800))  # 50MB

# Configuración de directorios
DOWNLOAD_DIR = os.path.join(BASE_DIR, os.getenv('DOWNLOAD_DIR', 'downloads'))
if not os.path.exists(DOWNLOAD_DIR):
    os.makedirs(DOWNLOAD_DIR)

logger.info(f"Aplicación iniciada. Directorio de descargas: {DOWNLOAD_DIR}")

# Almacenamiento temporal del progreso de descarga
download_progress = {}

class ProgressHook:
    def __init__(self, download_id):
        self.download_id = download_id
        
    def __call__(self, d):
        if d['status'] == 'downloading':
            percent = d.get('_percent_str', '0%').strip()
            speed = d.get('_speed_str', 'N/A')
            download_progress[self.download_id] = {
                'status': 'downloading',
                'percent': percent,
                'speed': speed,
                'filename': d.get('filename', '')
            }
        elif d['status'] == 'finished':
            download_progress[self.download_id] = {
                'status': 'finished',
                'percent': '100%',
                'speed': '0B/s',
                'filename': d.get('filename', '')
            }

def is_valid_url(url):
    """Valida si la URL es de YouTube o TikTok"""
    youtube_pattern = r'(https?://)?(www\.)?(youtube|youtu|youtube-nocookie)\.(com|be)/'
    tiktok_pattern = r'(https?://)?(www\.|vm\.)?tiktok\.com/'
    
    return re.match(youtube_pattern, url) or re.match(tiktok_pattern, url)

@app.route('/')
def index():
    """Página principal"""
    return render_template('index.html')

@app.route('/api/video-info', methods=['POST'])
def get_video_info():
    """Obtiene información del video sin descargarlo"""
    try:
        data = request.get_json()
        url = data.get('url')
        
        if not url or not is_valid_url(url):
            return jsonify({'error': 'URL no válida'}), 400
        
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extractflat': False,
            'format': 'best[height<=720]/best',  # Limitar calidad para evitar problemas
            'ignoreerrors': False,
            'extract_flat': False,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            try:
                info = ydl.extract_info(url, download=False)
                
                video_info = {
                    'title': info.get('title', 'Sin título'),
                    'duration': info.get('duration', 0),
                    'uploader': info.get('uploader', 'Desconocido'),
                    'thumbnail': info.get('thumbnail', ''),
                    'formats': []
                }
                
                # Obtener formatos disponibles - método más robusto
                if 'formats' in info and info['formats']:
                    # Filtrar y agregar formatos de video
                    for f in info['formats']:
                        if f.get('vcodec') and f.get('vcodec') != 'none':
                            video_info['formats'].append({
                                'format_id': f.get('format_id'),
                                'ext': f.get('ext', 'mp4'),
                                'quality': f.get('format_note', f.get('height', 'Desconocido')),
                                'filesize': f.get('filesize', 0)
                            })
                
                # Si no hay formatos específicos, agregar opciones básicas
                if not video_info['formats']:
                    video_info['formats'] = [
                        {'format_id': 'best', 'ext': 'mp4', 'quality': 'Mejor calidad', 'filesize': 0},
                        {'format_id': 'worst', 'ext': 'mp4', 'quality': 'Menor calidad', 'filesize': 0}
                    ]
                
                return jsonify(video_info)
                
            except yt_dlp.utils.DownloadError as e:
                logger.error(f"Error de descarga yt-dlp: {str(e)}")
                return jsonify({'error': f'Video no disponible o privado: {str(e)}'}), 400
            except Exception as e:
                logger.error(f"Error al extraer info: {str(e)}")
                return jsonify({'error': f'Error al procesar el video: {str(e)}'}), 500
            
    except Exception as e:
        return jsonify({'error': f'Error al obtener información del video: {str(e)}'}), 500

@app.route('/api/download', methods=['POST'])
def download_video():
    """Inicia la descarga del video"""
    try:
        data = request.get_json()
        url = data.get('url')
        quality = data.get('quality', 'best')
        format_type = data.get('format', 'mp4')
        
        if not url or not is_valid_url(url):
            return jsonify({'error': 'URL no válida'}), 400
        
        # Generar ID único para la descarga
        download_id = str(int(time.time() * 1000))
        
        # Configurar opciones de descarga
        ydl_opts = {
            'outtmpl': os.path.join(DOWNLOAD_DIR, '%(title)s.%(ext)s'),
            'format': 'best[height<=720]/best' if quality == 'best' else quality,
            'progress_hooks': [ProgressHook(download_id)],
            'ignoreerrors': False,
            'no_warnings': False,
        }
        
        # Configurar formato específico
        if format_type == 'mp3':
            ydl_opts.update({
                'format': 'bestaudio/best',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }],
            })
        
        def download_thread():
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([url])
            except Exception as e:
                download_progress[download_id] = {
                    'status': 'error',
                    'error': str(e)
                }
        
        # Iniciar descarga en hilo separado
        thread = threading.Thread(target=download_thread)
        thread.daemon = True
        thread.start()
        
        # Inicializar progreso
        download_progress[download_id] = {
            'status': 'starting',
            'percent': '0%',
            'speed': '0B/s'
        }
        
        return jsonify({'download_id': download_id})
        
    except Exception as e:
        return jsonify({'error': f'Error al iniciar descarga: {str(e)}'}), 500

@app.route('/api/progress/<download_id>')
def get_progress(download_id):
    """Obtiene el progreso de una descarga específica"""
    progress = download_progress.get(download_id, {'status': 'not_found'})
    return jsonify(progress)

@app.route('/api/downloads')
def list_downloads():
    """Lista todos los archivos descargados"""
    try:
        files = []
        if os.path.exists(DOWNLOAD_DIR):
            for filename in os.listdir(DOWNLOAD_DIR):
                filepath = os.path.join(DOWNLOAD_DIR, filename)
                if os.path.isfile(filepath):
                    files.append({
                        'filename': filename,
                        'size': os.path.getsize(filepath),
                        'modified': os.path.getmtime(filepath)
                    })
        
        return jsonify({'files': files})
    except Exception as e:
        return jsonify({'error': f'Error al listar descargas: {str(e)}'}), 500

@app.route('/api/download-file/<filename>')
def download_file(filename):
    """Descarga un archivo específico"""
    try:
        filepath = os.path.join(DOWNLOAD_DIR, filename)
        if os.path.exists(filepath):
            return send_file(filepath, as_attachment=True)
        else:
            return jsonify({'error': 'Archivo no encontrado'}), 404
    except Exception as e:
        return jsonify({'error': f'Error al descargar archivo: {str(e)}'}), 500

if __name__ == '__main__':
    # Configuración para desarrollo y producción
    port = int(os.getenv('PORT', 5000))
    host = os.getenv('HOST', '0.0.0.0')
    debug = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    
    logger.info(f"Iniciando servidor en {host}:{port} (debug={debug})")
    app.run(debug=debug, host=host, port=port)
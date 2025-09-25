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

def get_ydl_opts(additional_opts=None):
    """Obtiene configuración estándar de yt-dlp con headers anti-bot avanzados"""
    base_opts = {
        'quiet': True,
        'no_warnings': True,  
        'ignoreerrors': False,
        # Headers más actualizados para simular navegador real
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'referer': 'https://www.youtube.com/',
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': '*/*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Cache-Control': 'max-age=0',
        },
        # Configuraciones más agresivas anti-bot
        'extractor_args': {
            'youtube': {
                'skip': ['dash', 'hls'],
                'player_skip': ['js', 'configs'],
                'player_client': ['android', 'web'],
            }
        },
        # Configuraciones adicionales
        'socket_timeout': 30,
        'retries': 3,
        'fragment_retries': 3,
        'extract_flat': False,
        'age_limit': None,
        'prefer_insecure': False,
    }
    
    if additional_opts:
        base_opts.update(additional_opts)
    
    return base_opts

def extract_with_fallback(url):
    """Intenta extraer información del video con múltiples estrategias"""
    strategies = [
        # Estrategia 1: Configuración estándar
        get_ydl_opts(),
        
        # Estrategia 2: Cliente móvil
        get_ydl_opts({
            'extractor_args': {
                'youtube': {
                    'player_client': ['android'],
                    'skip': ['dash'],
                }
            }
        }),
        
        # Estrategia 3: Configuración mínima
        {
            'quiet': True,
            'no_warnings': True,
            'extractor_args': {
                'youtube': {
                    'player_client': ['android', 'web'],
                }
            }
        },
        
        # Estrategia 4: Solo extracción básica
        {
            'quiet': True,
            'extract_flat': False,
        }
    ]
    
    for i, opts in enumerate(strategies):
        try:
            logger.info(f"Intentando estrategia {i+1} para URL: {url}")
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)
                logger.info(f"Éxito con estrategia {i+1}")
                return info
        except yt_dlp.utils.DownloadError as e:
            logger.warning(f"Estrategia {i+1} falló: {str(e)}")
            continue
        except Exception as e:
            logger.warning(f"Error inesperado en estrategia {i+1}: {str(e)}")
            continue
    
    # Si todas las estrategias fallan
    raise Exception("No se pudo obtener información del video después de intentar múltiples estrategias")

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
        
        try:
            info = extract_with_fallback(url)
            
            video_info = {
                'title': info.get('title', 'Sin título'),
                'duration': info.get('duration', 0),
                'uploader': info.get('uploader', 'Desconocido'),
                'thumbnail': info.get('thumbnail', ''),
                'formats': []
            }
            
            # Siempre proporcionar formatos básicos que funcionan
            video_info['formats'] = [
                {'format_id': 'best', 'ext': 'mp4', 'quality': 'Mejor calidad disponible', 'filesize': 0},
                {'format_id': 'worst', 'ext': 'mp4', 'quality': 'Menor calidad', 'filesize': 0},
                {'format_id': 'bestaudio', 'ext': 'mp3', 'quality': 'Solo audio (MP3)', 'filesize': 0}
            ]
            
            # Intentar obtener formatos específicos si están disponibles
            if 'formats' in info and info['formats']:
                additional_formats = []
                seen_qualities = set()
                
                for f in info['formats']:
                    if f.get('vcodec') and f.get('vcodec') != 'none':
                        height = f.get('height')
                        if height and height not in seen_qualities and height <= 1080:
                            additional_formats.append({
                                'format_id': f.get('format_id'),
                                'ext': f.get('ext', 'mp4'),
                                'quality': f"{height}p" if height else f.get('format_note', 'Desconocido'),
                                'filesize': f.get('filesize', 0)
                            })
                            seen_qualities.add(height)
                
                # Agregar formatos adicionales si se encontraron
                if additional_formats:
                    video_info['formats'].extend(additional_formats[:3])  # Max 3 adicionales
            
            return jsonify(video_info)
            
        except Exception as e:
            logger.error(f"Error al extraer info: {str(e)}")
            return jsonify({'error': f'Video no disponible o bloqueado: {str(e)}'}), 400
            
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
        
        # Configurar opciones de descarga con formatos más flexibles y anti-bot
        ydl_opts = get_ydl_opts({
            'outtmpl': os.path.join(DOWNLOAD_DIR, '%(title)s.%(ext)s'),
            'format': quality if quality in ['best', 'worst', 'bestaudio'] else f'{quality}/best',
            'progress_hooks': [ProgressHook(download_id)],
        })
        
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
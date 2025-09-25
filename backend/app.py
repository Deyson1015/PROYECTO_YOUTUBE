from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from dotenv import load_dotenv
import yt_dlp
import os
import re
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode
import logging
from googleapiclient.discovery import build
import base64
import tempfile

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

logger.info("Aplicación iniciada (modo playlist, sin endpoints de descarga)")

# === Config de cookies para YouTube (para evitar bloqueos/429) ===
COOKIEFILE_PATH = None
COOKIE_HEADER_STR = None
try:
    if os.getenv('YT_COOKIES_FILE') and os.path.exists(os.getenv('YT_COOKIES_FILE')):
        COOKIEFILE_PATH = os.getenv('YT_COOKIES_FILE')
        logger.info('Usando cookies Netscape desde YT_COOKIES_FILE')
    elif os.getenv('YT_COOKIES_B64'):
        raw = base64.b64decode(os.getenv('YT_COOKIES_B64')).decode('utf-8', errors='ignore')
        tmp_path = os.path.join(tempfile.gettempdir(), 'yt_cookies.txt')
        with open(tmp_path, 'w', encoding='utf-8') as f:
            f.write(raw)
        COOKIEFILE_PATH = tmp_path
        logger.info('Usando cookies Netscape desde YT_COOKIES_B64 (archivo temporal)')
    if os.getenv('YT_COOKIES_HEADER'):
        COOKIE_HEADER_STR = os.getenv('YT_COOKIES_HEADER')  # cadena "key=value; key2=value2"
        logger.info('Añadiendo cabecera Cookie desde YT_COOKIES_HEADER')
except Exception as e:
    logger.warning(f'No se pudo preparar cookies: {e}')


def is_valid_url(url):
    """Valida si la URL es de YouTube o TikTok"""
    youtube_pattern = r'(https?://)?(www\.)?(youtube|youtu|youtube-nocookie)\.(com|be)/'
    tiktok_pattern = r'(https?://)?(www\.|vm\.)?tiktok\.com/'
    
    return re.match(youtube_pattern, url) or re.match(tiktok_pattern, url)

# === Normalizar URL de YouTube para evitar modo playlist/tab ===

def normalize_url(url: str) -> str:
    try:
        if not url:
            return url
        if 'youtube.com' in url or 'youtube-nocookie.com' in url or 'youtu.be' in url:
            parts = urlsplit(url)
            q = dict(parse_qsl(parts.query))
            keep = {}
            # Mantener solo parámetros útiles para un video único
            if 'v' in q:
                keep['v'] = q['v']
            if 't' in q:
                keep['t'] = q['t']
            # youtu.be no usa query para v
            if parts.netloc.endswith('youtu.be'):
                return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode({'t': keep.get('t')}) if 't' in keep else '', parts.fragment))
            return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(keep), parts.fragment))
        return url
    except Exception:
        return url


def extract_youtube_id(url):
    """Extrae el ID del video de YouTube de una URL"""
    patterns = [
        r'(?:v=|\/)([0-9A-Za-z_-]{11}).*',
        r'(?:embed\/)([0-9A-Za-z_-]{11})',
        r'(?:watch\?v=)([0-9A-Za-z_-]{11})',
        r'youtu\.be\/([0-9A-Za-z_-]{11})',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None


def get_youtube_info_api(video_id):
    """Obtiene información del video usando la API oficial de YouTube"""
    try:
        api_key = os.getenv('YOUTUBE_API_KEY')
        if not api_key or api_key == 'your_youtube_api_key_here':
            logger.warning("YouTube API key no configurada, usando método alternativo")
            return None
        
        youtube = build('youtube', 'v3', developerKey=api_key)
        request = youtube.videos().list(part='snippet,contentDetails,statistics', id=video_id)
        response = request.execute()
        if not response['items']:
            return None
        
        video = response['items'][0]
        snippet = video['snippet']
        
        # Convertir duración ISO 8601 a segundos
        duration_str = video['contentDetails']['duration']
        duration_seconds = parse_duration(duration_str)
        
        return {
            'title': snippet['title'],
            'duration': duration_seconds,
            'uploader': snippet['channelTitle'],
            'thumbnail': snippet['thumbnails'].get('maxres', snippet['thumbnails']['high'])['url'],
            'description': snippet.get('description', ''),
            'view_count': video['statistics'].get('viewCount', 0)
        }
        
    except Exception as e:
        logger.error(f"Error al usar YouTube API: {str(e)}")
        return None


def parse_duration(duration_str):
    """Convierte duración ISO 8601 (PT4M13S) a segundos"""
    import re
    pattern = r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?'
    match = re.match(pattern, duration_str)
    if not match:
        return 0
    
    hours = int(match.group(1) or 0)
    minutes = int(match.group(2) or 0) 
    seconds = int(match.group(3) or 0)
    
    return hours * 3600 + minutes * 60 + seconds


def get_ydl_opts(additional_opts=None):
    """Obtiene configuración estándar de yt-dlp con headers anti-bot avanzados"""
    base_opts = {
        'quiet': True,
        'no_warnings': True,  
        'ignoreerrors': False,
        'noplaylist': True,
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
        'extractor_args': {
            'youtube': {
                'skip': ['dash', 'hls'],
                'player_skip': ['js', 'configs'],
                'player_client': ['android', 'web', 'ios', 'tv_embedded'],
            }
        },
        'socket_timeout': 30,
        'retries': 3,
        'fragment_retries': 3,
        'extract_flat': False,
        'age_limit': None,
        'prefer_insecure': False,
    }

    # Inyectar cookies si están configuradas
    if COOKIEFILE_PATH:
        base_opts['cookiefile'] = COOKIEFILE_PATH
    if COOKIE_HEADER_STR:
        base_opts.setdefault('http_headers', {})['Cookie'] = COOKIE_HEADER_STR

    if additional_opts:
        # Combinar headers si hay adicionales
        if 'http_headers' in additional_opts:
            merged = base_opts.get('http_headers', {}).copy()
            merged.update(additional_opts['http_headers'])
            additional_opts = {**additional_opts, 'http_headers': merged}
        base_opts.update(additional_opts)
    return base_opts


# Reforzar estrategias para usar noplaylist

def extract_with_fallback(url):
    """Intenta extraer información del video con múltiples estrategias"""
    strategies = [
        # Estrategia 1: Configuración estándar
        get_ydl_opts(),
        
        # Estrategia 2: Cliente móvil + cookies forzadas
        get_ydl_opts({
            'extractor_args': {
                'youtube': {
                    'player_client': ['android', 'ios'],
                    'skip': ['dash'],
                }
            },
            'http_headers': {
                # Forzar referer y posible Cookie ya incluida
                'Referer': 'https://www.youtube.com/'
            }
        }),
        
        # Estrategia 3: Cliente TV embedded (suele evadir algunos bloqueos)
        get_ydl_opts({
            'extractor_args': {
                'youtube': {
                    'player_client': ['tv_embedded'],
                    'skip': ['dash']
                }
            },
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (CrKey armv7l 1.36.159268) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.6099.0 Safari/537.36 CrKey/1.36.159268',
                'Referer': 'https://www.youtube.com/'
            }
        }),
        
        # Estrategia 4: Básica
        get_ydl_opts({ 'extract_flat': False })
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


def get_video_info_hybrid(url):
    """Método híbrido: API de YouTube primero, fallback a yt-dlp"""
    # Verificar si es YouTube
    if 'youtube.com' in url or 'youtu.be' in url:
        video_id = extract_youtube_id(url)
        if video_id:
            logger.info(f"Intentando YouTube API para video ID: {video_id}")
            api_info = get_youtube_info_api(video_id)
            if api_info:
                logger.info("Éxito con YouTube API")
                return api_info, True  # True indica que vino de API
    
    # Fallback a yt-dlp para YouTube sin API o TikTok
    logger.info("Usando fallback yt-dlp")
    ydl_info = extract_with_fallback(url)
    return ydl_info, False  # False indica que vino de yt-dlp


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
            info, from_api = get_video_info_hybrid(url)
            
            video_info = {
                'title': info.get('title', 'Sin título'),
                'duration': info.get('duration', 0),
                'uploader': info.get('uploader', 'Desconocido'),
                'thumbnail': info.get('thumbnail', ''),
                'formats': [],
                'source': 'youtube_api' if from_api else 'yt_dlp'
            }
            
            # Siempre proporcionar formatos básicos que funcionan
            video_info['formats'] = [
                {'format_id': 'best', 'ext': 'mp4', 'quality': 'Mejor calidad disponible', 'filesize': 0},
                {'format_id': 'worst', 'ext': 'mp4', 'quality': 'Menor calidad', 'filesize': 0},
                {'format_id': 'bestaudio', 'ext': 'mp3', 'quality': 'Solo audio (MP3)', 'filesize': 0}
            ]
            
            # Si viene de API, agregar formatos predefinidos
            if from_api:
                video_info['formats'].extend([
                    {'format_id': '720', 'ext': 'mp4', 'quality': '720p HD', 'filesize': 0},
                    {'format_id': '480', 'ext': 'mp4', 'quality': '480p SD', 'filesize': 0},
                ])
            # Si viene de yt-dlp, intentar obtener formatos específicos
            elif 'formats' in info and info['formats']:
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


# === Selector de formato directo ===

def _pick_direct_format(info_dict, quality: str, format_type: str):
    # Si ya es una sola URL
    if info_dict.get('url') and not info_dict.get('formats'):
        return {
            'url': info_dict['url'],
            'ext': info_dict.get('ext', 'mp4'),
            'format_id': info_dict.get('format_id', 'direct'),
            'height': info_dict.get('height'),
            'acodec': info_dict.get('acodec'),
            'vcodec': info_dict.get('vcodec')
        }
    formats = info_dict.get('formats') or []
    if not formats:
        raise Exception('No hay formatos disponibles para enlace directo')
    def is_progressive(f):
        return (f.get('vcodec') and f.get('vcodec') != 'none') and (f.get('acodec') and f.get('acodec') != 'none')
    def is_audio_only(f):
        return (f.get('acodec') and f.get('acodec') != 'none') and (not f.get('vcodec') or f.get('vcodec') == 'none')
    def height_of(f):
        return f.get('height') or 0
    if format_type in ('mp3', 'audio', 'bestaudio'):
        audio_formats = [f for f in formats if is_audio_only(f)]
        audio_formats.sort(key=lambda f: (0 if (f.get('ext') in ('m4a', 'mp4', 'aac', 'mp3')) else 1, -(f.get('abr') or f.get('tbr') or 0)))
        if audio_formats:
            return audio_formats[0]
        prog_fallback = [f for f in formats if is_progressive(f)]
        if prog_fallback:
            prog_fallback.sort(key=lambda f: (height_of(f), f.get('ext') != 'mp4'))
            return prog_fallback[0]
        raise Exception('No se encontró formato de audio directo')
    progressive = [f for f in formats if is_progressive(f)]
    if quality not in ('best', 'worst', '720', '480', 'bestaudio'):
        exact = next((f for f in formats if f.get('format_id') == quality), None)
        if exact:
            return exact
    if progressive:
        if quality == 'worst':
            progressive.sort(key=lambda f: (height_of(f), f.get('ext') != 'mp4'))
            return progressive[0]
        if quality in ('720', '480'):
            target = int(quality)
            below = [f for f in progressive if height_of(f) and height_of(f) <= target]
            if below:
                below.sort(key=lambda f: (-(height_of(f)), f.get('ext') != 'mp4'))
                return below[0]
            above = [f for f in progressive if height_of(f) and height_of(f) > target]
            if above:
                above.sort(key=lambda f: (height_of(f), f.get('ext') != 'mp4'))
                return above[0]
        progressive.sort(key=lambda f: (-(height_of(f)), f.get('ext') != 'mp4', -(f.get('tbr') or 0)))
        return progressive[0]
    formats_sorted = sorted(formats, key=lambda f: (-(height_of(f)), f.get('ext') != 'mp4', -(f.get('tbr') or 0)))
    if formats_sorted:
        return formats_sorted[0]
    raise Exception('No fue posible seleccionar un formato directo')


# === Endpoint: devolver URL directa ===

@app.route('/api/direct-url', methods=['POST'])
def direct_url():
    try:
        data = request.get_json() or {}
        url = data.get('url')
        quality = str(data.get('quality', 'best'))
        format_type = str(data.get('format', 'mp4')).lower()
        if not url or not is_valid_url(url):
            return jsonify({'error': 'URL no válida'}), 400
        url = normalize_url(url)
        # Reutilizar la extracción robusta que ya funciona en /api/video-info
        info = extract_with_fallback(url)
        selected = _pick_direct_format(info, quality, format_type)
        direct = selected.get('url')
        if not direct:
            raise Exception('No se obtuvo URL directa del formato seleccionado')
        title = (info.get('title') or 'video').strip()
        safe_title = re.sub(r'[\\/:*?"<>|]+', '_', title).strip('_.') or 'video'
        ext = selected.get('ext') or ('m4a' if format_type in ('mp3', 'audio', 'bestaudio') else 'mp4')
        return jsonify({
            'direct_url': direct,
            'filename': f"{safe_title}.{ext}",
            'ext': ext,
            'format_id': selected.get('format_id'),
            'height': selected.get('height'),
            'source': 'yt_dlp'
        })
    except Exception as e:
        logger.error(f"Error al obtener enlace directo: {str(e)}")
        return jsonify({'error': f'No se pudo obtener enlace directo: {str(e)}'}), 400


# === Búsqueda por nombre ===

def youtube_search_api(query: str, max_results: int = 10):
    """Busca videos por nombre usando la API de YouTube y devuelve una lista de resultados estándar."""
    try:
        api_key = os.getenv('YOUTUBE_API_KEY')
        if not api_key or api_key == 'your_youtube_api_key_here':
            return None
        youtube = build('youtube', 'v3', developerKey=api_key)
        search_resp = youtube.search().list(
            q=query, part='snippet', type='video', maxResults=max_results
        ).execute()
        video_ids = [item['id']['videoId'] for item in search_resp.get('items', []) if item['id'].get('videoId')]
        if not video_ids:
            return []
        videos_resp = youtube.videos().list(
            id=','.join(video_ids), part='snippet,contentDetails,statistics'
        ).execute()
        results = []
        for item in videos_resp.get('items', []):
            vid = item['id']
            sn = item['snippet']
            cd = item['contentDetails']
            duration_seconds = parse_duration(cd.get('duration', 'PT0S'))
            thumb = (sn.get('thumbnails', {}).get('high') or sn.get('thumbnails', {}).get('default') or {}).get('url', '')
            results.append({
                'title': sn.get('title'),
                'uploader': sn.get('channelTitle'),
                'duration': duration_seconds,
                'thumbnail': thumb,
                'video_id': vid,
                'video_url': f'https://www.youtube.com/watch?v={vid}',
                'platform': 'youtube'
            })
        return results
    except Exception as e:
        logger.error(f"Error en youtube_search_api: {e}")
        return []


# === Nuevo: búsqueda por artista (canal) ===

def youtube_search_by_artist(query: str, max_results: int = 10):
    """Busca canales por nombre y devuelve videos del/los canal(es) mejor coincidencia."""
    try:
        api_key = os.getenv('YOUTUBE_API_KEY')
        if not api_key or api_key == 'your_youtube_api_key_here':
            return None
        youtube = build('youtube', 'v3', developerKey=api_key)
        # 1) Buscar canales que coincidan con el artista
        channels_resp = youtube.search().list(q=query, part='snippet', type='channel', maxResults=3).execute()
        channel_ids = [it['id']['channelId'] for it in channels_resp.get('items', []) if it['id'].get('channelId')]
        if not channel_ids:
            return []
        # 2) Traer videos de esos canales (relevancia)
        video_ids = []
        for ch in channel_ids:
            videos = youtube.search().list(part='snippet', channelId=ch, type='video', maxResults=min(10, max_results), order='relevance').execute()
            video_ids.extend([vi['id']['videoId'] for vi in videos.get('items', []) if vi['id'].get('videoId')])
            if len(video_ids) >= max_results:
                break
        video_ids = video_ids[:max_results]
        if not video_ids:
            return []
        details = youtube.videos().list(id=','.join(video_ids), part='snippet,contentDetails,statistics').execute()
        results = []
        for item in details.get('items', []):
            vid = item['id']
            sn = item['snippet']
            cd = item['contentDetails']
            duration_seconds = parse_duration(cd.get('duration', 'PT0S'))
            thumb = (sn.get('thumbnails', {}).get('high') or sn.get('thumbnails', {}).get('default') or {}).get('url', '')
            results.append({
                'title': sn.get('title'),
                'uploader': sn.get('channelTitle'),
                'duration': duration_seconds,
                'thumbnail': thumb,
                'video_id': vid,
                'video_url': f'https://www.youtube.com/watch?v={vid}',
                'platform': 'youtube'
            })
        # Ordenar por vistas descendente si están disponibles
        results.sort(key=lambda r: int(next((it['statistics'].get('viewCount', 0) for it in details.get('items', []) if it['id']==r['video_id']), 0)), reverse=True)
        return results
    except Exception as e:
        logger.error(f"Error en youtube_search_by_artist: {e}")
        return []


def yt_dlp_search(query: str, max_results: int = 10):
    """Fallback: usa yt-dlp 'ytsearch' para obtener resultados cuando no hay API."""
    try:
        ydl_opts = {'quiet': True, 'no_warnings': True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"ytsearch{max_results}:{query}", download=False)
            entries = info.get('entries') or []
            results = []
            for e in entries:
                if not e:
                    continue
                vid = e.get('id') or e.get('video_id')
                if not vid:
                    continue
                results.append({
                    'title': e.get('title'),
                    'uploader': e.get('uploader') or e.get('channel') or '',
                    'duration': e.get('duration') or 0,
                    'thumbnail': e.get('thumbnail') or '',
                    'video_id': vid,
                    'video_url': e.get('webpage_url') or f'https://www.youtube.com/watch?v={vid}',
                    'platform': 'youtube'
                })
            return results
    except Exception as e:
        logger.error(f"Error en yt_dlp_search: {e}")
        return []


# Nuevo: fallback para artista usando yt-dlp

def yt_dlp_search_by_artist(query: str, max_results: int = 10):
    try:
        # Traer más resultados y priorizar por coincidencia en uploader
        ydl_opts = {'quiet': True, 'no_warnings': True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"ytsearch{max_results*3}:{query}", download=False)
            entries = info.get('entries') or []
            qlower = query.lower()
            filtered = []
            for e in entries:
                up = (e.get('uploader') or e.get('channel') or '').lower()
                if qlower in up:
                    vid = e.get('id') or e.get('video_id')
                    if not vid:
                        continue
                    filtered.append({
                        'title': e.get('title'),
                        'uploader': e.get('uploader') or e.get('channel') or '',
                        'duration': e.get('duration') or 0,
                        'thumbnail': e.get('thumbnail') or '',
                        'video_id': vid,
                        'video_url': e.get('webpage_url') or f'https://www.youtube.com/watch?v={vid}',
                        'platform': 'youtube'
                    })
                if len(filtered) >= max_results:
                    break
            return filtered[:max_results]
    except Exception as e:
        logger.error(f"Error en yt_dlp_search_by_artist: {e}")
        return []


@app.route('/api/search', methods=['POST'])
def search_videos():
    """Busca videos por nombre. Usa YouTube API si está disponible; soporta 'type': 'video' o 'artist'."""
    try:
        data = request.get_json() or {}
        query = (data.get('query') or '').strip()
        max_results = int(data.get('maxResults', 10))
        search_type = (data.get('type') or 'video').lower()
        if not query:
            return jsonify({'error': 'Falta query'}), 400
        source = 'youtube_api'
        if search_type == 'artist':
            results = youtube_search_by_artist(query, max_results)
            if results is None:
                results = yt_dlp_search_by_artist(query, max_results)
                source = 'yt_dlp'
            elif isinstance(results, list) and len(results) == 0:
                fb = yt_dlp_search_by_artist(query, max_results)
                if fb:
                    results = fb
                    source = 'yt_dlp'
        else:
            results = youtube_search_api(query, max_results)
            if results is None:
                results = yt_dlp_search(query, max_results)
                source = 'yt_dlp'
            elif isinstance(results, list) and len(results) == 0:
                fb = yt_dlp_search(query, max_results)
                if fb:
                    results = fb
                    source = 'yt_dlp'
        return jsonify({'results': results or [], 'source': source})
    except Exception as e:
        logger.error(f"Error en /api/search: {e}")
        return jsonify({'error': f'No se pudo buscar: {str(e)}'}), 500


if __name__ == '__main__':
    # Configuración para desarrollo y producción
    port = int(os.getenv('PORT', 5000))
    host = os.getenv('HOST', '0.0.0.0')
    debug = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    
    logger.info(f"Iniciando servidor en {host}:{port} (debug={debug})")
    app.run(debug=debug, host=host, port=port)
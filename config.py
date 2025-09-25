# Configuración del Video Downloader

# Configuración del servidor
DEBUG = True
HOST = '0.0.0.0'
PORT = 5000

# Configuración de descargas
MAX_DOWNLOAD_SIZE = 500 * 1024 * 1024  # 500MB
DOWNLOAD_TIMEOUT = 300  # 5 minutos
ALLOWED_FORMATS = ['mp4', 'mp3', 'webm', 'm4a']

# Configuración de calidad
QUALITY_OPTIONS = {
    'best': 'best[ext=mp4]/best',
    'worst': 'worst[ext=mp4]/worst',
    'audio': 'bestaudio/best'
}

# Configuración de FFmpeg (opcional)
FFMPEG_PATH = None  # Se detectará automáticamente

# Configuración de logs
LOG_LEVEL = 'INFO'
LOG_FILE = 'video_downloader.log'

# URLs permitidas (patrones regex)
ALLOWED_DOMAINS = [
    r'(https?://)?(www\.)?(youtube|youtu|youtube-nocookie)\.(com|be)/',
    r'(https?://)?(www\.|vm\.)?tiktok\.com/'
]

# Límites de rate limiting
RATE_LIMIT = {
    'requests_per_minute': 30,
    'requests_per_hour': 100
}
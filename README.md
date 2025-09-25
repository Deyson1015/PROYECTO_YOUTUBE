# Video Downloader - YouTube & TikTok

Una aplicación web con interfaz móvil optimizada para descargar videos de YouTube y TikTok.

## Características

- 📱 **Interfaz móvil optimizada** - Diseño responsivo para dispositivos móviles
- 🎬 **YouTube & TikTok** - Soporte para ambas plataformas
- 🔍 **Análisis de video** - Vista previa con información del video
- ⚙️ **Opciones de calidad** - Selección de calidad y formato
- 📊 **Progreso en tiempo real** - Seguimiento del progreso de descarga
- 📁 **Historial de descargas** - Lista de archivos descargados
- 🎨 **Interfaz moderna** - Diseño atractivo y fácil de usar

## Requisitos

- Python 3.8+
- yt-dlp
- Flask
- FFmpeg (opcional, para conversión de audio)

## Instalación

1. **Clonar el repositorio:**
   ```bash
   git clone <tu-repositorio>
   cd PROYECTO_YOUTUBE
   ```

2. **Crear entorno virtual:**
   ```bash
   python -m venv venv
   
   # Windows
   venv\Scripts\activate
   
   # Linux/Mac
   source venv/bin/activate
   ```

3. **Instalar dependencias:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Instalar yt-dlp (alternativa):**
   ```bash
   # Si hay problemas con la versión del requirements.txt
   pip install yt-dlp --upgrade
   ```

5. **Instalar FFmpeg (opcional):**
   - **Windows:** Descargar desde https://ffmpeg.org/download.html
   - **Linux:** `sudo apt install ffmpeg`
   - **Mac:** `brew install ffmpeg`

## Uso

1. **Iniciar el servidor:**
   ```bash
   python backend/app.py
   ```

2. **Abrir en el navegador:**
   ```
   http://localhost:5000
   ```

3. **Usar la aplicación:**
   - Pegar el enlace de YouTube o TikTok
   - Hacer clic en "Analizar"
   - Seleccionar calidad y formato
   - Hacer clic en "Descargar"
   - Ver el progreso en tiempo real
   - Descargar el archivo desde el historial

## Estructura del Proyecto

```
PROYECTO_YOUTUBE/
├── backend/
│   └── app.py              # Servidor Flask principal
├── frontend/
│   ├── index.html          # Página principal
│   └── static/
│       ├── css/
│       │   └── styles.css  # Estilos CSS
│       └── js/
│           └── app.js      # JavaScript del frontend
├── downloads/              # Carpeta de descargas
├── requirements.txt        # Dependencias Python
└── README.md              # Este archivo
```

## API Endpoints

- `GET /` - Página principal
- `POST /api/video-info` - Obtener información del video
- `POST /api/download` - Iniciar descarga
- `GET /api/progress/<id>` - Obtener progreso de descarga
- `GET /api/downloads` - Listar archivos descargados
- `GET /api/download-file/<filename>` - Descargar archivo

## Formatos Soportados

### Video
- MP4 (recomendado)
- WebM
- MKV
- AVI

### Audio
- MP3 (extracción de audio)
- M4A
- WebM (solo audio)

## Plataformas Soportadas

- ✅ YouTube (videos y shorts)
- ✅ TikTok (videos públicos)
- ❌ Videos privados o con restricciones

## Solución de Problemas

### Error: "No module named 'yt_dlp'"
```bash
pip install yt-dlp --upgrade
```

### Error: "FFmpeg not found"
- Instalar FFmpeg y agregarlo al PATH del sistema
- Para solo video MP4, FFmpeg no es necesario

### Error: "Unable to extract video info"
- Verificar que la URL sea válida y pública
- Algunos videos pueden tener restricciones regionales

### El servidor no inicia
```bash
# Verificar que el puerto 5000 esté libre
netstat -an | findstr :5000

# Usar otro puerto si es necesario
python backend/app.py --port 8000
```

## Optimizaciones Móviles

- **Viewport optimizado** para dispositivos móviles
- **Touch-friendly** controles grandes y espaciados
- **Responsive design** se adapta a cualquier tamaño de pantalla
- **Scroll suave** para mejor experiencia de usuario
- **Gestión de teclado** para formularios móviles

## Seguridad

- **Validación de URLs** solo YouTube y TikTok
- **Límites de descarga** evita abuso del servidor
- **CORS configurado** para seguridad del navegador
- **Sanitización de nombres** de archivos descargados

## Contribuir

1. Fork el repositorio
2. Crear una rama para tu feature
3. Hacer commit de tus cambios
4. Push a la rama
5. Crear un Pull Request

## Licencia

MIT License - ver LICENSE file para detalles.

## Disclaimer

Esta aplicación es solo para uso educativo y personal. Respeta los términos de servicio de YouTube y TikTok. No uses esta herramienta para infringir derechos de autor.
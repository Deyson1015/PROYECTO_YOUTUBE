// Configuración de la API
const API_BASE = window.location.origin;

// Elementos del DOM
const urlInput = document.getElementById('urlInput');
const analyzeBtn = document.getElementById('analyzeBtn');
const analyzeSpinner = document.getElementById('analyzeSpinner');
const videoInfo = document.getElementById('videoInfo');
const videoThumbnail = document.getElementById('videoThumbnail');
const videoTitle = document.getElementById('videoTitle');
const videoUploader = document.getElementById('videoUploader');
const videoDuration = document.getElementById('videoDuration');
const qualitySelect = document.getElementById('qualitySelect');
const formatSelect = document.getElementById('formatSelect');
const downloadBtn = document.getElementById('downloadBtn');
const downloadSpinner = document.getElementById('downloadSpinner');
const progressSection = document.getElementById('progressSection');
const progressFill = document.getElementById('progressFill');
const progressPercent = document.getElementById('progressPercent');
const progressSpeed = document.getElementById('progressSpeed');
const progressFilename = document.getElementById('progressFilename');
const downloadsList = document.getElementById('downloadsList');
const refreshDownloads = document.getElementById('refreshDownloads');
const alert = document.getElementById('alert');
const alertMessage = document.getElementById('alertMessage');

// Variables globales
let currentVideoInfo = null;
let currentDownloadId = null;
let progressInterval = null;

// Inicialización
document.addEventListener('DOMContentLoaded', function() {
    setupEventListeners();
    loadDownloads();
    
    // Auto-pegar desde el portapapeles si está disponible
    if (navigator.clipboard && navigator.clipboard.readText) {
        navigator.clipboard.readText().then(text => {
            if (isValidUrl(text)) {
                urlInput.value = text;
            }
        }).catch(() => {
            // Silenciar errores de permisos
        });
    }
});

// Event Listeners
function setupEventListeners() {
    analyzeBtn.addEventListener('click', analyzeVideo);
    downloadBtn.addEventListener('click', startDownload);
    refreshDownloads.addEventListener('click', loadDownloads);
    
    urlInput.addEventListener('keypress', function(e) {
        if (e.key === 'Enter') {
            analyzeVideo();
        }
    });
    
    urlInput.addEventListener('input', function() {
        if (videoInfo.style.display !== 'none') {
            hideVideoInfo();
        }
    });

    // Touch events para mejor UX móvil
    urlInput.addEventListener('focus', function() {
        setTimeout(() => {
            this.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }, 300);
    });
}

// Validación de URL
function isValidUrl(url) {
    const youtubePattern = /^(https?:\/\/)?(www\.)?(youtube|youtu|youtube-nocookie)\.(com|be)\//;
    const tiktokPattern = /^(https?:\/\/)?(www\.|vm\.)?tiktok\.com\//;
    return youtubePattern.test(url) || tiktokPattern.test(url);
}

// Formatear duración
function formatDuration(seconds) {
    if (!seconds) return 'Desconocido';
    
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secs = seconds % 60;
    
    if (hours > 0) {
        return `${hours}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
    } else {
        return `${minutes}:${secs.toString().padStart(2, '0')}`;
    }
}

// Formatear tamaño de archivo
function formatFileSize(bytes) {
    if (!bytes) return 'Desconocido';
    
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(1024));
    return `${(bytes / Math.pow(1024, i)).toFixed(1)} ${sizes[i]}`;
}

// Mostrar alerta
function showAlert(message, type = 'error') {
    alertMessage.textContent = message;
    alert.className = `alert ${type}`;
    alert.style.display = 'flex';
    
    // Auto-cerrar después de 5 segundos
    setTimeout(() => {
        closeAlert();
    }, 5000);
}

// Cerrar alerta
function closeAlert() {
    alert.style.display = 'none';
}

// Ocultar información del video
function hideVideoInfo() {
    videoInfo.style.display = 'none';
    progressSection.style.display = 'none';
    currentVideoInfo = null;
}

// Analizar video
async function analyzeVideo() {
    const url = urlInput.value.trim();
    
    if (!url) {
        showAlert('Por favor, ingresa una URL');
        return;
    }
    
    if (!isValidUrl(url)) {
        showAlert('URL no válida. Solo se admiten enlaces de YouTube y TikTok');
        return;
    }
    
    setButtonLoading(analyzeBtn, true);
    hideVideoInfo();
    
    try {
        const response = await fetch(`${API_BASE}/api/video-info`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ url })
        });
        
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.error || 'Error al analizar el video');
        }
        
        currentVideoInfo = data;
        displayVideoInfo(data);
        animatePlatformDetection(url);
        
    } catch (error) {
        console.error('Error:', error);
        showAlert(error.message || 'Error al analizar el video');
    } finally {
        setButtonLoading(analyzeBtn, false);
    }
}

// Mostrar información del video
function displayVideoInfo(info) {
    // Thumbnail
    if (info.thumbnail) {
        videoThumbnail.src = info.thumbnail;
        videoThumbnail.style.display = 'block';
    } else {
        videoThumbnail.style.display = 'none';
    }
    
    // Detectar plataforma y agregar icono
    const url = urlInput.value.trim();
    let platformIcon = '';
    if (url.includes('youtube.com') || url.includes('youtu.be')) {
        platformIcon = '<i class="fab fa-youtube" style="color: #FF0000; margin-right: 0.5rem;"></i>';
    } else if (url.includes('tiktok.com')) {
        platformIcon = '<i class="fab fa-tiktok" style="color: #FF0050; margin-right: 0.5rem;"></i>';
    }
    
    // Detalles
    videoTitle.innerHTML = platformIcon + (info.title || 'Sin título');
    videoUploader.textContent = info.uploader || 'Desconocido';
    videoDuration.textContent = formatDuration(info.duration);
    
    // Opciones de calidad
    qualitySelect.innerHTML = '<option value="best">Mejor calidad</option>';
    
    if (info.formats && info.formats.length > 0) {
        const uniqueQualities = new Set();
        
        info.formats.forEach(format => {
            const quality = format.quality || 'unknown';
            if (!uniqueQualities.has(quality) && quality !== 'unknown') {
                uniqueQualities.add(quality);
                const option = document.createElement('option');
                option.value = format.format_id;
                option.textContent = `${quality} (${format.ext.toUpperCase()})`;
                if (format.filesize) {
                    option.textContent += ` - ${formatFileSize(format.filesize)}`;
                }
                qualitySelect.appendChild(option);
            }
        });
    }
    
    qualitySelect.innerHTML += '<option value="worst">Menor calidad</option>';
    
    // Mostrar sección
    videoInfo.style.display = 'block';
    videoInfo.scrollIntoView({ behavior: 'smooth' });
}

// Iniciar descarga
async function startDownload() {
    if (!currentVideoInfo) {
        showAlert('Primero analiza un video');
        return;
    }
    
    const url = urlInput.value.trim();
    const quality = qualitySelect.value;
    const format = formatSelect.value;
    
    setButtonLoading(downloadBtn, true);
    
    try {
        const response = await fetch(`${API_BASE}/api/download`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ url, quality, format })
        });
        
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.error || 'Error al iniciar descarga');
        }
        
        currentDownloadId = data.download_id;
        showProgressSection();
        startProgressTracking();
        
        showAlert('Descarga iniciada correctamente', 'success');
        
    } catch (error) {
        console.error('Error:', error);
        showAlert(error.message || 'Error al iniciar descarga');
        setButtonLoading(downloadBtn, false);
    }
}

// Mostrar sección de progreso
function showProgressSection() {
    progressSection.style.display = 'block';
    progressFill.style.width = '0%';
    progressPercent.textContent = '0%';
    progressSpeed.textContent = '0B/s';
    progressFilename.textContent = '';
    
    progressSection.scrollIntoView({ behavior: 'smooth' });
}

// Iniciar seguimiento de progreso
function startProgressTracking() {
    if (progressInterval) {
        clearInterval(progressInterval);
    }
    
    progressInterval = setInterval(updateProgress, 1000);
}

// Actualizar progreso
async function updateProgress() {
    if (!currentDownloadId) return;
    
    try {
        const response = await fetch(`${API_BASE}/api/progress/${currentDownloadId}`);
        const data = await response.json();
        
        if (data.status === 'downloading') {
            const percent = data.percent || '0%';
            const speed = data.speed || '0B/s';
            const filename = data.filename || '';
            
            progressFill.style.width = percent;
            progressPercent.textContent = percent;
            progressSpeed.textContent = speed;
            
            if (filename) {
                progressFilename.textContent = filename.split(/[/\\]/).pop();
            }
            
        } else if (data.status === 'finished') {
            progressFill.style.width = '100%';
            progressPercent.textContent = '100%';
            progressSpeed.textContent = 'Completado';
            
            clearInterval(progressInterval);
            setButtonLoading(downloadBtn, false);
            
            showAlert('¡Descarga completada!', 'success');
            
            // Actualizar lista de descargas
            setTimeout(() => {
                loadDownloads();
                progressSection.style.display = 'none';
            }, 2000);
            
        } else if (data.status === 'error') {
            clearInterval(progressInterval);
            setButtonLoading(downloadBtn, false);
            progressSection.style.display = 'none';
            
            showAlert(`Error en descarga: ${data.error}`, 'error');
        }
        
    } catch (error) {
        console.error('Error al obtener progreso:', error);
    }
}

// Cargar lista de descargas
async function loadDownloads() {
    try {
        const response = await fetch(`${API_BASE}/api/downloads`);
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.error || 'Error al cargar descargas');
        }
        
        displayDownloads(data.files || []);
        
    } catch (error) {
        console.error('Error:', error);
        downloadsList.innerHTML = '<p class="no-downloads">Error al cargar descargas</p>';
    }
}

// Mostrar lista de descargas
function displayDownloads(files) {
    if (!files.length) {
        downloadsList.innerHTML = '<p class="no-downloads"><i class="fas fa-inbox"></i> No hay descargas aún</p>';
        return;
    }
    
    // Ordenar por fecha de modificación (más reciente primero)
    files.sort((a, b) => b.modified - a.modified);
    
    downloadsList.innerHTML = files.map(file => {
        // Detectar tipo de archivo
        let fileIcon = '<i class="fas fa-file"></i>';
        if (file.filename.includes('.mp4')) {
            fileIcon = '<i class="fas fa-film" style="color: #FF6B6B;"></i>';
        } else if (file.filename.includes('.mp3')) {
            fileIcon = '<i class="fas fa-music" style="color: #6C5CE7;"></i>';
        }
        
        return `
            <div class="download-item">
                <div class="download-info">
                    <div class="download-name">
                        ${fileIcon}
                        ${file.filename}
                    </div>
                    <div class="download-meta">
                        <i class="fas fa-hdd"></i> ${formatFileSize(file.size)} • 
                        <i class="fas fa-calendar"></i> ${new Date(file.modified * 1000).toLocaleString('es-ES')}
                    </div>
                </div>
                <button class="download-action" onclick="downloadFile('${file.filename}')">
                    <i class="fas fa-download"></i> Descargar
                </button>
            </div>
        `;
    }).join('');
}

// Descargar archivo
function downloadFile(filename) {
    const link = document.createElement('a');
    link.href = `${API_BASE}/api/download-file/${encodeURIComponent(filename)}`;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    
    showAlert('Iniciando descarga del archivo...', 'success');
}

// Establecer estado de carga en botón
function setButtonLoading(button, loading) {
    button.disabled = loading;
    const spinner = button.querySelector('.spinner');
    const text = button.querySelector('.btn-text');
    
    if (loading) {
        spinner.style.display = 'block';
        text.style.display = 'none';
    } else {
        spinner.style.display = 'none';
        text.style.display = 'block';
    }
}

// Service Worker para PWA (opcional)
if ('serviceWorker' in navigator) {
    window.addEventListener('load', function() {
        navigator.serviceWorker.register('/static/sw.js')
            .then(function(registration) {
                console.log('ServiceWorker registrado correctamente');
            })
            .catch(function(error) {
                console.log('Error al registrar ServiceWorker');
            });
    });
}

// Prevenir zoom al hacer doble tap en iOS
let lastTouchEnd = 0;
document.addEventListener('touchend', function (event) {
    const now = (new Date()).getTime();
    if (now - lastTouchEnd <= 300) {
        event.preventDefault();
    }
    lastTouchEnd = now;
}, false);

// Manejo de orientación en móvil
window.addEventListener('orientationchange', function() {
    setTimeout(function() {
        window.scrollTo(0, 0);
    }, 500);
});

// Funciones de animación de iconos
function animateYouTubeIcon() {
    const youtubeIcon = document.querySelector('.youtube-icon');
    if (youtubeIcon) {
        youtubeIcon.style.animation = 'pulse 0.5s ease-in-out 3';
    }
}

function animateTikTokIcon() {
    const tiktokIcon = document.querySelector('.tiktok-icon');
    if (tiktokIcon) {
        tiktokIcon.style.animation = 'bounce-slow 0.5s ease-in-out 3';
    }
}

function animatePlatformDetection(url) {
    if (url.includes('youtube.com') || url.includes('youtu.be')) {
        animateYouTubeIcon();
        showAlert('¡Video de YouTube detectado!', 'success');
    } else if (url.includes('tiktok.com')) {
        animateTikTokIcon();
        showAlert('¡Video de TikTok detectado!', 'success');
    }
}

// Función para botón de scroll to top
function scrollToTop() {
    window.scrollTo({
        top: 0,
        behavior: 'smooth'
    });
}

// Mostrar/ocultar botón flotante
window.addEventListener('scroll', function() {
    const scrollButton = document.getElementById('scrollToTop');
    if (window.pageYOffset > 300) {
        scrollButton.style.display = 'flex';
    } else {
        scrollButton.style.display = 'none';
    }
});

// Botón flotante para scroll to top
const scrollToTopBtn = document.getElementById('scrollToTop');

window.addEventListener('scroll', function() {
    if (window.pageYOffset > 300) {
        scrollToTopBtn.style.display = 'flex';
    } else {
        scrollToTopBtn.style.display = 'none';
    }
});

function scrollToTop() {
    window.scrollTo({
        top: 0,
        behavior: 'smooth'
    });
}

// Efectos ripple para botones
document.addEventListener('click', function(e) {
    const target = e.target.closest('.ripple');
    if (!target) return;
    
    const rect = target.getBoundingClientRect();
    const ripple = document.createElement('span');
    const size = Math.max(rect.width, rect.height);
    const x = e.clientX - rect.left - size / 2;
    const y = e.clientY - rect.top - size / 2;
    
    ripple.style.width = ripple.style.height = size + 'px';
    ripple.style.left = x + 'px';
    ripple.style.top = y + 'px';
    ripple.classList.add('ripple-effect');
    
    target.appendChild(ripple);
    
    setTimeout(() => {
        ripple.remove();
    }, 600);
});

// Animaciones cuando los elementos entran en viewport
const observerOptions = {
    threshold: 0.1,
    rootMargin: '0px 0px -50px 0px'
};

const observer = new IntersectionObserver(function(entries) {
    entries.forEach(entry => {
        if (entry.isIntersecting) {
            entry.target.style.opacity = '1';
            entry.target.style.transform = 'translateY(0)';
        }
    });
}, observerOptions);

// Observar elementos que necesitan animación
document.addEventListener('DOMContentLoaded', function() {
    const elementsToObserve = document.querySelectorAll('.video-card, .download-options, .progress-card, .downloads-section');
    elementsToObserve.forEach(el => {
        el.style.opacity = '0';
        el.style.transform = 'translateY(20px)';
        el.style.transition = 'all 0.6s cubic-bezier(0.4, 0, 0.2, 1)';
        observer.observe(el);
    });
});

// Easter egg - Konami code
let konamiCode = [];
const konamiSequence = [38, 38, 40, 40, 37, 39, 37, 39, 66, 65]; // ↑↑↓↓←→←→BA

document.addEventListener('keydown', function(e) {
    konamiCode.push(e.keyCode);
    if (konamiCode.length > konamiSequence.length) {
        konamiCode.shift();
    }
    
    if (konamiCode.length === konamiSequence.length && 
        konamiCode.every((code, index) => code === konamiSequence[index])) {
        showAlert('🎉 ¡Código Konami activado! ¡Eres un verdadero gamer!', 'success');
        document.body.style.animation = 'rainbow 2s infinite';
        setTimeout(() => {
            document.body.style.animation = '';
        }, 5000);
    }
});
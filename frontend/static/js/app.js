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
// Playlist UI (reutilizamos ids existentes)
const downloadsList = document.getElementById('downloadsList');
const refreshDownloads = document.getElementById('refreshDownloads');
// Player controls
const mediaPlayer = document.getElementById('mediaPlayer');
const nowPlayingTitle = document.getElementById('nowPlayingTitle');
const prevBtn = document.getElementById('prevBtn');
const playPauseBtn = document.getElementById('playPauseBtn');
const nextBtn = document.getElementById('nextBtn');
// Alertas
const alert = document.getElementById('alert');
const alertMessage = document.getElementById('alertMessage');
// Resultados de búsqueda
const resultsSection = document.getElementById('resultsSection');
const resultsList = document.getElementById('resultsList');
const searchTypeSelect = document.getElementById('searchType');

// Estado global
let currentVideoInfo = null;
let playlist = []; // [{title, url, ext, duration, uploader, thumbnail, addedAt}]
let currentIndex = -1;

// Inicialización
document.addEventListener('DOMContentLoaded', function() {
    setupEventListeners();
    loadPlaylist();

    // Auto-pegar desde portapapeles
    if (navigator.clipboard && navigator.clipboard.readText) {
        navigator.clipboard.readText().then(text => {
            if (isValidUrl(text)) urlInput.value = text;
        }).catch(() => {});
    }
});

function setupEventListeners() {
    analyzeBtn.addEventListener('click', searchOrAnalyze);
    downloadBtn.addEventListener('click', addToPlaylist);
    refreshDownloads.addEventListener('click', clearPlaylist);

    urlInput.addEventListener('keypress', function(e) { if (e.key === 'Enter') searchOrAnalyze(); });
    urlInput.addEventListener('input', function() { if (videoInfo.style.display !== 'none') hideVideoInfo(); });

    // Player controls
    if (prevBtn) prevBtn.addEventListener('click', playPrev);
    if (nextBtn) nextBtn.addEventListener('click', playNext);
    if (playPauseBtn) playPauseBtn.addEventListener('click', togglePlayPause);

    if (mediaPlayer) {
        mediaPlayer.addEventListener('ended', playNext);
        mediaPlayer.addEventListener('play', () => setPlayIcon(true));
        mediaPlayer.addEventListener('pause', () => setPlayIcon(false));
    }

    // Touch UX
    urlInput.addEventListener('focus', function() {
        setTimeout(() => { this.scrollIntoView({ behavior: 'smooth', block: 'center' }); }, 300);
    });
}

function setPlayIcon(isPlaying) {
    if (!playPauseBtn) return;
    const icon = playPauseBtn.querySelector('i');
    if (!icon) return;
    icon.className = isPlaying ? 'fas fa-pause' : 'fas fa-play';
}

// Validación de URL
function isValidUrl(url) {
    const youtubePattern = /^(https?:\/\/)?(www\.)?(youtube|youtu|youtube-nocookie)\.(com|be)\//;
    const tiktokPattern = /^(https?:\/\/)?(www\.|vm\.)?tiktok\.com\//;
    return youtubePattern.test(url) || tiktokPattern.test(url);
}

// Utilidades de UI
function formatDuration(seconds) {
    if (!seconds) return 'Desconocido';
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = seconds % 60;
    return h > 0 ? `${h}:${m.toString().padStart(2,'0')}:${s.toString().padStart(2,'0')}` : `${m}:${s.toString().padStart(2,'0')}`;
}
function formatFileSize(bytes) {
    if (!bytes) return 'Desconocido';
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(1024));
    return `${(bytes / Math.pow(1024, i)).toFixed(1)} ${sizes[i]}`;
}
function showAlert(message, type = 'error') {
    alertMessage.textContent = message;
    alert.className = `alert ${type}`;
    alert.style.display = 'flex';
    setTimeout(() => { closeAlert(); }, 4000);
}
function closeAlert() { alert.style.display = 'none'; }

function hideVideoInfo() {
    videoInfo.style.display = 'none';
    currentVideoInfo = null;
}

// Analizar video
async function analyzeVideo() {
    const url = urlInput.value.trim();
    if (!url) return showAlert('Por favor, ingresa una URL');
    if (!isValidUrl(url)) return showAlert('URL no válida. Solo YouTube y TikTok');

    setButtonLoading(analyzeBtn, true);
    hideVideoInfo();

    try {
        const response = await fetch(`${API_BASE}/api/video-info`, {
            method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ url })
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || 'Error al analizar el video');
        currentVideoInfo = data; displayVideoInfo(data); animatePlatformDetection(url);
    } catch (e) { console.error(e); showAlert(e.message || 'Error al analizar'); }
    finally { setButtonLoading(analyzeBtn, false); }
}

function displayVideoInfo(info) {
    if (info.thumbnail) { videoThumbnail.src = info.thumbnail; videoThumbnail.style.display = 'block'; } else { videoThumbnail.style.display = 'none'; }
    const url = urlInput.value.trim();
    let platformIcon = '';
    if (url.includes('youtube.com') || url.includes('youtu.be')) platformIcon = '<i class="fab fa-youtube" style="color:#FF0000;margin-right:.5rem;"></i>';
    else if (url.includes('tiktok.com')) platformIcon = '<i class="fab fa-tiktok" style="color:#FF0050;margin-right:.5rem;"></i>';

    videoTitle.innerHTML = platformIcon + (info.title || 'Sin título');
    videoUploader.textContent = info.uploader || 'Desconocido';
    videoDuration.textContent = formatDuration(info.duration);

    // Opciones de calidad (con lo que llegó)
    qualitySelect.innerHTML = '<option value="best">Mejor calidad</option>';
    if (info.formats && info.formats.length > 0) {
        const seen = new Set();
        info.formats.forEach(f => {
            const q = f.quality || (f.height ? `${f.height}p` : null);
            if (!q || seen.has(q)) return;
            seen.add(q);
            const opt = document.createElement('option');
            opt.value = f.format_id; opt.textContent = `${q} (${(f.ext||'mp4').toUpperCase()})`;
            qualitySelect.appendChild(opt);
        });
    }
    qualitySelect.innerHTML += '<option value="worst">Menor calidad</option>';

    videoInfo.style.display = 'block';
    videoInfo.scrollIntoView({ behavior: 'smooth' });
}

// Nueva función: agregar a playlist y reproducir
async function addToPlaylist() {
    if (!currentVideoInfo) return showAlert('Primero analiza un video');
    const url = urlInput.value.trim();
    const quality = qualitySelect ? qualitySelect.value : 'best';
    // Si no existe el selector de tipo (mp4/mp3), usar 'mp4' por defecto
    const format = (typeof formatSelect !== 'undefined' && formatSelect && formatSelect.value) ? formatSelect.value : 'mp4';

    setButtonLoading(downloadBtn, true);
    try {
        // Obtener URL directa (sin descargar en servidor)
        const resp = await fetch(`${API_BASE}/api/direct-url`, {
            method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ url, quality, format })
        });
        const data = await resp.json();
        if (!resp.ok) throw new Error(data.error || 'No se pudo obtener el stream');

        const item = {
            title: currentVideoInfo.title || 'Sin título',
            uploader: currentVideoInfo.uploader || '',
            duration: currentVideoInfo.duration || 0,
            thumbnail: currentVideoInfo.thumbnail || '',
            url: data.direct_url,
            ext: data.ext || (format === 'mp3' ? 'm4a' : 'mp4'),
            addedAt: Date.now(),
        };
        playlist.push(item);
        savePlaylist();
        renderPlaylist();
        showAlert('Agregado a la playlist', 'success');

        // Autoreproducir si no hay nada reproduciéndose
        if (currentIndex === -1) {
            playIndex(0);
        }
    } catch (e) {
        console.error(e); showAlert(e.message || 'Error al agregar a playlist');
    } finally {
        setButtonLoading(downloadBtn, false);
    }
}

function savePlaylist() { localStorage.setItem('playlist', JSON.stringify(playlist)); }
function loadPlaylist() {
    try { playlist = JSON.parse(localStorage.getItem('playlist') || '[]'); } catch { playlist = []; }
    renderPlaylist();
}

function renderPlaylist() {
    if (!playlist.length) {
        downloadsList.innerHTML = '<p class="no-downloads"><i class="fas fa-inbox"></i> Tu playlist está vacía</p>';
        return;
    }
    downloadsList.innerHTML = playlist.map((item, idx) => `
        <div class="download-item">
            <div class="download-info" onclick="playIndex(${idx})" style="cursor: pointer;">
                <div class="download-name">
                    ${item.ext === 'mp3' || item.ext === 'm4a' ? '<i class="fas fa-music" style="color:#6C5CE7;"></i>' : '<i class="fas fa-film" style="color:#FF6B6B;"></i>'}
                    ${escapeHtml(item.title)}
                </div>
                <div class="download-meta">
                    <i class="fas fa-user"></i> ${escapeHtml(item.uploader || 'Desconocido')} • 
                    <i class="fas fa-clock"></i> ${formatDuration(item.duration)}
                </div>
            </div>
            <div class="download-actions">
                <button class="download-action" title="Reproducir" onclick="playIndex(${idx})"><i class="fas fa-play"></i></button>
                <button class="download-action" title="Eliminar" onclick="removeFromPlaylist(${idx}); event.stopPropagation();"><i class="fas fa-trash"></i></button>
            </div>
        </div>
    `).join('');
}

function escapeHtml(s) {
    return String(s || '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;','\'':'&#39;'}[c]));
}

function removeFromPlaylist(index) {
    if (index < 0 || index >= playlist.length) return;
    const removingCurrent = index === currentIndex;
    playlist.splice(index, 1);
    if (removingCurrent) {
        // Ajustar índice y parar reproducción
        mediaPlayer.pause();
        mediaPlayer.removeAttribute('src');
        nowPlayingTitle.textContent = 'Nada reproduciéndose';
        currentIndex = -1;
    } else if (index < currentIndex) {
        currentIndex -= 1;
    }
    savePlaylist();
    renderPlaylist();
}

function clearPlaylist() {
    if (!playlist.length) return;
    playlist = [];
    currentIndex = -1;
    savePlaylist();
    renderPlaylist();
    if (mediaPlayer) { mediaPlayer.pause(); mediaPlayer.removeAttribute('src'); }
    nowPlayingTitle.textContent = 'Tu playlist está vacía';
    showAlert('Playlist vaciada', 'success');
}

function playIndex(index) {
    if (!playlist.length) return;
    if (index < 0 || index >= playlist.length) index = 0;
    currentIndex = index;
    const item = playlist[currentIndex];
    if (!item) return;

    try {
        // Reproducir directo desde la URL del CDN
        mediaPlayer.src = item.url;
        mediaPlayer.play().catch(() => {/* autoplay policy */});
        nowPlayingTitle.textContent = item.title || 'Reproduciendo';
        setPlayIcon(true);
        // Scroll to player
        const playerSection = document.getElementById('playerSection');
        if (playerSection) playerSection.scrollIntoView({ behavior: 'smooth' });
    } catch (e) {
        console.error('No se pudo reproducir:', e);
        showAlert('No se pudo iniciar la reproducción');
    }
}

function playPrev() { if (!playlist.length) return; const idx = currentIndex <= 0 ? playlist.length - 1 : currentIndex - 1; playIndex(idx); }
function playNext() { if (!playlist.length) return; const idx = currentIndex >= playlist.length - 1 ? 0 : currentIndex + 1; playIndex(idx); }
function togglePlayPause() { if (!mediaPlayer) return; if (mediaPlayer.paused) mediaPlayer.play(); else mediaPlayer.pause(); }

// Establecer estado de carga en botón
function setButtonLoading(button, loading) {
    button.disabled = loading;
    const spinner = button.querySelector('.spinner');
    const text = button.querySelector('.btn-text');
    if (spinner && text) { spinner.style.display = loading ? 'block' : 'none'; text.style.display = loading ? 'none' : 'block'; }
}

// Service Worker para PWA (opcional)
if ('serviceWorker' in navigator) {
    window.addEventListener('load', function() {
        navigator.serviceWorker.register('/static/sw.js').catch(() => {});
    });
}

// Animaciones e interacciones varias
function animateYouTubeIcon() { const el = document.querySelector('.youtube-icon'); if (el) el.style.animation = 'pulse 0.5s ease-in-out 3'; }
function animateTikTokIcon() { const el = document.querySelector('.tiktok-icon'); if (el) el.style.animation = 'bounce-slow 0.5s ease-in-out 3'; }
function animatePlatformDetection(url) { if (url.includes('youtube.com')||url.includes('youtu.be')) { animateYouTubeIcon(); showAlert('¡Video de YouTube detectado!', 'success'); } else if (url.includes('tiktok.com')) { animateTikTokIcon(); showAlert('¡Video de TikTok detectado!', 'success'); } }

// Botón flotante y efectos
window.addEventListener('scroll', function() { const btn = document.getElementById('scrollToTop'); if (!btn) return; btn.style.display = window.pageYOffset > 300 ? 'flex' : 'none'; });
function scrollToTop() { window.scrollTo({ top: 0, behavior: 'smooth' }); }

document.addEventListener('click', function(e) {
    const target = e.target.closest('.ripple'); if (!target) return;
    const rect = target.getBoundingClientRect();
    const ripple = document.createElement('span');
    const size = Math.max(rect.width, rect.height);
    const x = e.clientX - rect.left - size / 2; const y = e.clientY - rect.top - size / 2;
    ripple.style.width = ripple.style.height = size + 'px'; ripple.style.left = x + 'px'; ripple.style.top = y + 'px'; ripple.classList.add('ripple-effect');
    target.appendChild(ripple); setTimeout(() => ripple.remove(), 600);
});

const observerOptions = { threshold: 0.1, rootMargin: '0px 0px -50px 0px' };
const observer = new IntersectionObserver(function(entries) { entries.forEach(entry => { if (entry.isIntersecting) { entry.target.style.opacity = '1'; entry.target.style.transform = 'translateY(0)'; } }); }, observerOptions);

document.addEventListener('DOMContentLoaded', function() {
    const els = document.querySelectorAll('.video-card, .download-options, .progress-card, .downloads-section');
    els.forEach(el => { el.style.opacity = '0'; el.style.transform = 'translateY(20px)'; el.style.transition = 'all 0.6s cubic-bezier(0.4,0,0.2,1)'; observer.observe(el); });
});

// Easter egg
let konamiCode = []; const konamiSequence = [38,38,40,40,37,39,37,39,66,65];
document.addEventListener('keydown', function(e) {
    konamiCode.push(e.keyCode); if (konamiCode.length > konamiSequence.length) konamiCode.shift();
    if (konamiCode.length === konamiSequence.length && konamiCode.every((c,i)=>c===konamiSequence[i])) {
        showAlert('🎉 ¡Código Konami activado!', 'success'); document.body.style.animation='rainbow 2s infinite'; setTimeout(()=>{document.body.style.animation='';},5000);
    }
});

// Eliminar funciones de descarga/proxy ya no usadas en modo playlist
function showProgressSection() { /* oculto en modo playlist */ }
function startProgressTracking() { /* no-op */ }
async function updateProgress() { /* no-op */ }
async function downloadViaProxyWithProgress() { /* no-op */ }
function downloadFile() { /* no-op */ }

async function searchOrAnalyze() {
    const text = urlInput.value.trim();
    if (!text) return showAlert('Escribe un nombre o pega un link');

    // Si parece URL válida, analizamos como antes
    if (isValidUrl(text)) return analyzeVideo();

    // Caso contrario: buscar por nombre (por título o artista)
    setButtonLoading(analyzeBtn, true);
    hideVideoInfo();
    try {
        const type = searchTypeSelect ? searchTypeSelect.value : 'video';
        const resp = await fetch(`${API_BASE}/api/search`, {
            method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ query: text, maxResults: 10, type })
        });
        const data = await resp.json();
        if (!resp.ok) throw new Error(data.error || 'No se pudo buscar');
        renderSearchResults(data.results || []);
    } catch (e) {
        console.error(e); showAlert(e.message || 'Error en la búsqueda');
    } finally { setButtonLoading(analyzeBtn, false); }
}

function renderSearchResults(results) {
    if (!results || !results.length) {
        resultsList.innerHTML = '<p class="no-downloads"><i class="fas fa-search"></i> Sin resultados</p>';
        resultsSection.style.display = 'block';
        return;
    }
    resultsList.innerHTML = results.map((r, idx) => `
        <div class="download-item">
            <div class="download-info">
                <div class="download-name">
                    <i class="fab fa-youtube" style="color:#FF0000;"></i>
                    ${escapeHtml(r.title)}
                </div>
                <div class="download-meta">
                    <i class="fas fa-user"></i> ${escapeHtml(r.uploader || 'Desconocido')} • 
                    <i class="fas fa-clock"></i> ${formatDuration(r.duration || 0)}
                </div>
            </div>
            <div class="download-actions">
                <button class="download-action" title="Seleccionar" onclick="selectSearchResult('${r.video_url.replace(/'/g, "&#39;")}')"><i class="fas fa-check"></i></button>
            </div>
        </div>
    `).join('');
    resultsSection.style.display = 'block';
}

window.selectSearchResult = async function(videoUrl) {
    // Colocar URL y analizar como antes
    urlInput.value = videoUrl;
    resultsSection.style.display = 'none';
    await analyzeVideo();
}
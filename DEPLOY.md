# Video Downloader - Guía de Despliegue

Esta guía te ayudará a desplegar tu aplicación de descarga de videos en diferentes plataformas.

## 🚀 Despliegue en Render

### Pasos para desplegar en Render:

1. **Crear cuenta en Render**: Ve a [render.com](https://render.com) y crea una cuenta.

2. **Conectar repositorio**: 
   - Sube tu código a GitHub
   - En Render, selecciona "New Web Service"
   - Conecta tu repositorio de GitHub

3. **Configuración automática**:
   - Render detectará automáticamente que es una aplicación Python
   - Usará el `requirements.txt` y `Procfile` automáticamente

4. **Variables de entorno** (opcional):
   ```
   FLASK_ENV=production
   FLASK_DEBUG=False
   SECRET_KEY=tu_clave_secreta_muy_segura
   ```

5. **Desplegar**: Hacer clic en "Create Web Service"

## 🌐 Despliegue en Heroku

### Pasos para Heroku:

1. **Instalar Heroku CLI**:
   ```bash
   # Windows
   winget install Heroku.CLI
   ```

2. **Login y crear app**:
   ```bash
   heroku login
   heroku create tu-app-name
   ```

3. **Configurar variables**:
   ```bash
   heroku config:set FLASK_ENV=production
   heroku config:set SECRET_KEY=tu_clave_secreta
   ```

4. **Desplegar**:
   ```bash
   git add .
   git commit -m "Deploy to Heroku"
   git push heroku main
   ```

## ☁️ Despliegue en Railway

1. **Ir a Railway**: [railway.app](https://railway.app)
2. **Conectar GitHub**: Importar tu repositorio
3. **Deploy automático**: Railway detectará la configuración automáticamente

## 🐳 Despliegue con Docker

Si prefieres usar Docker, aquí está el Dockerfile:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 5000

CMD ["gunicorn", "backend.app:app", "--bind", "0.0.0.0:5000"]
```

## 📝 Variables de Entorno Importantes

- `PORT`: Puerto del servidor (automático en Render/Heroku)
- `FLASK_ENV`: production
- `SECRET_KEY`: Clave secreta segura
- `CORS_ORIGINS`: Dominios permitidos para CORS

## 🔧 Troubleshooting

### Error común: "Module not found"
- Asegúrate de que `requirements.txt` esté actualizado
- Verifica que la estructura de carpetas sea correcta

### Error: "Port binding"
- El puerto se configura automáticamente con `$PORT`
- No hardcodees el puerto en producción

### Error: "Static files not found"
- Verifica que las rutas en `app.py` sean correctas
- Los archivos estáticos deben estar en `frontend/static/`

## 🌟 Recomendaciones

1. **Render** (Recomendado):
   - Fácil de usar
   - Plan gratuito disponible
   - SSL automático
   - Escalado automático

2. **Heroku**:
   - Muy popular
   - Buena documentación
   - Plan gratuito limitado

3. **Railway**:
   - Moderno y rápido
   - Buena experiencia de usuario
   - Plan gratuito generoso

## 🔒 Seguridad

- Cambia `SECRET_KEY` en producción
- Configura `CORS_ORIGINS` apropiadamente
- Usa HTTPS en producción (automático en Render/Heroku)

¡Tu aplicación estará lista para funcionar en minutos! 🎉
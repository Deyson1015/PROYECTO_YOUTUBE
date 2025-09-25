#!/usr/bin/env python3
import os
import sys

# Agregar el directorio actual al path
sys.path.append(os.path.dirname(__file__))

# Importar la aplicación Flask desde el backend
from backend.app import app

if __name__ == "__main__":
    app.run()
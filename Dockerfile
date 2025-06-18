# Étape de base
FROM python:3.11-slim

# Dépendances système
RUN apt-get update && apt-get install -y \
    ffmpeg \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Dossier de travail
WORKDIR /app

# Copier les fichiers
COPY . .

# Installer les dépendances Python
RUN pip install --upgrade pip && pip install -r requirements.txt

# Port utilisé par Railway (ou 5000 par défaut en local)
ENV PORT=5000

# Commande de démarrage
CMD ["gunicorn", "app:app", "--bind", "0.0.0.0:5000"]

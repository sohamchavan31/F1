"""
Django settings for F1 Replay backend.
"""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "dev-insecure-key-change-in-prod")

DEBUG = os.getenv("DEBUG", "1") == "1"

ALLOWED_HOSTS = os.getenv("ALLOWED_HOSTS", "localhost 127.0.0.1").split()

INSTALLED_APPS = [
    "django.contrib.staticfiles",
    "rest_framework",
    "channels",
    "api",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.common.CommonMiddleware",
]

ROOT_URLCONF = "f1_project.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {"context_processors": []},
    }
]

WSGI_APPLICATION = "f1_project.wsgi.application"
ASGI_APPLICATION  = "f1_project.asgi.application"

# ── MongoDB ───────────────────────────────────────────────────────────────────
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
F1_DB_NAME = os.getenv("F1_DB_NAME", "f1_replay")

# ── Django Channels — Redis channel layer ─────────────────────────────────────
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [REDIS_URL],
        },
    }
}

# ── DRF ───────────────────────────────────────────────────────────────────────
REST_FRAMEWORK = {
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_PARSER_CLASSES":   ["rest_framework.parsers.JSONParser"],
}

STATIC_URL = "/static/"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

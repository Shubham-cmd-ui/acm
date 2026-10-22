"""
Django settings for doc_intel_rag project.
AI-Powered Document Intelligence Assistant using RAG & Gemini API.
"""

from pathlib import Path
import os
import environ

# Base Directory: Points to root doc_intel_rag/
BASE_DIR = Path(__file__).resolve().parent.parent

# Initialize environment variables
env = environ.Env(
    DEBUG=(bool, True),
    SECRET_KEY=(str, 'django-insecure-rag-dev-key-change-in-production-12345'),
    ALLOWED_HOSTS=(list, ['127.0.0.1', 'localhost', '*']),
    GEMINI_API_KEY=(str, ''),
    GEMINI_GENERATION_MODEL=(str, 'gemini-3.5-flash-lite'),
    GEMINI_EMBEDDING_MODEL=(str, 'gemini-embedding-001'),
    TOP_K_CHUNKS=(int, 4),
    CHUNK_SIZE=(int, 800),
    CHUNK_OVERLAP=(int, 150),
    SIMILARITY_THRESHOLD=(float, 0.35),
)

# Read .env file if it exists
env_file = BASE_DIR / '.env'
if env_file.exists():
    environ.Env.read_env(env_file)

# Core Security Settings
SECRET_KEY = env('SECRET_KEY')
DEBUG = env('DEBUG')
ALLOWED_HOSTS = env('ALLOWED_HOSTS')

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # Custom RAG application
    'rag_assistant.apps.RagAssistantConfig',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'doc_intel_rag.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'doc_intel_rag.wsgi.application'
ASGI_APPLICATION = 'doc_intel_rag.asgi.application'

# Database
# Default: SQLite3 for portability and zero configuration
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = '/static/'
STATICFILES_DIRS = [
    BASE_DIR / 'rag_assistant' / 'static',
]
STATIC_ROOT = BASE_DIR / 'staticfiles'

# Media files (Uploaded PDF/TXT documents & FAISS vector indices)
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'
VECTOR_INDEX_DIR = MEDIA_ROOT / 'indices'
DOCUMENTS_UPLOAD_DIR = MEDIA_ROOT / 'documents'

# Ensure media storage directories exist
os.makedirs(DOCUMENTS_UPLOAD_DIR, exist_ok=True)
os.makedirs(VECTOR_INDEX_DIR, exist_ok=True)

# Upload constraints (Increased to 50 MB)
DATA_UPLOAD_MAX_MEMORY_SIZE = 60 * 1024 * 1024       # 60 MB request body limit
FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024        # 5 MB RAM threshold (files > 5MB stream to disk to save memory)
MAX_UPLOAD_SIZE_MB = 50                              # Maximum document upload limit (50 MB)

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ==============================================================================
# RAG & Generative AI Configuration
# ==============================================================================
GEMINI_API_KEY = env('GEMINI_API_KEY', default=os.getenv('GEMINI_API_KEY', ''))
GEMINI_GENERATION_MODEL = env('GEMINI_GENERATION_MODEL')
GEMINI_EMBEDDING_MODEL = env('GEMINI_EMBEDDING_MODEL')

# RAG Pipeline Parameters
TOP_K_CHUNKS = env('TOP_K_CHUNKS')                   # Number of relevant chunks retrieved
CHUNK_SIZE = env('CHUNK_SIZE')                       # Character length of each text chunk
CHUNK_OVERLAP = env('CHUNK_OVERLAP')                 # Character overlap between adjacent chunks
SIMILARITY_THRESHOLD = env('SIMILARITY_THRESHOLD')   # Minimum cosine similarity confidence

"""
Django settings for autoworld_project.

Generated to match exactly:
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'autoworld_project.settings')
"""

from pathlib import Path
import os
import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent


# SECRET_KEY — use env var on Render, fallback for local dev
SECRET_KEY = os.environ.get('SECRET_KEY', 'django-insecure-your-secret-key')


# DEBUG — False on Render (set DEBUG=False in Render env vars)
DEBUG = os.environ.get('DEBUG', 'True') == 'True'

ALLOWED_HOSTS = [
    'localhost',
    '127.0.0.1',
    '192.168.1.194',
    '192.168.1.101',
    '192.168.1.103',
    '192.168.88.20',
    '10.26.70.28',
    '10.20.249.116',
    '.onrender.com',   # ← Render public domain (covers *.onrender.com)
]

# Also allow the RENDER_EXTERNAL_HOSTNAME env var Render sets automatically
RENDER_EXTERNAL_HOSTNAME = os.environ.get('RENDER_EXTERNAL_HOSTNAME')
if RENDER_EXTERNAL_HOSTNAME:
    ALLOWED_HOSTS.append(RENDER_EXTERNAL_HOSTNAME)  




INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'ecommerceapp',
    'authenticatorapp',
    'paymentapp',
    'aiapp',
    'widget_tweaks',
]

LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = '/redirect-after-login/'  # This should match the path for role-based redirection


MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',  # ← serve static files on Render
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'autoworld_project.urls'
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [ BASE_DIR / 'templates' ],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',

                
                'ecommerceapp.context_processors.user_roles',
            ],
        },
    },
]

WSGI_APPLICATION = 'autoworld_project.wsgi.application'




DATABASES = {
    'default': dj_database_url.config(
        # On Render: DATABASE_URL env var is set automatically by the PostgreSQL add-on
        # Locally: falls back to your local PostgreSQL
        default='postgresql://postgres:delta@localhost:5432/autoworld_db',
        conn_max_age=600,
    )
}




AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]




LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True




STATIC_URL = '/static/'
STATICFILES_DIRS = [ BASE_DIR / 'static' ]
STATIC_ROOT = BASE_DIR / 'staticfiles'

# WhiteNoise — compressed static file storage for production (Django 5 syntax)
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}



MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'




DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

STRIPE_PUBLIC_KEY = "pk_test_xxxxxxxxxxx"
STRIPE_SECRET_KEY = "sk_test_xxxxxxxxxxx"
STRIPE_WEBHOOK_SECRET = "whsec_xxxxxxxxxxx"



PAYPAL_CLIENT_ID = 'your_sandbox_client_id'
PAYPAL_SECRET = 'your_sandbox_secret'
PAYPAL_BASE_URL = "https://api-m.sandbox.paypal.com"  


STRIPE_SECRET_KEY = 'your_stripe_secret_key'
STRIPE_PUBLIC_KEY = 'your_stripe_public_key'

MPESA_CONSUMER_KEY = os.environ.get('MPESA_CONSUMER_KEY', '')
MPESA_CONSUMER_SECRET = os.environ.get('MPESA_CONSUMER_SECRET', '')
MPESA_BASE_URL = 'https://sandbox.safaricom.co.ke'
MPESA_SHORTCODE = os.environ.get('MPESA_SHORTCODE', '174379')
MPESA_PASSKEY = os.environ.get('MPESA_PASSKEY', '')
MPESA_CALLBACK_URL = os.environ.get('MPESA_CALLBACK_URL', 'https://your-app.onrender.com/payment/callback/')





# Email backend (Gmail SMTP)
# To enable: replace with your Gmail address and App Password
# Get App Password: Google Account → Security → 2-Step Verification → App Passwords
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_USE_TLS = True
EMAIL_PORT = 587
EMAIL_HOST_USER = 'yourautoworldemail@gmail.com'      # ← Replace with your Gmail
EMAIL_HOST_PASSWORD = 'your-app-password'              # ← Replace with Gmail App Password
DEFAULT_FROM_EMAIL = f'AutoWorld <{EMAIL_HOST_USER}>'




AFRICASTALKING_USERNAME = 'your_username'
AFRICASTALKING_API_KEY = 'your_api_key'

# ── Groq AI ──────────────────────────────────────────────────────────────────
# Get your free key at https://console.groq.com → API Keys
GROQ_API_KEY = os.environ.get('GROQ_API_KEY', '')  # Set in Render env vars
GROQ_MODEL = 'llama-3.1-8b-instant'          # Fast model for customer chatbot
GROQ_MODEL_SMART = 'llama-3.3-70b-versatile'  # Smart model for admin insights

# Forecasting model max age before falling back to live-fit (days)
FORECAST_MODEL_MAX_AGE_DAYS = 7

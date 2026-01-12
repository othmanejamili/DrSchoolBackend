"""
Django settings for Drive project.
"""

from pathlib import Path
import os
import sys
import cloudinary
import cloudinary.uploader
import cloudinary.api

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# ============================================
# SECURITY & ENVIRONMENT
# ============================================

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', 'django-insecure-1tty#9$2&-+8ay(y3e99odwcmv-)y=#%m@pt=8ysevn4a*93i8')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.environ.get('DEBUG', 'False') == 'True'

ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')

# Detect if we're running tests
TESTING = 'test' in sys.argv

# ============================================
# APPLICATION DEFINITION
# ============================================

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'corsheaders',
    'django_ratelimit',
    'django_filters',
    'django_extensions',
    'cloudinary',
    'cloudinary_storage',
    'DriveApp',
]

# Conditionally add debug_toolbar only in development
if DEBUG and not TESTING:
    INSTALLED_APPS.insert(0, 'debug_toolbar')

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

# Add debug toolbar middleware only in development
if DEBUG and not TESTING:
    MIDDLEWARE.insert(0, 'debug_toolbar.middleware.DebugToolbarMiddleware')

# ============================================
# CLOUDINARY CONFIGURATION
# ============================================

cloudinary.config(
    cloud_name=os.environ.get('CLOUDINARY_CLOUD_NAME', 'dsfgsdjgz'),
    api_key=os.environ.get('CLOUDINARY_API_KEY', '551648374292981'),
    api_secret=os.environ.get('CLOUDINARY_API_SECRET', 'KmgyWi_QVc4xmvNj4Fe9Pj1JDyU'),
    secure=True
)

DEFAULT_FILE_STORAGE = 'cloudinary_storage.storage.MediaCloudinaryStorage'
STATICFILES_STORAGE = 'cloudinary_storage.storage.StaticHashedCloudinaryStorage'

MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')
STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

SESSION_SERIALIZER = 'django.contrib.sessions.serializers.JSONSerializer'

# ============================================
# DEBUG TOOLBAR SETTINGS
# ============================================

if DEBUG and not TESTING:
    DEBUG_TOOLBAR_CONFIG = {
        'SHOW_TOOLBAR_CALLBACK': lambda request: True,
        'RESULTS_CACHE_SIZE': 100,
        'SHOW_COLLAPSED': True,
        'IS_RUNNING_TESTS': False,  # Explicitly disable during tests
    }
    INTERNAL_IPS = ['127.0.0.1', 'localhost']
else:
    DEBUG_TOOLBAR_CONFIG = {
        'IS_RUNNING_TESTS': True,
    }

# ============================================
# URL & TEMPLATE CONFIGURATION
# ============================================

ROOT_URLCONF = 'Drive.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'Drive.wsgi.application'

# ============================================
# DATABASE CONFIGURATION
# ============================================

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': os.environ.get('DB_NAME', 'SaasDjango'),
        'USER': os.environ.get('DB_USER', 'root'),
        'PASSWORD': os.environ.get('DB_PASSWORD', 'Othmane491!'),
        'HOST': os.environ.get('DB_HOST', '127.0.0.1'),
        'PORT': os.environ.get('DB_PORT', '3306'),
        'CONN_MAX_AGE': 600,
        'OPTIONS': {
            'connect_timeout': 10,
        }
    }
}

# ============================================
# CORS SETTINGS
# ============================================

CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:5173",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173",
]

CORS_ALLOW_CREDENTIALS = True

# ============================================
# REST FRAMEWORK SETTINGS
# ============================================

# Base throttling rates
THROTTLE_RATES_BASE = {
    # General rates
    'anon': '100/hour',
    'user': '1000/hour',
    
    # Authentication endpoints
    'login': '5/minute',
    'register': '10/hour',
    
    # School endpoints
    'school': '200/hour',
    'school_create': '10/hour',
    'school_users': '60/minute',
    
    # Student profile endpoints
    'student_progress': '100/hour',
    'student_progress_update': '30/hour',
    'student_performance_prediction': '50/hour',
    
    # Other endpoints
    'stats': '30/minute',
    'burst': '60/minute',
    'ip_based': '500/hour',
}

# Adjust rates based on environment
if DEBUG:
    THROTTLE_RATES = {k: v.replace('/hour', '/minute').replace('/minute', '/second') 
                      for k, v in THROTTLE_RATES_BASE.items()}
    THROTTLE_RATES.update({
        'user': '10000/hour',
        'register': '100/hour',
        'student_progress_update': '1000/hour',
    })
elif TESTING:
    # Very high limits for testing
    THROTTLE_RATES = {
        'anon': '1000/minute',
        'user': '10000/minute',
        'login': '100/minute',
        'register': '100/minute',
        'student_progress': '100/minute',
        'student_progress_update': '100/minute',
        'student_performance_prediction': '100/minute',
        'school': '1000/minute',
        'school_create': '100/minute',
        'stats': '100/minute',
    }
else:
    # Production - stricter
    THROTTLE_RATES = THROTTLE_RATES_BASE.copy()
    THROTTLE_RATES.update({
        'anon': '50/hour',
        'user': '500/hour',
        'register': '5/hour',
    })

REST_FRAMEWORK = {
    # Pagination
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 50,
    
    # Authentication
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.SessionAuthentication',
        'rest_framework.authentication.TokenAuthentication',
    ],
    
    # Permissions
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    
    # Throttling (Rate Limiting)
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': THROTTLE_RATES,
    
    # Filtering
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ],
    
    # Error handling
    'EXCEPTION_HANDLER': 'rest_framework.views.exception_handler',
    
    # Renderer classes
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
        'rest_framework.renderers.BrowsableAPIRenderer' if DEBUG else 'rest_framework.renderers.JSONRenderer',
    ],
}

# ============================================
# PASSWORD VALIDATION
# ============================================

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
        'OPTIONS': {
            'min_length': 8,
        }
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# ============================================
# INTERNATIONALIZATION
# ============================================

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# ============================================
# STATIC FILES
# ============================================

STATIC_URL = '/static/'
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'
STATIC_ROOT = BASE_DIR / 'staticfiles'

# ============================================
# DEFAULT AUTO FIELD
# ============================================

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
AUTH_USER_MODEL = 'DriveApp.User'

# ============================================
# CELERY CONFIGURATION
# ============================================

CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL', 'redis://localhost:6379/0')
CELERY_RESULT_BACKEND = os.environ.get('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'UTC'
CELERY_ENABLE_UTC = True
CELERY_RESULT_EXPIRES = 3600
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_SEND_SENT_EVENT = True
CELERY_WORKER_SEND_TASK_EVENTS = True

# ============================================
# EMAIL CONFIGURATION
# ============================================

EMAIL_BACKEND = os.environ.get('EMAIL_BACKEND', 'django.core.mail.backends.console.EmailBackend')
EMAIL_HOST = os.environ.get('EMAIL_HOST', 'smtp.gmail.com')
EMAIL_PORT = int(os.environ.get('EMAIL_PORT', 587))
EMAIL_USE_TLS = os.environ.get('EMAIL_USE_TLS', 'True') == 'True'
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', 'othmanejamili19@gmail.com')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', 'xldajgfebylgdhsa')
DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', 'othmanejamili19@gmail.com')

# ============================================
# RATE LIMITING CONFIGURATION
# ============================================

RATELIMIT_ENABLE = not TESTING  # Disable during tests
RATELIMIT_USE_CACHE = 'default'

# ============================================
# CACHE CONFIGURATION
# ============================================

# Use different Redis database for testing
if TESTING:
    redis_db = '2'
else:
    redis_db = os.environ.get('REDIS_DB', '1')

CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': os.environ.get('REDIS_URL', f'redis://127.0.0.1:6379/{redis_db}'),
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            'CONNECTION_POOL_KWARGS': {
                'max_connections': 100 if not TESTING else 10,
                'retry_on_timeout': True,
            },
            'SOCKET_CONNECT_TIMEOUT': 5,
            'SOCKET_TIMEOUT': 5,
            'COMPRESSOR': 'django_redis.compressors.zlib.ZlibCompressor',
            'IGNORE_EXCEPTIONS': True,
        },
        'KEY_PREFIX': 'driving_school_test' if TESTING else 'driving_school',
        'TIMEOUT': 300,
    }
}

# ============================================
# LOGGING CONFIGURATION
# ============================================

# Create logs directory if it doesn't exist
LOGS_DIR = os.path.join(BASE_DIR, 'logs')
os.makedirs(LOGS_DIR, exist_ok=True)

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
        'file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': os.path.join(LOGS_DIR, 'django.log'),
            'maxBytes': 1024 * 1024 * 10,
            'backupCount': 5,
            'formatter': 'verbose',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': True,
        },
        'django.db.backends': {
            'handlers': ['console'],
            'level': 'WARNING',
            'propagate': False,
        },
        'django.request': {
            'handlers': ['console', 'file'],
            'level': 'ERROR',
            'propagate': False,
        },
        'django_ratelimit': {
            'handlers': ['console'],
            'level': 'WARNING',
            'propagate': False,
        },
        'django.core.cache': {
            'handlers': ['console'],
            'level': 'DEBUG' if DEBUG else 'WARNING',
            'propagate': False,
        },
        'DriveApp': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False,
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'WARNING',
    },
}

# Enable SQL logging in debug mode
if DEBUG:
    LOGGING['loggers']['django.db.backends']['level'] = 'DEBUG'

# ============================================
# SECURITY SETTINGS
# ============================================

# Basic security settings (enabled in production)
if not DEBUG:
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = 'DENY'
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 31536000  # 1 year
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True

# ============================================
# CUSTOM SETTINGS
# ============================================

# Cache timeouts in seconds
CACHE_TIMEOUTS = {
    # User-related caches
    'user_queryset': 60 * 5,
    'user_stats': 60 * 10,
    'school_users': 60 * 3,
    
    # School-related caches
    'schools_queryset': 60 * 5,
    'school_data': 60 * 30,
    'school_student_count': 60 * 5,
    
    # Student profile caches
    'student_profile': 60 * 5,
    'student_progress': 60 * 2,
    'student_prediction': 60 * 10,
    'my_profile': 60 * 3,
    
    # Default
    'default': 60 * 5,
}

# Maximum file upload size (10MB)
DATA_UPLOAD_MAX_MEMORY_SIZE = 10485760  # 10MB
FILE_UPLOAD_MAX_MEMORY_SIZE = 10485760  # 10MB

# ============================================
# TEST SETTINGS OVERRIDE
# ============================================

if TESTING:
    # Use faster password hasher for tests
    PASSWORD_HASHERS = [
        'django.contrib.auth.hashers.MD5PasswordHasher',
    ]
    
    # Use local memory cache for faster tests
    CACHES['default'] = {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'unique-snowflake',
    }
    
    # Disable email sending during tests
    EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'
    
    # Disable rate limiting during tests
    RATELIMIT_ENABLE = False
    
    # Use console logging only
    LOGGING['handlers'] = {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        }
    }
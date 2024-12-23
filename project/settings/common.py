import os
from datetime import datetime, timezone

# AFLABS PROJECT SETTINGS
PROJECT_NAME = "Flare Data Availability Client"
PROJECT_SETTINGS = os.environ.get("DJANGO_SETTINGS_MODULE", "project.settings.local")
PROJECT_COMMIT_HASH = "local"
PROJECT_VERSION = "local"
PROJECT_BUILD_DATE = datetime.now(tz=timezone.utc)

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# DJANGO CORE SETTINGS

# A list of strings representing the host/domain names that this Django site can serve.
# This is a security measure to prevent HTTP Host header attacks, which are possible
# even under many seemingly-safe web server configurations.
ALLOWED_HOSTS = []

# database connection
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("DB_NAME", ""),
        "USER": os.environ.get("DB_USER", ""),
        "PASSWORD": os.environ.get("DB_PASSWORD", ""),
        "HOST": os.environ.get("DB_HOST", "db"),
        "PORT": os.environ.get("DB_PORT", "5432"),
    }
}

# logging
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {
            "()": "django.utils.log.ServerFormatter",
            "format": "[{server_time}] {levelname} {name}: {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stderr",
            "formatter": "default",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": os.environ.get("LOG_LEVEL", "INFO"),
    },
}

# Start app in debug mode. This shows more detailed error messages. Should not be used
# in production
DEBUG = False

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

INSTALLED_APPS = [
    # builtin
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.postgres",
    # dependencies
    "rest_framework",
    "corsheaders",
    "drf_spectacular",
    # our apps
    "ftso.apps.FtsoConfig",
    "fsp.apps.FspConfig",
    "fdc.apps.FdcConfig",
]

LANGUAGE_CODE = "en-us"

MEDIA_URL = "/media/"

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "project.urls"

SECRET_KEY = os.environ.get("SECRET_KEY", "RUNNING_IN_LOCAL_MODE")

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [os.path.join(BASE_DIR, "django_templates")],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]


TIME_ZONE = "Europe/Ljubljana"

USE_I18N = True

USE_TZ = True

WSGI_APPLICATION = "project.wsgi.application"

# END OF DJANGO CORE

# STATIC FILES

STATIC_URL = "/static/"

# END OF STATIC FILES

# DEPENDENCY SETTINGS

# djangorestframework
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (),
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}

# drf-spectacular
SPECTACULAR_SETTINGS = {
    "TITLE": f"{PROJECT_NAME} API",
    "DESCRIPTION": f"Api documentation for {PROJECT_NAME}",
    "VERSION": "1.0.0",
    "SCHEMA_PATH_PREFIX": r"/api/v[0-9]",
    "ENUM_ADD_EXPLICIT_BLANK_NULL_CHOICE": False,
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
}

# django-types
from django.db.models.query import QuerySet

for cls in [QuerySet]:
    cls.__class_getitem__ = classmethod(lambda cls, *args, **kwargs: cls)  # type: ignore [attr-defined]

# END OF DEPENDENCY SETTINGS

CONFIG_MODULE = os.environ.get("CONFIG_MODULE", None)

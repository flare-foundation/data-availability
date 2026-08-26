import os
from datetime import UTC, datetime

# AFLABS PROJECT SETTINGS
PROJECT_NAME = "Flare Data Availability Client"
PROJECT_SETTINGS = os.environ.get("DJANGO_SETTINGS_MODULE", "project.settings.local")
PROJECT_COMMIT_HASH = "local"
PROJECT_VERSION = "local"
PROJECT_BUILD_DATE = datetime.now(tz=UTC)

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
        "OPTIONS": {
            "pool": True,
        },
    }
}

# logging
LOG_FORMAT = os.environ.get("LOG_FORMAT", "default")
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {
        "caller": {
            "()": "project.logging.CallerFilter",
        },
    },
    "formatters": {
        "default": {
            "format": "[{timestamp}] [{datetime}] {levelname} {caller}: {message}",
            "style": "{",
        },
        "json": {
            "()": "pythonjsonlogger.json.JsonFormatter",
            "fmt": "%(timestamp)s %(datetime)s %(levelname)s %(caller)s %(message)s",
            "rename_fields": {
                "levelname": "level",
            },
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stderr",
            "formatter": LOG_FORMAT,
            "filters": ["caller"],
        },
    },
    "root": {
        "handlers": ["console"],
        "level": LOG_LEVEL,
    },
}

# caching
REDIS_HOST = os.environ.get("REDIS_HOST")
REDIS_PORT = os.environ.get("REDIS_PORT")
REDIS_USERNAME = os.environ.get("REDIS_USERNAME")
REDIS_PASSWORD = os.environ.get("REDIS_PASSWORD")

_locmem_cache = {
    "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
    "LOCATION": "fallback",
}

_redis_configured = REDIS_HOST and REDIS_PORT

_redis_location = ""
if _redis_configured and REDIS_USERNAME and REDIS_PASSWORD:
    _redis_location = (
        f"redis://{REDIS_USERNAME}:{REDIS_PASSWORD}@{REDIS_HOST}:{REDIS_PORT}"
    )
elif _redis_configured:
    _redis_location = f"redis://{REDIS_HOST}:{REDIS_PORT}"

CACHES = {"fallback": _locmem_cache}

if _redis_configured:
    CACHES["default"] = {"BACKEND": "project.cache.FallbackCache"}
    CACHES["redis"] = {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": _redis_location,
        "OPTIONS": {
            "socket_connect_timeout": 2,
            "socket_timeout": 2,
        },
    }
else:
    CACHES["default"] = _locmem_cache

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
    "dal.apps.DalConfig",
]

# The c-chain indexer this service READS from. Deliberately not a Django
# database alias: the schema is managed by gorm in another repository, and an
# alias would invite `migrate` and the test runner to create and own it.
CCHAIN_INDEXER = {
    "HOST": os.environ.get("CCHAIN_DB_HOST", ""),
    "PORT": int(os.environ.get("CCHAIN_DB_PORT", "3306")),
    "NAME": os.environ.get("CCHAIN_DB_NAME", ""),
    "USER": os.environ.get("CCHAIN_DB_USER", ""),
    "PASSWORD": os.environ.get("CCHAIN_DB_PASSWORD", ""),
}

# The chain the DAL's signature checks are bound to. chainId is INSIDE every
# signed payload, so this is the value that stops artifacts signed for one
# network being admitted on another. Read straight from DAL_RPC_URL (falling
# back to RPC_URL) rather than through configuration.config: that builds the
# whole FTSO/FDC configuration -- Relay resolution, epoch factories, provider
# lists -- and refuses any chain outside the four public ones, none of which the
# DAL needs or should be constrained by.
DAL_RPC_URL = os.environ.get("DAL_RPC_URL", os.environ.get("RPC_URL", ""))

# The UtxoInstructionChannel carrying the proposer registry. Read at latest for
# endpoints, and AT A GENERATION for membership.
DAL_CHANNEL_ADDRESS = os.environ.get("DAL_CHANNEL_ADDRESS", "")
_DAL_CHAIN_ID = os.environ.get("DAL_CHAIN_ID", "")
DAL_CHAIN_ID = int(_DAL_CHAIN_ID) if _DAL_CHAIN_ID else None

# How long an expectation stays open before it is closed as UNMET. Configurable
# because it is a statement about how patient a deployment is with its origins,
# not a constant -- and because a harness that must observe the give-up path
# cannot wait half an hour to see it.
DAL_GIVE_UP_MINUTES = int(os.environ.get("DAL_GIVE_UP_MINUTES", "30"))

# Origins on the local network are refused unless a deployment says otherwise.
# The end-to-end harness runs every TEE machine on loopback and needs this on;
# a public deployment must leave it off. Dangerous prefixes -- metadata
# addresses, multicast -- stay blocked either way.
DAL_ALLOW_PRIVATE_ORIGINS = (
    os.environ.get("DAL_ALLOW_PRIVATE_ORIGINS", "").lower() == "true"
)

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
    "project.debug.debug_error_middleware",
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
    "DEFAULT_RENDERER_CLASSES": ("rest_framework.renderers.JSONRenderer",),
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

if os.environ.get("INJECT_SWAGGER_X_API_KEY_HEADER_AUTH", "false") == "true":
    SPECTACULAR_SETTINGS["APPEND_COMPONENTS"] = {
        "securitySchemes": {
            "ApiKeyAuth": {
                "type": "apiKey",
                "in": "header",
                "name": "x-api-key",
            }
        }
    }
    SPECTACULAR_SETTINGS["SECURITY"] = [{"ApiKeyAuth": []}]

# django-types
from django.db.models.query import QuerySet

for cls in [QuerySet]:
    cls.__class_getitem__ = classmethod(lambda cls, *args, **kwargs: cls)  # type: ignore [attr-defined]

# END OF DEPENDENCY SETTINGS

# when set, api key header value will be included in debug logs
DEBUG_LOG_API_KEY = os.environ.get("DEBUG_LOG_API_KEY", "false") == "true"

_HISTORY_KEEP_ROUNDS = os.environ.get("HISTORY_KEEP_ROUNDS", "")
try:
    HISTORY_KEEP_ROUNDS = int(_HISTORY_KEEP_ROUNDS)
except ValueError:
    HISTORY_KEEP_ROUNDS = None

from .common import *

DEBUG = True

ALLOWED_HOSTS = ["*"]

# for faster tests
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

SEND_EMAIL_CONFIRMATIONS = False

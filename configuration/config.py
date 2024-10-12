import importlib

from django.conf import settings

from configuration.types import Configuration

config: Configuration = importlib.import_module(f".{settings.CONFIG_MODULE}", "configuration.configs").get_config()

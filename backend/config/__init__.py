"""Configuration package for IntelliHostel."""
from backend.config.settings import *
import backend.config.settings as settings

__all__ = [name for name in dir(settings) if not name.startswith("_")]

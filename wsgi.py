"""Entrada WSGI para el servidor web."""

from app import app as application

app = application

__all__ = ["app", "application"]
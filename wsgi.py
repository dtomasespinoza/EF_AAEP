"""
  wsgi.py
  =======

  Punto de entrada WSGI para servidores de produccion.

  En desarrollo se ejecuta `python app.py`, que arranca el servidor de
  desarrollo de Flask. Eso NO se debe usar en produccion: es de un solo
  proceso, muestra errores internos y no aguanta varias peticiones a la vez.

  Este archivo expone el mismo objeto `app` de Flask como `application`,
  que es el nombre que esperan Gunicorn, uWSGI y el panel de
  PythonAnywhere:

      gunicorn wsgi:application

  En PythonAnywhere basta con indicar este archivo en el campo
  "WSGI configuration file" del panel web.

  Importarlo NO arranca ningun servidor: solo crea la aplicacion. Por eso
  se puede importar sin efectos secundarios en pruebas, Gunicorn o produccion.
"""

from app import app as application

# Alias habitual en la documentacion de Flask. Se deja el mismo objeto bajo
# los dos nombres para que cualquiera de los dos sirva.
app = application

__all__ = ["app", "application"]
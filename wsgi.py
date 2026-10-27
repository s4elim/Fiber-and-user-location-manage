"""WSGI entry point for production hosting.

PythonAnywhere, gunicorn, uWSGI and other WSGI servers import this module
instead of running ``app.py`` directly. Keep this file at the project root.

Local development still works the old way:  python app.py
"""

import os
import sys

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)

from app import app as application  # noqa: E402  (path setup must run first)

__all__ = ["application"]

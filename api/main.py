"""Entrypoint for Vercel's services runtime, which expects the ASGI app
at the api service root. The app itself lives in app/main.py; this puts
the api folder on the path and re-exports it. Local and Docker runs
use app.main directly.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.main import app  # noqa: E402,F401

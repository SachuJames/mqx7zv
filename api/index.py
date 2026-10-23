"""Vercel entry point. The real app lives in app/main.py; this just
puts the api folder on the path and re-exports it so Vercel's Python
runtime finds the ASGI app. Local and Docker runs use app.main directly.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.main import app  # noqa: E402,F401

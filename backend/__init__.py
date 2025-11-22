"""
Compatibility wrapper so hosted platforms that still invoke `python backend/main.py`
will start the Telegram bot (backend package no longer contains API code).
"""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))


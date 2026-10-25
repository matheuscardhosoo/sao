#!/usr/bin/env python3
"""
Underworld (SAO) Management CLI Shortcut
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "scripts"))

from scripts.manage import main

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Keep the plugin CLI path available for existing installations."""

from pathlib import Path
import runpy
import sys


if __name__ == "__main__":
    skill = Path(__file__).resolve().parents[1] / "skills" / "qingan-initiative-civil-service-examination-sprint-coach"
    scripts = skill / "scripts"
    sys.path.insert(0, str(scripts))
    runpy.run_path(str(scripts / "qingan.py"), run_name="__main__")

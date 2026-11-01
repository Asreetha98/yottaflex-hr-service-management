"""Deterministic synthetic data generator for the HR service platform (seed 20261022).

The generator reuses the stdlib-only rule engines from ``backend/app/rules`` so the
stored ticket decisions are exactly what the platform would produce, while the
ground truth is derived from the generation templates (independent of the engines).
"""

import os
import sys

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND_DIR = os.path.join(ROOT_DIR, "backend")
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

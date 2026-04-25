import os
import sys

# Ensure the api/ directory is on the path so vercel_app can be imported
# regardless of how Vercel resolves module paths.
sys.path.insert(0, os.path.dirname(__file__))

from vercel_app import app  # noqa: E402 — intentional late import after path fix

__all__ = ["app"]


"""
Vercel Serverless Function entry point for doc_intel_rag Django project.
"""
import os
import sys
from pathlib import Path

# Ensure project root is in sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'doc_intel_rag.settings')

from doc_intel_rag.wsgi import application, app

"""
WSGI config for doc_intel_rag project.
"""
import os
from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'doc_intel_rag.settings')
application = get_wsgi_application()

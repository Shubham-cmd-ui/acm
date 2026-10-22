"""
WSGI config for doc_intel_rag project.
Configured for local development and Vercel serverless deployment.
"""
import os
from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'doc_intel_rag.settings')

application = get_wsgi_application()
app = application

# Auto-migrate SQLite database in Vercel serverless container on cold start
if os.environ.get('VERCEL'):
    try:
        from django.core.management import call_command
        from django.db import connection
        tables = connection.introspection.table_names()
        if 'rag_assistant_document' not in tables:
            call_command('migrate', interactive=False)
    except Exception as e:
        print("Vercel auto-migration status:", e)

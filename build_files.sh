#!/bin/bash
# Vercel Build Script for doc_intel_rag Django project

echo "--> Installing Python dependencies..."
python3 -m pip install -r requirements.txt

echo "--> Collecting static files..."
python3 manage.py collectstatic --noinput --clear

echo "--> Applying database migrations..."
python3 manage.py migrate --noinput || true

echo "--> Build completed successfully!"

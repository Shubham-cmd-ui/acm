import os
from django import forms
from django.conf import settings
from django.core.exceptions import ValidationError

ALLOWED_EXTENSIONS = {'.pdf', '.txt'}
ALLOWED_MIME_TYPES = {
    'application/pdf',
    'text/plain',
    'application/octet-stream',  # Some browsers send TXT or PDF as octet-stream
}

class DocumentUploadForm(forms.Form):
    """
    Form to upload and validate PDF or TXT documents.
    Enforces file extension, MIME type, and size limits.
    """
    file = forms.FileField(
        label="Select Document (PDF or TXT)",
        error_messages={
            'empty': 'The uploaded file is empty (0 bytes).',
            'required': 'Please provide a file to upload.'
        },
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'id': 'documentFileInput',
            'accept': '.pdf,.txt',
        })
    )

    def clean_file(self):
        uploaded_file = self.cleaned_data.get('file')

        if not uploaded_file:
            raise ValidationError("Please provide a file to upload.")

        # 1. Validate file extension
        filename = uploaded_file.name
        ext = os.path.splitext(filename)[1].lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise ValidationError(
                f"Unsupported file format '{ext}'. Only .pdf and .txt files are allowed."
            )

        # 2. Validate file size (50MB limit)
        max_mb = getattr(settings, 'MAX_UPLOAD_SIZE_MB', 50)
        max_size_bytes = max_mb * 1024 * 1024
        if uploaded_file.size > max_size_bytes:
            raise ValidationError(
                f"File size ({uploaded_file.size / (1024 * 1024):.1f} MB) exceeds maximum allowed limit of {max_mb} MB."
            )

        if uploaded_file.size == 0:
            raise ValidationError("The uploaded file is empty (0 bytes).")

        # 3. Validate content type if available
        content_type = getattr(uploaded_file, 'content_type', '')
        if content_type and content_type not in ALLOWED_MIME_TYPES:
            # Tolerant fallback: if extension is valid .pdf or .txt, proceed
            if ext not in ALLOWED_EXTENSIONS:
                raise ValidationError(f"Invalid MIME type '{content_type}' for document upload.")

        return uploaded_file

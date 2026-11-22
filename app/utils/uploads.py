import os
import uuid
from pathlib import Path
from werkzeug.utils import secure_filename
from flask import current_app

def allowed_file(filename):
    if not filename or '.' not in filename:
        return False
    ext = filename.rsplit('.', 1)[1].lower()
    return ext in current_app.config['ALLOWED_EXTENSIONS']

def save_uploaded_file(file_storage):
    """
    Validates and securely saves an uploaded file to the configured UPLOAD_FOLDER.
    Returns a dict with saved file details or raises ValueError.
    """
    if not file_storage or file_storage.filename == '':
        raise ValueError("No file selected.")

    original_filename = secure_filename(file_storage.filename)
    if not allowed_file(original_filename):
        allowed_list = ", ".join(sorted(current_app.config['ALLOWED_EXTENSIONS']))
        raise ValueError(f"File type not permitted. Allowed extensions: {allowed_list}")

    upload_folder = current_app.config['UPLOAD_FOLDER']
    os.makedirs(upload_folder, exist_ok=True)

    # Generate a unique stored filename
    ext = original_filename.rsplit('.', 1)[1].lower()
    unique_filename = f"{uuid.uuid4().hex}_{original_filename}"
    file_path = os.path.join(upload_folder, unique_filename)

    file_storage.save(file_path)
    file_size = os.path.getsize(file_path)

    max_size = current_app.config.get('MAX_CONTENT_LENGTH', 16 * 1024 * 1024)
    if file_size > max_size:
        os.remove(file_path)
        raise ValueError(f"File exceeds maximum allowed size of {max_size / (1024*1024):.0f}MB.")

    mime_type = file_storage.mimetype or 'application/octet-stream'

    return {
        'filename': unique_filename,
        'original_filename': original_filename,
        'file_path': file_path,
        'file_size': file_size,
        'mime_type': mime_type
    }

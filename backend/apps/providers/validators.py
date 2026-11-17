from pathlib import Path

from django.core.exceptions import ValidationError

MAX_DOCUMENT_BYTES = 5 * 1024 * 1024  # 5 MB

# extension -> the bytes a genuine file of that type starts with
_SIGNATURES = {
    ".pdf": b"%PDF-",
    ".jpg": b"\xff\xd8\xff",
    ".jpeg": b"\xff\xd8\xff",
    ".png": b"\x89PNG\r\n\x1a\n",
}


def validate_document_file(file):
    """PDF/JPG/PNG up to 5 MB, and the content must match the extension, so a
    renamed .exe or .html cannot be uploaded as 'id.pdf'."""
    signature = _SIGNATURES.get(Path(file.name).suffix.lower())
    if signature is None:
        raise ValidationError("Upload a PDF, JPG or PNG file.")
    if file.size > MAX_DOCUMENT_BYTES:
        raise ValidationError("File is too large (maximum 5 MB).")
    head = file.read(len(signature))
    file.seek(0)
    if not head.startswith(signature):
        raise ValidationError("The file content does not match its extension.")

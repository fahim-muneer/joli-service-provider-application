import os
from pathlib import Path

from django.conf import settings
from django.core.files.storage import FileSystemStorage


class PrivateStorage(FileSystemStorage):
    """Storage for sensitive uploads (provider ID documents).

    - Lives in PRIVATE_MEDIA_ROOT (default: <BASE_DIR>/private_media), which is NOT
      served by the web server and not under MEDIA_URL.
    - Has no public URL: `.url` raises. Files only leave through a view that
      checks permissions.
    The location is read from settings on every use, so tests can override it.
    """

    @property
    def base_location(self):
        root = getattr(settings, "PRIVATE_MEDIA_ROOT", None) or Path(settings.BASE_DIR) / "private_media"
        return str(root)

    @property
    def location(self):
        return os.path.abspath(self.base_location)

    @property
    def base_url(self):
        return None

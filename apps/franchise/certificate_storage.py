from django.conf import settings
from django.core.files.storage import FileSystemStorage


class PrivateCertificateStorage(FileSystemStorage):
    def __init__(self, **kwargs):
        kwargs.setdefault("file_permissions_mode", 0o600)
        kwargs.setdefault("directory_permissions_mode", 0o700)
        super().__init__(**kwargs)

    def url(self, name):
        raise ValueError("Certificate files are only available through authorized views.")


def get_certificate_storage():
    return PrivateCertificateStorage(
        location=settings.CERTIFICATE_STORAGE_ROOT,
        base_url="",
    )

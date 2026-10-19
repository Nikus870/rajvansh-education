from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.core.files.storage import Storage
from django.utils.module_loading import import_string


class PrivateCertificateStorage(FileSystemStorage):
    def __init__(self, **kwargs):
        kwargs.setdefault("file_permissions_mode", 0o600)
        kwargs.setdefault("directory_permissions_mode", 0o700)
        super().__init__(**kwargs)

    def url(self, name):
        raise ValueError("Certificate files are only available through authorized views.")


class PrivateStorageProxy(Storage):
    """Expose storage operations without exposing backend-generated public URLs."""

    def __init__(self, backend):
        self.backend = backend

    def _open(self, name, mode="rb"):
        return self.backend.open(name, mode)

    def _save(self, name, content):
        return self.backend.save(name, content)

    def delete(self, name):
        return self.backend.delete(name)

    def exists(self, name):
        return self.backend.exists(name)

    def listdir(self, path):
        return self.backend.listdir(path)

    def size(self, name):
        return self.backend.size(name)

    def path(self, name):
        path = getattr(self.backend, "path", None)
        if path is None:
            raise NotImplementedError("This certificate backend has no local filesystem path.")
        return path(name)

    def get_accessed_time(self, name):
        return self.backend.get_accessed_time(name)

    def get_created_time(self, name):
        return self.backend.get_created_time(name)

    def get_modified_time(self, name):
        return self.backend.get_modified_time(name)

    def url(self, name):
        raise ValueError("Certificate files are only available through authorized views.")


def get_certificate_storage():
    backend_path = settings.CERTIFICATE_STORAGE_BACKEND
    options = dict(settings.CERTIFICATE_STORAGE_OPTIONS)
    if backend_path == "apps.franchise.certificate_storage.PrivateCertificateStorage":
        options.setdefault("location", settings.CERTIFICATE_STORAGE_ROOT)
        options.setdefault("base_url", "")
    backend = import_string(backend_path)(**options)
    return PrivateStorageProxy(backend)

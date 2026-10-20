import uuid
import mimetypes
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.storage import FileSystemStorage, Storage
from django.http import FileResponse, Http404
from django.utils.deconstruct import deconstructible
from PIL import Image, UnidentifiedImageError


ALLOWED_PROFILE_IMAGE_FORMATS = {"JPEG", "PNG", "WEBP"}
PROFILE_IMAGE_EXTENSIONS = {
    ".jpg": "JPEG",
    ".jpeg": "JPEG",
    ".png": "PNG",
    ".webp": "WEBP",
}
MAX_PROFILE_IMAGE_SIZE = 5 * 1024 * 1024
MAX_PROFILE_IMAGE_PIXELS = 30_000_000


def validate_profile_image(upload):
    if upload.size > MAX_PROFILE_IMAGE_SIZE:
        raise ValidationError("Profile photos must be 5 MB or smaller.")

    extension = Path(upload.name).suffix.lower()
    if extension not in PROFILE_IMAGE_EXTENSIONS:
        raise ValidationError("Upload a JPEG, PNG, or WEBP image.")

    try:
        upload.seek(0)
        with Image.open(upload) as image:
            if (
                image.format not in ALLOWED_PROFILE_IMAGE_FORMATS
                or image.format != PROFILE_IMAGE_EXTENSIONS[extension]
            ):
                raise ValidationError(
                    "Upload a JPEG, PNG, or WEBP image."
                )
            if image.width * image.height > MAX_PROFILE_IMAGE_PIXELS:
                raise ValidationError(
                    "Profile photos must be 30 megapixels or smaller."
                )
            image.verify()
    except (
        Image.DecompressionBombError,
        UnidentifiedImageError,
        OSError,
        ValueError,
    ) as exc:
        raise ValidationError("Upload a valid JPEG, PNG, or WEBP image.") from exc
    finally:
        upload.seek(0)


def profile_image_upload_to(instance, filename):
    extension = Path(filename).suffix.lower()
    image_id = uuid.uuid4().hex
    if hasattr(instance, "role"):
        owner_id = instance.franchise_id
        image_type = "staff"
    elif hasattr(instance, "franchise_id"):
        owner_id = instance.franchise_id
        image_type = "students"
    else:
        owner_id = instance.pk or "pending"
        image_type = "owners"
    return f"{image_type}/{owner_id}/{image_id}{extension}"


@deconstructible
class PrivateProfileImageStorage(FileSystemStorage):
    def __init__(self, **kwargs):
        kwargs.setdefault("location", settings.PROFILE_IMAGE_STORAGE_ROOT)
        kwargs.setdefault("base_url", "")
        kwargs.setdefault("file_permissions_mode", 0o600)
        kwargs.setdefault("directory_permissions_mode", 0o700)
        super().__init__(**kwargs)

    def url(self, name):
        raise ValueError(
            "Profile images are only available through authorized views."
        )


class PrivateProfileImageStorageProxy(Storage):
    def __init__(self):
        self.backend = PrivateProfileImageStorage()

    def _open(self, name, mode="rb"):
        return self.backend.open(name, mode)

    def _save(self, name, content):
        return self.backend.save(name, content)

    def delete(self, name):
        return self.backend.delete(name)

    def exists(self, name):
        return self.backend.exists(name)

    def path(self, name):
        return self.backend.path(name)

    def size(self, name):
        return self.backend.size(name)

    def url(self, name):
        raise ValueError(
            "Profile images are only available through authorized views."
        )


def get_private_profile_image_storage():
    return PrivateProfileImageStorageProxy()


def serve_profile_image(image):
    if not image:
        raise Http404("Profile photo not found.")
    try:
        photo = image.storage.open(image.name, "rb")
    except FileNotFoundError as exc:
        raise Http404("Profile photo not found.") from exc

    content_type = mimetypes.guess_type(image.name)[0] or "application/octet-stream"
    response = FileResponse(photo, content_type=content_type)
    response["Cache-Control"] = "private, no-store"
    response["X-Content-Type-Options"] = "nosniff"
    return response

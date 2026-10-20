import logging
import secrets
import uuid
from io import BytesIO
from pathlib import Path

from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone
from PIL import Image, ImageOps, UnidentifiedImageError
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from .models import CertificateRequest
from .profile_images import MAX_PROFILE_IMAGE_PIXELS

logger = logging.getLogger(__name__)

CERTIFICATE_TEMPLATE_PATH = (
    Path(__file__).resolve().parent
    / "static"
    / "franchise"
    / "images"
    / "certificate_template.png"
)
CERTIFICATE_TEMPLATE_WIDTH = 1792
CERTIFICATE_TEMPLATE_HEIGHT = 2400
CERTIFICATE_PAGE_HEIGHT = 842


def _register_unicode_fonts():
    project_font_dir = (
        Path(__file__).resolve().parent
        / "static"
        / "franchise"
        / "fonts"
    )
    font_paths = (
        Path("C:/Windows/Fonts/Nirmala.ttf"),
        project_font_dir / "NotoSansDevanagari.ttf",
        Path("/usr/share/fonts/truetype/noto/NotoSansDevanagari-Regular.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    )
    bold_font_paths = (
        Path("C:/Windows/Fonts/NirmalaB.ttf"),
        Path("/usr/share/fonts/truetype/noto/NotoSansDevanagari-Bold.ttf"),
        project_font_dir / "NotoSansDevanagari.ttf",
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    )
    regular = next((path for path in font_paths if path.is_file()), None)
    bold = next((path for path in bold_font_paths if path.is_file()), None)
    if regular is None:
        raise FileNotFoundError("A Unicode font is required to generate certificates.")
    if "CertificateUnicode" not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont("CertificateUnicode", str(regular)))
        pdfmetrics.registerFont(
            TTFont("CertificateUnicode-Bold", str(bold or regular))
        )
    return "CertificateUnicode", "CertificateUnicode-Bold"


def _wrap_text(text, font_name, font_size, max_width):
    lines = []
    line = ""

    for word in text.split():
        if pdfmetrics.stringWidth(word, font_name, font_size) > max_width:
            if line:
                lines.append(line)
                line = ""
            chunk = ""
            for character in word:
                candidate = chunk + character
                if chunk and pdfmetrics.stringWidth(
                    candidate,
                    font_name,
                    font_size,
                ) > max_width:
                    lines.append(chunk)
                    chunk = character
                else:
                    chunk = candidate
            line = chunk
            continue

        candidate = f"{line} {word}".strip()
        if line and pdfmetrics.stringWidth(
            candidate,
            font_name,
            font_size,
        ) > max_width:
            lines.append(line)
            line = word
        else:
            line = candidate

    if line:
        lines.append(line)
    return lines


def _draw_fitted_field(
    document,
    text,
    font_name,
    *,
    scale,
    left_px,
    right_px,
    baseline_px,
    max_size,
    min_size=6.5,
    max_lines=6,
    leading=8,
    alignment="center",
):
    text = (text or "").strip()
    if not text:
        return

    max_width = (right_px - left_px) * scale
    font_size = max_size
    lines = _wrap_text(text, font_name, font_size, max_width)
    while len(lines) > max_lines and font_size > min_size:
        font_size = max(min_size, font_size - 0.5)
        lines = _wrap_text(text, font_name, font_size, max_width)
    if len(lines) > max_lines:
        raise ValueError("Certificate text does not fit its printed field.")

    x = left_px * scale
    if alignment == "center":
        x = (left_px + right_px) * scale / 2
    center_y = (
        CERTIFICATE_TEMPLATE_HEIGHT - baseline_px
    ) * scale
    document.setFont(font_name, font_size)
    first_baseline = center_y + (len(lines) - 1) * leading / 2
    for index, line in enumerate(lines):
        if alignment == "center":
            document.drawCentredString(
                x,
                first_baseline - index * leading,
                line,
                shaping=True,
            )
        else:
            document.drawString(
                x,
                first_baseline - index * leading,
                line,
                shaping=True,
            )


def _student_photo(student, certificate_request_id):
    if not student.profile_image:
        return None

    try:
        with student.profile_image.open("rb") as photo_file:
            with Image.open(photo_file) as photo:
                if photo.width * photo.height > MAX_PROFILE_IMAGE_PIXELS:
                    logger.warning(
                        "Student photo exceeds the image size limit for certificate request %s.",
                        certificate_request_id,
                    )
                    return None
                return ImageOps.fit(
                    photo.convert("RGB"),
                    (340, 500),
                    method=Image.Resampling.LANCZOS,
                    centering=(0.5, 0.38),
                )
    except FileNotFoundError:
        logger.warning(
            "Student photo is missing for certificate request %s.",
            certificate_request_id,
        )
    except (
        Image.DecompressionBombError,
        UnidentifiedImageError,
        OSError,
        ValueError,
    ):
        logger.warning(
            "Student photo could not be read for certificate request %s.",
            certificate_request_id,
            exc_info=True,
        )
    return None


def generate_certificate_pdf(certificate_request, verification_url):
    if not CERTIFICATE_TEMPLATE_PATH.is_file():
        raise FileNotFoundError(
            f"Certificate template is missing: {CERTIFICATE_TEMPLATE_PATH}"
        )

    with Image.open(CERTIFICATE_TEMPLATE_PATH) as template:
        if template.size != (
            CERTIFICATE_TEMPLATE_WIDTH,
            CERTIFICATE_TEMPLATE_HEIGHT,
        ):
            raise ValueError("Certificate template dimensions do not match the layout.")
        template_reader = ImageReader(template.copy())

    regular_font, bold_font = _register_unicode_fonts()
    scale = CERTIFICATE_PAGE_HEIGHT / CERTIFICATE_TEMPLATE_HEIGHT
    page_width = CERTIFICATE_TEMPLATE_WIDTH * scale
    output = BytesIO()
    document = canvas.Canvas(
        output,
        pagesize=(page_width, CERTIFICATE_PAGE_HEIGHT),
        pageCompression=1,
    )
    document.drawImage(
        template_reader,
        0,
        0,
        width=page_width,
        height=CERTIFICATE_PAGE_HEIGHT,
        mask="auto",
    )
    document.setFillColorRGB(0.09, 0.08, 0.08)

    student = certificate_request.student
    _draw_fitted_field(
        document,
        student.registration_number,
        regular_font,
        scale=scale,
        left_px=1300,
        right_px=1600,
        baseline_px=210,
        max_size=10,
        max_lines=2,
        alignment="left",
    )
    _draw_fitted_field(
        document,
        student.full_name,
        bold_font,
        scale=scale,
        left_px=205,
        right_px=1585,
        baseline_px=1139,
        max_size=19,
        min_size=8,
        leading=10,
    )
    _draw_fitted_field(
        document,
        student.guardian_name,
        regular_font,
        scale=scale,
        left_px=465,
        right_px=1585,
        baseline_px=1270,
        max_size=13,
        alignment="left",
    )
    _draw_fitted_field(
        document,
        student.course.name,
        regular_font,
        scale=scale,
        left_px=1095,
        right_px=1585,
        baseline_px=1398,
        max_size=12,
        alignment="left",
    )
    _draw_fitted_field(
        document,
        student.university.name if student.university_id else "",
        regular_font,
        scale=scale,
        left_px=465,
        right_px=1585,
        baseline_px=1525,
        max_size=12,
        alignment="left",
    )
    _draw_fitted_field(
        document,
        student.course.duration,
        regular_font,
        scale=scale,
        left_px=610,
        right_px=1585,
        baseline_px=1655,
        max_size=12,
        alignment="left",
    )
    _draw_fitted_field(
        document,
        certificate_request.issued_at.strftime("%d %B %Y")
        if certificate_request.issued_at
        else "",
        regular_font,
        scale=scale,
        left_px=490,
        right_px=790,
        baseline_px=2105,
        max_size=9,
        min_size=6,
        max_lines=1,
        alignment="left",
    )
    _draw_fitted_field(
        document,
        certificate_request.certificate_number,
        regular_font,
        scale=scale,
        left_px=375,
        right_px=790,
        baseline_px=2160,
        max_size=9,
        min_size=6,
        max_lines=1,
        alignment="left",
    )
    _draw_fitted_field(
        document,
        f"Verify this certificate: {verification_url}",
        regular_font,
        scale=scale,
        left_px=100,
        right_px=1692,
        baseline_px=2285,
        max_size=7,
        min_size=5,
        max_lines=1,
    )

    photo = _student_photo(student, certificate_request.pk)
    if photo is not None:
        photo_scale = page_width / CERTIFICATE_TEMPLATE_WIDTH
        photo_left = 1387 * photo_scale
        photo_bottom = (
            CERTIFICATE_TEMPLATE_HEIGHT - 653
        ) * photo_scale
        photo_width = 170 * photo_scale
        photo_height = 248 * photo_scale
        document.drawImage(
            ImageReader(photo),
            photo_left,
            photo_bottom,
            width=photo_width,
            height=photo_height,
            mask="auto",
        )

    document.showPage()
    document.save()
    return output.getvalue()


def approve_certificate_request(certificate_request_id, reviewer, verification_url):
    if (
        not reviewer.is_authenticated
        or not reviewer.is_active
        or not reviewer.is_superuser
    ):
        raise PermissionError("Only a superuser may approve certificate requests.")

    stored_name = None
    try:
        with transaction.atomic():
            certificate_request = (
                CertificateRequest.objects.select_for_update()
                .select_related(
                    "student",
                    "student__course",
                    "student__university",
                    "franchise",
                )
                .get(pk=certificate_request_id)
            )
            if certificate_request.status != CertificateRequest.STATUS_PENDING:
                raise ValueError("Only pending certificate requests can be approved.")
            if not certificate_request.eligibility_verified:
                raise ValueError("Verify course eligibility before approval.")
            if not certificate_request.eligibility_remarks.strip():
                raise ValueError("Record the eligibility evidence reviewed before approval.")
            if certificate_request.student.franchise_id != certificate_request.franchise_id:
                raise ValueError("The student is not registered under the requesting franchise.")

            now = timezone.now()
            certificate_request.certificate_number = (
                f"RGE-{now:%Y%m%d}-{uuid.uuid4().hex[:12].upper()}"
            )
            certificate_request.verification_token = secrets.token_urlsafe(32)
            certificate_request.issued_at = now.date()
            certificate_request.reviewed_by = reviewer
            certificate_request.reviewed_at = now

            pdf_data = generate_certificate_pdf(
                certificate_request,
                verification_url(certificate_request.verification_token),
            )
            certificate_request.certificate_file.save(
                f"{certificate_request.certificate_number}.pdf",
                ContentFile(pdf_data),
                save=False,
            )
            stored_name = certificate_request.certificate_file.name
            certificate_request.status = CertificateRequest.STATUS_APPROVED
            certificate_request.save(
                update_fields=(
                    "certificate_number",
                    "verification_token",
                    "issued_at",
                    "reviewed_by",
                    "reviewed_at",
                    "certificate_file",
                    "status",
                )
            )
            return certificate_request
    except Exception:
        if stored_name:
            storage = CertificateRequest._meta.get_field("certificate_file").storage
            try:
                if storage.exists(stored_name):
                    storage.delete(stored_name)
            except Exception:
                logger.exception(
                    "Could not remove incomplete certificate file %s after approval failed.",
                    stored_name,
                )
        raise


def reject_certificate_request(certificate_request_id, reviewer):
    if (
        not reviewer.is_authenticated
        or not reviewer.is_active
        or not reviewer.is_superuser
    ):
        raise PermissionError("Only a superuser may reject certificate requests.")

    with transaction.atomic():
        certificate_request = CertificateRequest.objects.select_for_update().get(
            pk=certificate_request_id
        )
        if certificate_request.status != CertificateRequest.STATUS_PENDING:
            raise ValueError("Only pending certificate requests can be rejected.")
        certificate_request.status = CertificateRequest.STATUS_REJECTED
        certificate_request.reviewed_by = reviewer
        certificate_request.reviewed_at = timezone.now()
        certificate_request.save(
            update_fields=("status", "reviewed_by", "reviewed_at")
        )
        return certificate_request


def revoke_certificate_request(certificate_request_id, reviewer):
    if (
        not reviewer.is_authenticated
        or not reviewer.is_active
        or not reviewer.is_superuser
    ):
        raise PermissionError("Only a superuser may revoke certificates.")

    with transaction.atomic():
        certificate_request = CertificateRequest.objects.select_for_update().get(
            pk=certificate_request_id
        )
        if (
            certificate_request.status != CertificateRequest.STATUS_APPROVED
            or certificate_request.is_revoked
        ):
            raise ValueError("Only an active approved certificate can be revoked.")
        certificate_request.is_revoked = True
        certificate_request.revoked_by = reviewer
        certificate_request.revoked_at = timezone.now()
        certificate_request.save(
            update_fields=("is_revoked", "revoked_by", "revoked_at")
        )
        return certificate_request

import logging
import secrets
import uuid
from datetime import date
from io import BytesIO
from pathlib import Path

from django.conf import settings
from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone
from reportlab import __file__ as reportlab_package
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from .models import CertificateRequest

logger = logging.getLogger(__name__)


def _register_unicode_fonts():
    bundled_font_dir = Path(reportlab_package).parent / "fonts"
    font_paths = (
        Path("C:/Windows/Fonts/Nirmala.ttf"),
        Path("C:/Windows/Fonts/arial.ttf"),
        Path("/usr/share/fonts/truetype/noto/NotoSansDevanagari-Regular.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        bundled_font_dir / "Vera.ttf",
    )
    bold_font_paths = (
        Path("C:/Windows/Fonts/NirmalaB.ttf"),
        Path("C:/Windows/Fonts/arialbd.ttf"),
        Path("/usr/share/fonts/truetype/noto/NotoSansDevanagari-Bold.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
        bundled_font_dir / "VeraBd.ttf",
    )
    regular = next((path for path in font_paths if path.is_file()), None)
    bold = next((path for path in bold_font_paths if path.is_file()), None)
    if regular:
        if "CertificateUnicode" not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont("CertificateUnicode", str(regular)))
            pdfmetrics.registerFont(
                TTFont("CertificateUnicode-Bold", str(bold or regular))
            )
        return "CertificateUnicode", "CertificateUnicode-Bold"
    return "Helvetica", "Helvetica-Bold"


def generate_certificate_pdf(certificate_request, verification_url):
    regular_font, bold_font = _register_unicode_fonts()
    width, height = landscape(A4)
    output = BytesIO()
    document = canvas.Canvas(output, pagesize=(width, height))

    document.setFillColorRGB(0.98, 0.985, 0.995)
    document.rect(0, 0, width, height, fill=1, stroke=0)
    document.setStrokeColorRGB(0.05, 0.14, 0.31)
    document.setLineWidth(3)
    document.rect(24, 24, width - 48, height - 48, fill=0, stroke=1)
    document.setStrokeColorRGB(0.76, 0.62, 0.31)
    document.setLineWidth(1)
    document.rect(32, 32, width - 64, height - 64, fill=0, stroke=1)

    logo_path = settings.MEDIA_ROOT / "site" / "Rajvans_Education_Emblem_Logo.png"
    if logo_path.is_file():
        document.drawImage(
            ImageReader(str(logo_path)),
            width / 2 - 25,
            height - 96,
            width=50,
            height=50,
            preserveAspectRatio=True,
            mask="auto",
        )

    document.setFillColorRGB(0.05, 0.14, 0.31)
    document.setFont(bold_font, 15)
    document.drawCentredString(width / 2, height - 116, "RAJVANS GROUP OF EDUCATIONS")
    document.setFont(bold_font, 27)
    document.drawCentredString(width / 2, height - 160, "COURSE COMPLETION CERTIFICATE")
    document.setFillColorRGB(0.32, 0.36, 0.43)
    document.setFont(regular_font, 13)
    document.drawCentredString(width / 2, height - 195, "This certificate is issued to")

    student = certificate_request.student
    document.setFillColorRGB(0.05, 0.14, 0.31)
    document.setFont(bold_font, 25)
    document.drawCentredString(width / 2, height - 237, student.full_name)
    document.setStrokeColorRGB(0.76, 0.62, 0.31)
    document.setLineWidth(1)
    document.line(width * 0.25, height - 249, width * 0.75, height - 249)

    document.setFillColorRGB(0.22, 0.25, 0.31)
    document.setFont(regular_font, 14)
    document.drawCentredString(width / 2, height - 278, "for completion of the course")
    document.setFont(bold_font, 19)
    document.drawCentredString(width / 2, height - 309, student.course.name)

    institution = student.university.name if student.university_id else ""
    if institution:
        document.setFont(regular_font, 11)
        document.drawCentredString(width / 2, height - 333, f"Institution: {institution}")

    issued_date = certificate_request.issued_at or date.today()
    document.setFont(regular_font, 10)
    document.drawString(58, 91, f"Registration No.: {student.registration_number}")
    document.drawString(58, 73, f"Certificate No.: {certificate_request.certificate_number}")
    document.drawRightString(width - 58, 91, f"Issue Date: {issued_date:%d %B %Y}")
    document.setStrokeColorRGB(0.05, 0.14, 0.31)
    document.line(width - 220, 93, width - 58, 93)
    document.setFont(regular_font, 9)
    document.drawRightString(width - 58, 78, "Authorized Signatory")
    document.setFillColorRGB(0.32, 0.36, 0.43)
    document.setFont(regular_font, 8)
    document.drawCentredString(width / 2, 51, f"Verify this certificate: {verification_url}")
    document.showPage()
    document.save()
    return output.getvalue()


def approve_certificate_request(certificate_request_id, reviewer, verification_url):
    if not reviewer.is_authenticated or not reviewer.is_superuser:
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
            if storage.exists(stored_name):
                storage.delete(stored_name)
        raise


def reject_certificate_request(certificate_request_id, reviewer):
    if not reviewer.is_authenticated or not reviewer.is_superuser:
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

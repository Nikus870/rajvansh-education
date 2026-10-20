import uuid
from django.conf import settings
from django.db import IntegrityError, models, transaction
from django.core.validators import RegexValidator
from django.utils import timezone

from apps.courses.models import Course
from apps.universities.models import University
from apps.franchise.models import FranchiseProfile
from apps.franchise.profile_images import (
    get_private_profile_image_storage,
    profile_image_upload_to,
    validate_profile_image,
)


def generate_registration_number():
    """
    Generate a unique registration number using a UUID-based suffix.
    Format: RG-YYYYMMDD-XXXXXXXXXX  (where X is part of a UUID hex)
    This approach is collision-safe and does not depend on row count.
    """
    today = timezone.localdate().strftime("%Y%m%d")
    suffix = uuid.uuid4().hex[:10].upper()
    return f"RG-{today}-{suffix}"


class Student(models.Model):
    """
    Represents a student registered by a franchise.

    Every student must be linked to one franchise (via FranchiseProfile).
    The franchise owner / staff who created the record is recorded via
    `created_by`.  The parent administrator can view all students; a
    franchise user can view only students that belong to their own
    franchise.
    """

    GENDER_CHOICES = [
        ("M", "Male"),
        ("F", "Female"),
        ("O", "Other"),
        ("N", "Prefer not to say"),
    ]

    STUDY_MODE_CHOICES = [
        ("regular", "Regular"),
        ("odl", "ODL / Distance"),
    ]

    ADMISSION_STATUS_CHOICES = [
        ("pending", "Pending"),
        ("admitted", "Admitted"),
        ("rejected", "Rejected"),
        ("cancelled", "Cancelled"),
        ("enrolled", "Enrolled"),
    ]

    FEE_STATUS_CHOICES = [
        ("pending", "Fee Pending"),
        ("partial", "Partially Paid"),
        ("paid", "Fully Paid"),
        ("waived", "Waived"),
    ]

    QUALIFICATION_CHOICES = [
        ("10th", "10th (SSC / Matriculation)"),
        ("12th", "12th (HSC / Intermediate)"),
        ("diploma", "Diploma"),
        ("graduation", "Graduation (Bachelor's)"),
        ("post_graduation", "Post Graduation (Master's)"),
        ("other", "Other"),
    ]

    # ── Identification ────────────────────────────────────────────────────
    registration_number = models.CharField(
        max_length=30,
        unique=True,
        editable=False,
        help_text="Auto-generated on save.",
    )

    # ── Personal details ──────────────────────────────────────────────────
    full_name = models.CharField(max_length=180)

    guardian_name = models.CharField(
        max_length=180,
        blank=True,
        verbose_name="Father / Guardian Name",
    )

    date_of_birth = models.DateField(null=True, blank=True)

    gender = models.CharField(
        max_length=1,
        choices=GENDER_CHOICES,
        blank=True,
    )

    mobile = models.CharField(
        max_length=15,
        validators=[
            RegexValidator(
                r"^\+?[0-9]{7,15}$",
                "Enter a valid mobile number.",
            )
        ],
    )

    email = models.EmailField(blank=True)

    address = models.TextField(blank=True)

    profile_image = models.ImageField(
        upload_to=profile_image_upload_to,
        storage=get_private_profile_image_storage,
        validators=[validate_profile_image],
        blank=True,
    )

    # ── Academic details ──────────────────────────────────────────────────
    course = models.ForeignKey(
        Course,
        on_delete=models.PROTECT,
        related_name="students",
    )

    university = models.ForeignKey(
        University,
        on_delete=models.PROTECT,
        related_name="students",
    )

    study_mode = models.CharField(
        max_length=10,
        choices=STUDY_MODE_CHOICES,
        default="odl",
    )

    previous_qualification = models.CharField(
        max_length=30,
        choices=QUALIFICATION_CHOICES,
        blank=True,
    )

    admission_date = models.DateField(null=True, blank=True)

    # ── Status fields ─────────────────────────────────────────────────────
    admission_status = models.CharField(
        max_length=20,
        choices=ADMISSION_STATUS_CHOICES,
        default="pending",
    )

    fee_status = models.CharField(
        max_length=10,
        choices=FEE_STATUS_CHOICES,
        default="pending",
    )

    remarks = models.TextField(blank=True)

    # ── Relationships ─────────────────────────────────────────────────────
    franchise = models.ForeignKey(
        FranchiseProfile,
        on_delete=models.PROTECT,
        related_name="students",
        help_text="Franchise responsible for this registration.",
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_students",
        help_text="User who registered this student.",
    )

    # ── Timestamps ────────────────────────────────────────────────────────
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Student"
        verbose_name_plural = "Students"

    def __str__(self):
        return f"{self.registration_number} – {self.full_name}"

    @property
    def has_profile_image(self):
        return bool(
            self.profile_image
            and self.profile_image.storage.exists(self.profile_image.name)
        )

    def save(self, *args, **kwargs):
        if not self.registration_number:
            for _ in range(5):
                candidate = generate_registration_number()
                self.registration_number = candidate
                try:
                    with transaction.atomic():
                        super().save(*args, **kwargs)
                    return
                except IntegrityError:
                    if not Student.objects.filter(
                        registration_number=candidate
                    ).exists():
                        raise
            raise RuntimeError(
                "Could not generate a unique registration number "
                "after 5 attempts. Please try again."
            )
        super().save(*args, **kwargs)

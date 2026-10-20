import secrets
from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone

from .certificate_storage import get_certificate_storage
from .profile_images import (
    get_private_profile_image_storage,
    profile_image_upload_to,
    validate_profile_image,
)

class FranchiseProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="franchise_profile",
    )
    mobile = models.CharField(max_length=30)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    business_name = models.CharField(max_length=180, blank=True)
    address = models.TextField(blank=True)
    profile_image = models.ImageField(
        upload_to=profile_image_upload_to,
        storage=get_private_profile_image_storage,
        validators=[validate_profile_image],
        blank=True,
    )
    monthly_student_target = models.PositiveIntegerField(
        default=20,
        validators=[MinValueValidator(1)],
        help_text="Monthly new-student registration target for this franchise.",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.user.get_full_name() or self.user.username

    @property
    def has_profile_image(self):
        return bool(
            self.profile_image
            and self.profile_image.storage.exists(self.profile_image.name)
        )


class FranchiseApplication(models.Model):
    STATUS = [
        ("pending", "Pending"),
        ("review", "Under Review"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
        ("contacted", "Contacted"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="franchise_applications",
        null=True,
        blank=True,
    )

    name = models.CharField(max_length=120)
    mobile = models.CharField(max_length=30)
    email = models.EmailField()
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    business_name = models.CharField(max_length=180, blank=True)
    address = models.TextField(blank=True)
    experience = models.TextField(blank=True)
    message = models.TextField(blank=True)

    status = models.CharField(
        max_length=20,
        choices=STATUS,
        default="pending",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} - {self.email}"


class FranchiseActivationToken(models.Model):
    application = models.OneToOneField(
        FranchiseApplication,
        on_delete=models.CASCADE,
        related_name="activation_token",
    )

    token = models.CharField(
        max_length=128,
        unique=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)

    used = models.BooleanField(default=False)

    TOKEN_EXPIRY_HOURS = 24

    @property
    def is_expired(self):
        """Returns True if the token is older than TOKEN_EXPIRY_HOURS."""
        expiry = self.created_at + timedelta(hours=self.TOKEN_EXPIRY_HOURS)
        return timezone.now() > expiry

    def __str__(self):
        return f"Activation - {self.application.email}"


class FranchiseStaff(models.Model):
    """
    Represents a staff member employed by a franchise owner.

    The user account is created when the staff member accepts the
    invitation and sets their password.  Until then, user may be None
    and the record acts as a pending invitation.
    """

    ROLE_CHOICES = [
        ("counsellor", "Counsellor"),
        ("data_entry", "Data Entry Operator"),
        ("coordinator", "Admission Coordinator"),
        ("manager", "Branch Manager"),
    ]

    franchise = models.ForeignKey(
        FranchiseProfile,
        on_delete=models.CASCADE,
        related_name="staff_members",
    )

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="franchise_staff_profile",
    )

    name = models.CharField(max_length=180)
    profile_image = models.ImageField(
        upload_to=profile_image_upload_to,
        storage=get_private_profile_image_storage,
        validators=[validate_profile_image],
        blank=True,
    )
    email = models.EmailField()
    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default="counsellor",
    )

    is_active = models.BooleanField(default=True)

    invited_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-invited_at"]
        unique_together = [("franchise", "email")]
        verbose_name = "Franchise Staff"
        verbose_name_plural = "Franchise Staff"

    def __str__(self):
        return f"{self.name} ({self.get_role_display()}) – {self.franchise}"

    @property
    def has_profile_image(self):
        return bool(
            self.profile_image
            and self.profile_image.storage.exists(self.profile_image.name)
        )


class FranchiseStaffInvitation(models.Model):
    """
    Single-use, time-limited invitation token sent to a staff member.
    """

    staff = models.ForeignKey(
        FranchiseStaff,
        on_delete=models.CASCADE,
        related_name="invitations",
    )

    token = models.CharField(max_length=128, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    used = models.BooleanField(default=False)

    TOKEN_EXPIRY_HOURS = 24

    @property
    def is_expired(self):
        expiry = self.created_at + timedelta(hours=self.TOKEN_EXPIRY_HOURS)
        return timezone.now() > expiry

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Invitation – {self.staff.email}"


class CertificateRequest(models.Model):
    STATUS_PENDING = "pending"
    STATUS_APPROVED = "approved"
    STATUS_REJECTED = "rejected"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_APPROVED, "Approved"),
        (STATUS_REJECTED, "Rejected"),
    ]

    student = models.ForeignKey(
        "students.Student",
        on_delete=models.PROTECT,
        related_name="certificate_requests",
    )
    franchise = models.ForeignKey(
        FranchiseProfile,
        on_delete=models.PROTECT,
        related_name="certificate_requests",
    )
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="certificate_requests",
    )
    requested_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
    )
    eligibility_verified = models.BooleanField(
        default=False,
        help_text="Confirm verified course completion before approval.",
    )
    eligibility_remarks = models.TextField(
        blank=True,
        help_text="Record the evidence source reviewed before approving eligibility.",
    )
    admin_remarks = models.TextField(blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_certificate_requests",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    certificate_number = models.CharField(
        max_length=40,
        unique=True,
        null=True,
        blank=True,
    )
    issued_at = models.DateField(null=True, blank=True)
    verification_token = models.CharField(
        max_length=64,
        unique=True,
        null=True,
        blank=True,
        editable=False,
    )
    is_revoked = models.BooleanField(default=False)
    revoked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="revoked_certificate_requests",
    )
    revoked_at = models.DateTimeField(null=True, blank=True)
    certificate_file = models.FileField(
        upload_to="",
        storage=get_certificate_storage,
        blank=True,
    )

    class Meta:
        ordering = ["-requested_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["student"],
                condition=Q(status="pending"),
                name="unique_pending_certificate_per_student",
            ),
            models.UniqueConstraint(
                fields=["student"],
                condition=Q(status="approved", is_revoked=False),
                name="unique_active_certificate_per_student",
            ),
        ]
        indexes = [
            models.Index(fields=["status", "requested_at"]),
            models.Index(fields=["franchise", "status"]),
        ]

    def __str__(self):
        return f"{self.student} certificate request ({self.get_status_display()})"

    @property
    def course(self):
        return self.student.course

    def clean(self):
        super().clean()
        if self.student_id and self.franchise_id:
            if self.student.franchise_id != self.franchise_id:
                raise ValidationError(
                    {"franchise": "The requesting franchise must own this student."}
                )
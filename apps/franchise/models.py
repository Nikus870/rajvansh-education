import secrets
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone


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
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.user.get_full_name() or self.user.username


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
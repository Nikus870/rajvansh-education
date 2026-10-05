from django.conf import settings
from django.db import models


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

    def __str__(self):
        return f"Activation - {self.application.email}"
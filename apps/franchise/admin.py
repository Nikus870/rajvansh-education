from secrets import token_urlsafe

from django.conf import settings
from django.contrib import admin, messages
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.urls import reverse

from .models import (
    FranchiseActivationToken,
    FranchiseApplication,
    FranchiseProfile,
)


@admin.register(FranchiseProfile)
class FranchiseProfileAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "mobile",
        "city",
        "state",
        "created_at",
    )

    search_fields = (
        "user__username",
        "user__email",
        "mobile",
        "city",
        "business_name",
    )


@admin.register(FranchiseActivationToken)
class FranchiseActivationTokenAdmin(admin.ModelAdmin):
    list_display = (
        "application",
        "created_at",
        "used",
    )

    list_filter = ("used",)

    search_fields = (
        "application__email",
        "application__name",
    )

    readonly_fields = (
        "application",
        "token",
        "created_at",
        "used",
    )


@admin.register(FranchiseApplication)
class FranchiseApplicationAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "email",
        "city",
        "business_name",
        "status",
        "created_at",
    )

    list_filter = (
        "status",
        "state",
    )

    search_fields = (
        "name",
        "email",
        "mobile",
        "city",
        "business_name",
    )

    actions = [
        "approve_applications",
        "reject_applications",
    ]

    @admin.action(description="Approve selected applications")
    def approve_applications(self, request, queryset):
        approved_count = 0
        email_count = 0

        for application in queryset:

            # Already approved
            if application.status == "approved":
                self.message_user(
                    request,
                    f"{application.email} is already approved.",
                    level=messages.WARNING,
                )
                continue

            # Find existing user by email/username
            user = User.objects.filter(
                email__iexact=application.email
            ).first()

            if not user:
                user = User.objects.filter(
                    username__iexact=application.email
                ).first()

            # Create user if necessary
            if not user:
                user = User(
                    username=application.email,
                    email=application.email,
                    first_name=application.name,
                    is_active=False,
                )

                user.set_unusable_password()
                user.save()

            else:
                # Never activate staff/superuser accounts through
                # the franchise approval system.
                if user.is_staff or user.is_superuser:
                    self.message_user(
                        request,
                        (
                            f"{application.email} belongs to a staff "
                            "or superuser account and cannot be approved "
                            "as a franchise account."
                        ),
                        level=messages.ERROR,
                    )
                    continue

                user.email = application.email
                user.first_name = application.name
                user.is_active = False
                user.set_unusable_password()
                user.save()

            # Create/update franchise profile
            FranchiseProfile.objects.update_or_create(
                user=user,
                defaults={
                    "mobile": application.mobile,
                    "city": application.city,
                    "state": application.state,
                    "business_name": application.business_name,
                    "address": application.address,
                },
            )

            # Connect application with user
            application.user = user
            application.status = "approved"
            application.save(
                update_fields=[
                    "user",
                    "status",
                    "updated_at",
                ]
            )

            # Create activation token
            activation_token, created = (
                FranchiseActivationToken.objects.get_or_create(
                    application=application,
                    defaults={
                        "token": token_urlsafe(48),
                    },
                )
            )

            # If an old token was already used, create a fresh one
            if activation_token.used:
                activation_token.token = token_urlsafe(48)
                activation_token.used = False
                activation_token.save(
                    update_fields=[
                        "token",
                        "used",
                    ]
                )

            # Build activation URL
            activation_path = reverse(
                "franchise:activate",
                kwargs={
                    "token": activation_token.token,
                },
            )

            activation_url = request.build_absolute_uri(
                activation_path
            )

            # Send activation email
            subject = (
                "Franchise Account Approved - "
                "Rajvansh Group of Educations"
            )

            message = f"""
Dear {application.name},

Your franchise application with Rajvansh Group of Educations
has been approved.

Your franchise account has been created successfully.

Please use the following link to activate your account
and create your password:

{activation_url}

After setting your password, you will be able to log in
to your franchise dashboard.

If you did not submit this application, please ignore this email.

Regards,
Rajvansh Group of Educations
"""

            try:
                send_mail(
                    subject=subject,
                    message=message.strip(),
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[application.email],
                    fail_silently=False,
                )

                email_count += 1

            except Exception as exc:
                self.message_user(
                    request,
                    (
                        f"Application for {application.email} was "
                        f"approved, but the activation email could "
                        f"not be sent: {exc}"
                    ),
                    level=messages.ERROR,
                )

            approved_count += 1

            # Also show activation URL to admin for development/testing
            self.message_user(
                request,
                (
                    f"Approved {application.email}. "
                    f"Activation URL: {activation_url}"
                ),
                level=messages.SUCCESS,
            )

        if approved_count:
            self.message_user(
                request,
                (
                    f"{approved_count} application(s) approved. "
                    f"{email_count} activation email(s) generated."
                ),
                level=messages.INFO,
            )

    @admin.action(description="Reject selected applications")
    def reject_applications(self, request, queryset):
        updated = queryset.exclude(
            status="approved"
        ).update(
            status="rejected"
        )

        self.message_user(
            request,
            f"{updated} application(s) rejected.",
            level=messages.WARNING,
        )
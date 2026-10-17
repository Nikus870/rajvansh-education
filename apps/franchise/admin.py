import logging
from secrets import token_urlsafe

import resend
from django.conf import settings
from django.contrib import admin, messages
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone

from .models import (
    FranchiseActivationToken,
    FranchiseApplication,
    FranchiseProfile,
    FranchiseStaff,
    FranchiseStaffInvitation,
)

logger = logging.getLogger(__name__)


def _send_activation_email(request, application, *, renew=False):
    """
    Send a franchise activation email through the Resend HTTPS API.
    Existing approval and token records remain intact if delivery fails.
    """
    token, _ = FranchiseActivationToken.objects.get_or_create(
        application=application,
        defaults={"token": token_urlsafe(48)},
    )

    if renew or token.used or token.is_expired:
        token.token = token_urlsafe(48)
        token.created_at = timezone.now()
        token.used = False
        token.save(update_fields=["token", "created_at", "used"])

    activation_url = request.build_absolute_uri(
        reverse(
            "franchise:activate",
            kwargs={"token": token.token},
        )
    )

    message = f"""
Dear {application.name},

Your franchise application with Rajvansh Group of Educations has been approved.

Please use the link below to activate your account and create your password:

{activation_url}

This link is valid for 24 hours.

Regards,
Rajvansh Group of Educations
"""

    api_key = getattr(settings, "RESEND_API_KEY", "")

    if not api_key:
        logger.error(
            "RESEND_API_KEY is missing; activation email not sent "
            "for application ID %s.",
            application.pk,
        )
        return False

    try:
        resend.api_key = api_key

        response = resend.Emails.send(
            {
                "from": settings.DEFAULT_FROM_EMAIL,
                "to": [application.email],
                "subject": (
                    "Franchise Account Approved - "
                    "Rajvansh Group of Educations"
                ),
                "text": message.strip(),
            }
        )

        if isinstance(response, dict) and response.get("id"):
            logger.info(
                "Resend accepted activation email for application ID %s.",
                application.pk,
            )
            return True

        logger.error(
            "Resend returned an unexpected response for application ID %s: %r",
            application.pk,
            response,
        )
        return False

    except Exception:
        logger.exception(
            "Resend API failed for application ID %s.",
            application.pk,
        )
        return False


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
        failed_emails = 0

        for application in queryset:

            # Already approved
            if application.status == "approved":
                if not application.user:
                    self.message_user(
                        request,
                        (
                            f"{application.email} is approved "
                            "but has no linked user."
                        ),
                        level=messages.ERROR,
                    )
                    continue

                if application.user.is_active:
                    self.message_user(
                        request,
                        f"{application.email} is already activated.",
                        level=messages.WARNING,
                    )
                    continue

                if _send_activation_email(
                    request,
                    application,
                    renew=True,
                ):
                    email_count += 1
                    self.message_user(
                        request,
                        (
                            "A fresh activation link was sent to "
                            f"{application.email}."
                        ),
                        level=messages.SUCCESS,
                    )
                else:
                    failed_emails += 1
                    self.message_user(
                        request,
                        (
                            f"{application.email} remains approved, "
                            "but its activation email could not be sent. "
                            "Check the server logs."
                        ),
                        level=messages.ERROR,
                    )

                approved_count += 1
                continue

            # Find an existing account by email or username.
            user = User.objects.filter(
                email__iexact=application.email
            ).first()

            if not user:
                user = User.objects.filter(
                    username__iexact=application.email
                ).first()

            # Never attach an existing account to a public application.
            if user:
                self.message_user(
                    request,
                    (
                        f"{application.email} already belongs to an "
                        "account and cannot be approved automatically."
                    ),
                    level=messages.ERROR,
                )
                continue

            # Create an inactive user with no usable password.
            user = User(
                username=application.email,
                email=application.email,
                first_name=application.name,
                is_active=False,
                is_staff=False,
                is_superuser=False,
            )
            user.set_unusable_password()
            user.save()

            # Create the franchise profile.
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

            # Link the application to the newly created account.
            application.user = user
            application.status = "approved"
            application.save(
                update_fields=[
                    "user",
                    "status",
                    "updated_at",
                ]
            )

            approved_count += 1

            self.message_user(
                request,
                f"Approved {application.email}.",
                level=messages.SUCCESS,
            )

            # Email failure does not undo the approval.
            if _send_activation_email(request, application):
                email_count += 1
            else:
                failed_emails += 1
                self.message_user(
                    request,
                    (
                        f"Application for {application.email} was "
                        "approved, but the activation email could not "
                        "be sent. Check the server logs."
                    ),
                    level=messages.ERROR,
                )

        if approved_count:
            self.message_user(
                request,
                (
                    f"{approved_count} application(s) processed as approved. "
                    f"{email_count} activation email(s) sent successfully. "
                    f"{failed_emails} email(s) failed."
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


@admin.register(FranchiseStaff)
class FranchiseStaffAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "email",
        "role",
        "franchise",
        "is_active",
        "invited_at",
    )

    list_filter = (
        "role",
        "is_active",
        "franchise",
    )

    search_fields = (
        "name",
        "email",
        "franchise__business_name",
        "franchise__user__email",
    )

    readonly_fields = ("invited_at", "updated_at")

    actions = [
        "activate_staff",
        "deactivate_staff",
    ]

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)

        if obj.user_id and obj.user.is_active != obj.is_active:
            obj.user.is_active = obj.is_active
            obj.user.save(update_fields=["is_active"])

    @admin.action(description="Activate selected staff members")
    def activate_staff(self, request, queryset):
        updated = queryset.update(is_active=True)

        for staff in queryset:
            if staff.user:
                staff.user.is_active = True
                staff.user.save(update_fields=["is_active"])

        self.message_user(
            request,
            f"{updated} staff member(s) activated.",
        )

    @admin.action(description="Deactivate selected staff members")
    def deactivate_staff(self, request, queryset):
        updated = queryset.update(is_active=False)

        for staff in queryset:
            if staff.user:
                staff.user.is_active = False
                staff.user.save(update_fields=["is_active"])

        self.message_user(
            request,
            f"{updated} staff member(s) deactivated.",
            level=messages.WARNING,
        )


@admin.register(FranchiseStaffInvitation)
class FranchiseStaffInvitationAdmin(admin.ModelAdmin):
    list_display = (
        "staff",
        "created_at",
        "used",
    )

    list_filter = ("used",)

    readonly_fields = (
        "staff",
        "token",
        "created_at",
        "used",
    )

    search_fields = (
        "staff__email",
        "staff__name",
    )
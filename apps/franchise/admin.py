import logging
from secrets import token_urlsafe

import resend
from django.conf import settings
from django.contrib import admin, messages
from django.contrib.auth.models import User
from django.urls import path, reverse
from django.utils import timezone
from django.utils.html import format_html, format_html_join

from .certificate_service import (
    approve_certificate_request,
    reject_certificate_request,
    revoke_certificate_request,
)
from .certificate_views import admin_certificate_download
from .models import (
    CertificateRequest,
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

This link is valid for 10 minutes.

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


@admin.register(CertificateRequest)
class CertificateRequestAdmin(admin.ModelAdmin):
    list_display = (
        "student",
        "course_name",
        "franchise",
        "status",
        "eligibility_verified",
        "requested_at",
        "certificate_number",
        "is_revoked",
        "revoked_at",
    )
    list_filter = (
        "status",
        "student__course",
        "franchise",
        "requested_at",
        "is_revoked",
    )
    search_fields = (
        "student__full_name",
        "student__registration_number",
        "certificate_number",
        "franchise__business_name",
        "franchise__user__username",
        "franchise__user__email",
    )
    date_hierarchy = "requested_at"
    raw_id_fields = ("student", "franchise", "requested_by", "reviewed_by")
    readonly_fields = (
        "student",
        "student_registration_number",
        "student_full_name",
        "course_name",
        "institution_name",
        "study_mode",
        "prior_requests",
        "franchise",
        "requested_by",
        "requested_at",
        "status",
        "reviewed_by",
        "reviewed_at",
        "certificate_number",
        "issued_at",
        "verification_token",
        "is_revoked",
        "revoked_by",
        "revoked_at",
        "certificate_download_link",
    )
    fieldsets = (
        (
            "Request",
            {
                "fields": (
                    "student",
                    "student_registration_number",
                    "student_full_name",
                    "course_name",
                    "institution_name",
                    "study_mode",
                    "prior_requests",
                    "franchise",
                    "requested_by",
                    "requested_at",
                    "status",
                )
            },
        ),
        (
            "Eligibility and remarks",
            {
                "fields": (
                    "eligibility_verified",
                    "eligibility_remarks",
                    "admin_remarks",
                )
            },
        ),
        (
            "Certificate",
            {
                "fields": (
                    "reviewed_by",
                    "reviewed_at",
                    "certificate_number",
                    "issued_at",
                    "is_revoked",
                    "revoked_by",
                    "revoked_at",
                    "certificate_download_link",
                )
            },
        ),
    )
    actions = (
        "approve_requests",
        "reject_requests",
        "revoke_certificates",
    )

    @admin.display(description="Course")
    def course_name(self, obj):
        return obj.student.course.name

    @admin.display(description="Student name")
    def student_full_name(self, obj):
        return obj.student.full_name

    @admin.display(description="Registration number")
    def student_registration_number(self, obj):
        return obj.student.registration_number

    @admin.display(description="Institution")
    def institution_name(self, obj):
        return obj.student.university.name if obj.student.university_id else "—"

    @admin.display(description="Study mode")
    def study_mode(self, obj):
        return obj.student.get_study_mode_display()

    @admin.display(description="Previous certificate requests")
    def prior_requests(self, obj):
        previous = (
            CertificateRequest.objects.filter(student_id=obj.student_id)
            .exclude(pk=obj.pk)
            .order_by("-requested_at")
        )
        if not previous.exists():
            return "No previous requests"
        return format_html(
            "<ul>{}</ul>",
            format_html_join(
                "",
                '<li><a href="{}">{}</a> — {}{}</li>',
                (
                    (
                        reverse(
                            "admin:franchise_certificaterequest_change",
                            args=(item.pk,),
                        ),
                        item.requested_at.strftime("%d %b %Y"),
                        item.get_status_display(),
                        (
                            f" — {item.certificate_number}"
                            if item.certificate_number
                            else ""
                        ),
                    )
                    for item in previous
                ),
            ),
        )

    @admin.display(description="Generated certificate")
    def certificate_download_link(self, obj):
        if (
            obj.status != CertificateRequest.STATUS_APPROVED
            or obj.is_revoked
            or not obj.certificate_file
        ):
            return "No available certificate"
        url = reverse(
            "admin:franchise_certificaterequest_download_certificate",
            args=(obj.pk,),
        )
        return format_html('<a href="{}">Download certificate PDF</a>', url)

    def get_urls(self):
        custom_urls = [
            path(
                "<int:request_id>/download-certificate/",
                self.admin_site.admin_view(admin_certificate_download),
                name="franchise_certificaterequest_download_certificate",
            )
        ]
        return custom_urls + super().get_urls()

    def _require_superuser(self, request):
        if request.user.is_active and request.user.is_superuser:
            return True
        self.message_user(
            request,
            "Only an active superuser may review certificate requests.",
            level=messages.ERROR,
        )
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.action(description="Approve selected verified certificate requests")
    def approve_requests(self, request, queryset):
        if not self._require_superuser(request):
            return

        approved = 0
        failed = 0
        for certificate_request in queryset:
            try:
                approve_certificate_request(
                    certificate_request.pk,
                    request.user,
                    lambda token: request.build_absolute_uri(
                        reverse(
                            "franchise:certificate_verify",
                            kwargs={"token": token},
                        )
                    ),
                )
            except (PermissionError, ValueError) as error:
                failed += 1
                self.message_user(
                    request,
                    f"Request {certificate_request.pk} was not approved: {error}",
                    level=messages.WARNING,
                )
            except Exception:
                failed += 1
                logger.exception(
                    "Certificate approval failed for request ID %s.",
                    certificate_request.pk,
                )
                self.message_user(
                    request,
                    f"Request {certificate_request.pk} could not be approved. Check the server log.",
                    level=messages.ERROR,
                )
            else:
                approved += 1
        if approved:
            self.message_user(request, f"{approved} certificate request(s) approved.")
        if failed:
            self.message_user(
                request,
                f"{failed} certificate request(s) were not approved.",
                level=messages.WARNING,
            )

    @admin.action(description="Reject selected pending certificate requests")
    def reject_requests(self, request, queryset):
        if not self._require_superuser(request):
            return

        rejected = 0
        for certificate_request in queryset:
            try:
                reject_certificate_request(certificate_request.pk, request.user)
            except (PermissionError, ValueError) as error:
                self.message_user(
                    request,
                    f"Request {certificate_request.pk} was not rejected: {error}",
                    level=messages.WARNING,
                )
            else:
                rejected += 1
        if rejected:
            self.message_user(request, f"{rejected} request(s) rejected.")

    @admin.action(description="Revoke selected approved certificates")
    def revoke_certificates(self, request, queryset):
        if not self._require_superuser(request):
            return
        revoked = 0
        failed = 0
        for certificate_request in queryset:
            try:
                revoke_certificate_request(certificate_request.pk, request.user)
            except (PermissionError, ValueError) as error:
                failed += 1
                self.message_user(
                    request,
                    f"Request {certificate_request.pk} was not revoked: {error}",
                    level=messages.WARNING,
                )
            else:
                revoked += 1
        if revoked:
            self.message_user(
                request,
                f"{revoked} certificate(s) revoked.",
                level=messages.WARNING,
            )
        if failed:
            self.message_user(
                request,
                f"{failed} certificate(s) were not revoked.",
                level=messages.WARNING,
            )
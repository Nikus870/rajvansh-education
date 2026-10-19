"""
Extended franchise views — dashboard, staff management, password change,
password reset workflow, and logout.

URL namespace: franchise
"""

import logging
import secrets
import smtplib
from datetime import timedelta
from functools import wraps

from django.contrib import messages
from django.contrib.auth import (
    login,
    logout,
    update_session_auth_hash,
)
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.core.paginator import Paginator
from django.conf import settings
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import Resolver404, resolve, reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils import timezone
from django.db.models import Q
from urllib.parse import urlsplit

from .forms import (
    FranchiseLoginForm,
    FranchiseRegistrationForm,
    FranchiseSetPasswordForm,
    FranchiseStaffInviteForm,
    FranchisePasswordChangeForm,
    FranchiseForgotPasswordForm,
    FranchisePasswordResetForm,
)
from .analytics import get_student_growth_analytics
from .models import (
    FranchiseActivationToken,
    FranchiseApplication,
    FranchiseStaff,
    FranchiseStaffInvitation,
)

logger = logging.getLogger(__name__)

# ─── Helpers ──────────────────────────────────────────────────────────────────


def franchise_owner_required(view_func):
    """
    Ensures the user is authenticated AND is a franchise owner
    (has a FranchiseProfile).  Franchise staff are not allowed.
    """
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect(f"/franchise/login/?next={request.path}")
        if not hasattr(request.user, "franchise_profile"):
            messages.warning(request, "Only franchise owners can access this page.")
            if _active_staff_profile(request.user):
                return redirect("franchise:staff_dashboard")
            return redirect("franchise:dashboard")
        return view_func(request, *args, **kwargs)
    return _wrapped


def portal_required(view_func):
    """
    Ensures the user is authenticated AND belongs to the franchise portal
    (either a franchise owner, franchise staff, or superuser doing support).
    """
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect(f"/franchise/login/?next={request.path}")

        is_owner = hasattr(request.user, "franchise_profile")
        is_staff = _active_staff_profile(request.user)
        is_super = request.user.is_superuser

        if not (is_owner or is_staff or is_super):
            messages.warning(
                request,
                "Your franchise account is inactive or has not been approved.",
            )
            try:
                request.user.franchise_staff_profile
            except FranchiseStaff.DoesNotExist:
                return redirect("core:home")
            logout(request)
            return redirect("franchise:login")
        return view_func(request, *args, **kwargs)
    return _wrapped


def _active_staff_profile(user):
    try:
        return user.franchise_staff_profile.is_active
    except FranchiseStaff.DoesNotExist:
        return False


def _safe_franchise_next_url(request, user, next_url):
    if not next_url or not url_has_allowed_host_and_scheme(
        next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return None

    next_path = urlsplit(next_url).path
    try:
        view_name = resolve(next_path).view_name
    except Resolver404:
        return None

    owner_views = {
        "franchise:dashboard",
        "franchise:profile",
        "franchise:change_password",
        "franchise:staff_list",
        "franchise:staff_invite",
        "franchise:staff_toggle",
        "franchise:staff_resend_invitation",
        "students:list",
        "students:register",
        "students:export_csv",
        "students:detail",
        "students:edit",
    }
    staff_views = {
        "franchise:staff_dashboard",
        "franchise:change_password",
        "students:list",
        "students:register",
        "students:export_csv",
        "students:detail",
        "students:edit",
    }

    if hasattr(user, "franchise_profile") and view_name in owner_views:
        return next_url
    if _active_staff_profile(user) and view_name in staff_views:
        return next_url
    return None


# ─── Public pages ─────────────────────────────────────────────────────────────


def landing(request):
    return render(request, "franchise/landing.html")


def register(request):
    if request.user.is_authenticated and hasattr(request.user, "franchise_profile"):
        return redirect("franchise:dashboard")

    form = FranchiseRegistrationForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(
            request,
            "Your franchise interest has been submitted successfully. "
            "Our team will review your application and contact you "
            "after approval.",
        )
        return redirect("franchise:landing")

    return render(request, "franchise/register.html", {"form": form})


# ─── Authentication ───────────────────────────────────────────────────────────


def franchise_login(request):
    if request.user.is_authenticated:
        if request.user.is_superuser:
            messages.info(
                request,
                "Django Admin accounts do not automatically have franchise access. "
                "Use an approved franchise owner or staff account to sign in here.",
            )
        elif hasattr(request.user, "franchise_profile"):
            return redirect("franchise:dashboard")
        try:
            staff_profile = (
                None
                if request.user.is_superuser
                else request.user.franchise_staff_profile
            )
        except FranchiseStaff.DoesNotExist:
            staff_profile = None
        if staff_profile:
            if staff_profile.is_active:
                return redirect("franchise:staff_dashboard")
            logout(request)
            messages.error(request, "Your franchise staff account is inactive.")
        elif not request.user.is_superuser:
            return redirect("core:home")

    if request.method == "POST":
        form = FranchiseLoginForm(request.POST, request=request)

        if form.is_valid():
            user = form.get_user()
            login(request, user)

            next_url = request.POST.get("next") or request.GET.get("next")
            safe_next_url = _safe_franchise_next_url(request, user, next_url)
            if safe_next_url:
                return redirect(safe_next_url)

            # Redirect based on role
            if hasattr(user, "franchise_profile"):
                return redirect("franchise:dashboard")
            if hasattr(user, "franchise_staff_profile"):
                return redirect("franchise:staff_dashboard")
            return redirect("franchise:dashboard")
    else:
        form = FranchiseLoginForm(request=request)

    return render(
        request,
        "franchise/login.html",
        {"form": form, "next_url": request.GET.get("next", "")},
    )


def activate_account(request, token):
    form = FranchiseSetPasswordForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        password_error = None
        activation_valid = False

        with transaction.atomic():
            try:
                activation = FranchiseActivationToken.objects.select_for_update().get(
                    token=token
                )
            except FranchiseActivationToken.DoesNotExist:
                activation = None

            if activation is not None:
                application = (
                    FranchiseApplication.objects.select_for_update()
                    .filter(pk=activation.application_id)
                    .first()
                )
                user = None
                if application and application.user_id:
                    user = (
                        User.objects.select_for_update()
                        .filter(pk=application.user_id)
                        .first()
                    )

                activation_valid = bool(
                    not activation.used
                    and not activation.is_expired
                    and application
                    and application.status == "approved"
                    and user
                    and not user.is_active
                    and not user.is_staff
                    and not user.is_superuser
                    and application.email.strip().casefold()
                    == user.email.strip().casefold()
                )

                if activation_valid:
                    try:
                        validate_password(form.cleaned_data["password1"], user)
                    except ValidationError as error:
                        password_error = error
                    else:
                        user.set_password(form.cleaned_data["password1"])
                        user.is_active = True
                        user.save(update_fields=["password", "is_active"])

                        activation.used = True
                        activation.save(update_fields=["used"])

        if password_error:
            form.add_error("password1", password_error)
            return render(
                request,
                "franchise/activate.html",
                {"form": form, "application": application},
            )

        if not activation_valid:
            messages.error(
                request,
                "This activation link is invalid or unavailable. "
                "Please contact the administrator.",
            )
            return redirect("franchise:login")

        login(
            request,
            user,
            backend="apps.franchise.backends.EmailOrUsernameBackend",
        )
        messages.success(
            request,
            "Your franchise account has been activated successfully. Welcome!",
        )
        return redirect("franchise:dashboard")

    activation = (
        FranchiseActivationToken.objects.select_related(
            "application",
            "application__user",
        )
        .filter(token=token)
        .first()
    )
    application = activation.application if activation else None
    user = application.user if application and application.user_id else None
    activation_valid = bool(
        activation
        and not activation.used
        and not activation.is_expired
        and application.status == "approved"
        and user
        and not user.is_active
        and not user.is_staff
        and not user.is_superuser
        and application.email.strip().casefold() == user.email.strip().casefold()
    )

    if not activation_valid:
        messages.error(
            request,
            "This activation link is invalid or unavailable. "
            "Please contact the administrator.",
        )
        return redirect("franchise:login")

    return render(
        request,
        "franchise/activate.html",
        {"form": form, "application": application},
    )


def franchise_logout(request):
    if request.method == "POST":
        logout(request)
        messages.info(request, "You have been logged out.")
    return redirect("core:home")


# ─── Dashboards ───────────────────────────────────────────────────────────────


@portal_required
def dashboard(request):
    """
    Main dashboard for franchise owners.
    Shows live statistics for the franchise.
    """
    if not hasattr(request.user, "franchise_profile"):
        # Redirect staff to their own dashboard
        if hasattr(request.user, "franchise_staff_profile"):
            return redirect("franchise:staff_dashboard")
        messages.warning(request, "Your franchise account has not been approved.")
        return redirect("core:home")

    profile = request.user.franchise_profile

    # Import here to avoid circular imports
    from apps.students.models import Student

    students_qs = Student.objects.filter(franchise=profile)
    analytics = get_student_growth_analytics(profile)

    stats = {
        "total_students": analytics["total"],
        "this_month": analytics["this_month"],
        "previous_month": analytics["previous_month"],
        "growth_percentage": analytics["growth_percentage"],
        "pending_admissions": students_qs.filter(
            admission_status="pending"
        ).count(),
        "admitted": students_qs.filter(
            admission_status="admitted"
        ).count(),
        "fee_pending": students_qs.filter(
            fee_status="pending"
        ).count(),
        "staff_count": profile.staff_members.filter(is_active=True).count(),
    }

    recent_students = students_qs.select_related("course", "university")[:5]

    return render(
        request,
        "franchise/dashboard.html",
        {
            "profile": profile,
            "applications": request.user.franchise_applications.all(),
            "stats": stats,
            "analytics": analytics,
            "recent_students": recent_students,
        },
    )


@portal_required
def staff_dashboard(request):
    """Dashboard for franchise staff members."""
    if not hasattr(request.user, "franchise_staff_profile"):
        return redirect("franchise:dashboard")

    staff_profile = request.user.franchise_staff_profile
    franchise = staff_profile.franchise

    from apps.students.models import Student
    students_qs = Student.objects.filter(franchise=franchise)
    analytics = get_student_growth_analytics(franchise)

    stats = {
        "total_students": analytics["total"],
        "this_month": analytics["this_month"],
        "previous_month": analytics["previous_month"],
        "growth_percentage": analytics["growth_percentage"],
        "my_registrations": students_qs.filter(created_by=request.user).count(),
    }

    return render(
        request,
        "franchise/staff_dashboard.html",
        {
            "staff_profile": staff_profile,
            "franchise": franchise,
            "stats": stats,
            "analytics": analytics,
        },
    )


# ─── Staff management ─────────────────────────────────────────────────────────


@franchise_owner_required
def staff_list(request):
    """List all staff members of the franchise owner's franchise."""
    profile = request.user.franchise_profile
    staff = profile.staff_members.select_related("user").order_by("name")

    return render(
        request,
        "franchise/staff_list.html",
        {
            "staff": staff,
            "profile": profile,
            "page_title": "Staff Management",
        },
    )


@franchise_owner_required
def staff_invite(request):
    """Invite a new staff member to the franchise."""
    profile = request.user.franchise_profile
    form = FranchiseStaffInviteForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        email = form.cleaned_data["email"].lower().strip()
        name = form.cleaned_data["name"]
        role = form.cleaned_data["role"]

        existing_staff = FranchiseStaff.objects.filter(
            franchise=profile, email__iexact=email
        ).first()

        if existing_staff and existing_staff.user_id:
            messages.info(request, f"{email} already has an account in your franchise.")
            return redirect("franchise:staff_list")

        # Invitation acceptance creates a new portal account; it must never
        # reuse an account selected through either its email or username.
        if User.objects.filter(
            Q(email__iexact=email) | Q(username__iexact=email)
        ).exists():
            form.add_error(
                "email",
                "This email address is already associated with an account. "
                "Please use a different email.",
            )
            return render(
                request,
                "franchise/staff_invite.html",
                {"form": form, "page_title": "Invite Staff"},
            )

        if existing_staff:
            if _send_staff_invitation(request, existing_staff):
                messages.success(request, f"Invitation resent to {email}.")
            else:
                messages.error(request, f"The invitation email to {email} could not be sent.")
            return redirect("franchise:staff_list")

        staff = FranchiseStaff.objects.create(
            franchise=profile,
            name=name,
            email=email,
            role=role,
            is_active=True,
        )

        if _send_staff_invitation(request, staff):
            messages.success(
                request,
                f"Invitation sent to {email}. They will receive a link to set their password.",
            )
        else:
            messages.error(
                request,
                f"The staff record was created, but the invitation email to {email} could not be sent. Resend it after checking email configuration.",
            )
        return redirect("franchise:staff_list")

    return render(
        request,
        "franchise/staff_invite.html",
        {"form": form, "page_title": "Invite Staff Member"},
    )


def _send_staff_invitation(request, staff: FranchiseStaff):
    """
    Create a new invitation token (invalidating the old one) and send
    the invitation email via the configured email backend.
    """
    # Invalidate previous tokens
    FranchiseStaffInvitation.objects.filter(staff=staff).update(used=True)

    # Create new token
    invitation = FranchiseStaffInvitation.objects.create(
        staff=staff,
        token=secrets.token_urlsafe(48),
    )

    invite_path = reverse(
        "franchise:accept_staff_invitation",
        kwargs={"token": invitation.token},
    )
    invite_url = request.build_absolute_uri(invite_path)

    subject = "Invitation to join Rajvans Group of Educations – Franchise Portal"
    message = f"""
Dear {staff.name},

You have been invited to join the franchise portal of Rajvans Group of Educations
as a {staff.get_role_display()} for {staff.franchise.business_name or str(staff.franchise)}.

Please use the following link to create your account:

{invite_url}

This link is valid for 24 hours.

If you did not expect this invitation, please ignore this email.

Regards,
Rajvans Group of Educations
"""

    try:
        sent_count = send_mail(
            subject=subject,
            message=message.strip(),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[staff.email],
            fail_silently=False,
        )
        return sent_count == 1
    except (OSError, smtplib.SMTPException):
        logger.warning("Staff invitation email delivery failed.")
        return False


def accept_staff_invitation(request, token):
    """
    Staff member accepts their invitation and sets a password.
    """
    invitation = get_object_or_404(
        FranchiseStaffInvitation.objects.select_related("staff", "staff__franchise"),
        token=token,
    )

    if invitation.used:
        messages.error(request, "This invitation link has already been used.")
        return redirect("franchise:login")

    if invitation.is_expired:
        messages.error(
            request,
            "This invitation link has expired (valid for 24 hours). "
            "Please ask your franchise manager to resend the invitation.",
        )
        return redirect("franchise:login")

    staff = invitation.staff

    if not staff.is_active:
        messages.error(request, "This staff account has been deactivated.")
        return redirect("franchise:login")
    if staff.user_id:
        messages.error(
            request,
            "This invitation is no longer valid. Please contact the franchise owner.",
        )
        return redirect("franchise:login")

    form = FranchiseSetPasswordForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            invitation = (
                FranchiseStaffInvitation.objects
                .select_for_update()
                .select_related("staff")
                .get(pk=invitation.pk)
            )
            staff = invitation.staff

            if invitation.used or invitation.is_expired or not staff.is_active or staff.user_id:
                messages.error(
                    request,
                    "This invitation is no longer valid. Please request a new one.",
                )
                return redirect("franchise:login")

            if User.objects.filter(
                Q(email__iexact=staff.email) | Q(username__iexact=staff.email)
            ).exists():
                messages.error(
                    request,
                    "An account already exists for this invitation. Please contact the franchise owner.",
                )
                return redirect("franchise:login")

            # Validate password
            try:
                validate_password(form.cleaned_data["password1"])
            except ValidationError as e:
                form.add_error("password1", e)
                return render(
                    request,
                    "franchise/accept_invitation.html",
                    {"form": form, "staff": staff},
                )

            name_parts = staff.name.split()
            user = User.objects.create_user(
                username=staff.email,
                email=staff.email,
                password=form.cleaned_data["password1"],
                first_name=name_parts[0] if name_parts else "",
                last_name=" ".join(name_parts[1:]),
                is_active=True,
                is_staff=False,
                is_superuser=False,
            )

            staff.user = user
            staff.save(update_fields=["user", "updated_at"])

            invitation.used = True
            invitation.save(update_fields=["used"])

        login(
            request,
            user,
            backend="apps.franchise.backends.EmailOrUsernameBackend",
        )
        messages.success(
            request,
            f"Welcome, {user.first_name}! Your account has been activated.",
        )
        return redirect("franchise:staff_dashboard")

    return render(
        request,
        "franchise/accept_invitation.html",
        {"form": form, "staff": staff},
    )


@franchise_owner_required
def staff_toggle_active(request, pk):
    """Activate or deactivate a staff member."""
    profile = request.user.franchise_profile
    staff = get_object_or_404(FranchiseStaff, pk=pk, franchise=profile)

    if request.method == "POST":
        staff.is_active = not staff.is_active
        staff.save(update_fields=["is_active", "updated_at"])

        # Also deactivate/activate their user account if they have one
        if staff.user:
            staff.user.is_active = staff.is_active
            staff.user.save(update_fields=["is_active"])

        action = "activated" if staff.is_active else "deactivated"
        messages.success(request, f"Staff member {staff.name} has been {action}.")

    return redirect("franchise:staff_list")


@franchise_owner_required
def staff_resend_invitation(request, pk):
    """Resend invitation to a pending staff member."""
    profile = request.user.franchise_profile
    staff = get_object_or_404(FranchiseStaff, pk=pk, franchise=profile)

    if request.method == "POST":
        if staff.user and staff.user.is_active:
            messages.info(request, f"{staff.name} has already activated their account.")
        else:
            _send_staff_invitation(request, staff)
            messages.success(request, f"Invitation resent to {staff.email}.")

    return redirect("franchise:staff_list")


# ─── Password management ──────────────────────────────────────────────────────


@portal_required
def change_password(request):
    """Authenticated franchise user changes their own password."""
    form = FranchisePasswordChangeForm(request.POST or None, user=request.user)

    if request.method == "POST" and form.is_valid():
        new_password = form.cleaned_data["new_password1"]

        try:
            validate_password(new_password, request.user)
        except ValidationError as e:
            form.add_error("new_password1", e)
            return render(
                request,
                "franchise/change_password.html",
                {"form": form},
            )

        request.user.set_password(new_password)
        request.user.save()

        # Keep the user logged in after password change
        update_session_auth_hash(request, request.user)

        messages.success(request, "Your password has been changed successfully.")
        return redirect("franchise:dashboard")

    return render(
        request,
        "franchise/change_password.html",
        {"form": form, "page_title": "Change Password"},
    )


def forgot_password(request):
    """
    Step 1: User enters their email address to request a password reset.
    Sends a reset link via the configured email backend (console in dev).
    """
    if request.user.is_authenticated:
        return redirect("franchise:dashboard")

    form = FranchiseForgotPasswordForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        email = form.cleaned_data["email"].lower().strip()

        # Find the user — do not reveal whether the email exists
        user = User.objects.filter(email__iexact=email).first()

        if user and user.is_active and not user.is_staff and not user.is_superuser:
            _send_password_reset(request, user)

        # Always show success regardless (prevents email enumeration)
        messages.success(
            request,
            "If that email address is associated with a franchise account, "
            "a password reset link will be sent. If you do not receive it, contact support.",
        )
        return redirect("franchise:login")

    return render(
        request,
        "franchise/forgot_password.html",
        {"form": form, "page_title": "Reset Password"},
    )


def _send_password_reset(request, user):
    """
    Generate a password-reset token and send the reset email.
    Uses Django's built-in PasswordResetTokenGenerator for secure,
    single-use, time-limited tokens.
    """
    from django.contrib.auth.tokens import default_token_generator
    from django.utils.encoding import force_bytes
    from django.utils.http import urlsafe_base64_encode

    token = default_token_generator.make_token(user)
    uid = urlsafe_base64_encode(force_bytes(user.pk))

    reset_path = reverse(
        "franchise:reset_password",
        kwargs={"uidb64": uid, "token": token},
    )
    reset_url = request.build_absolute_uri(reset_path)

    subject = "Password Reset – Rajvans Franchise Portal"
    message = f"""
Dear {user.get_full_name() or user.username},

A password reset was requested for your franchise portal account.

Click the link below to set a new password:

{reset_url}

This link is valid for 1 hour. If you did not request a password reset,
please ignore this email. Your password will not change.

Regards,
Rajvans Group of Educations
"""
    try:
        sent_count = send_mail(
            subject=subject,
            message=message.strip(),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=False,
        )
        return sent_count == 1
    except (OSError, smtplib.SMTPException):
        logger.warning("Password reset email delivery failed.")
        return False


def reset_password(request, uidb64, token):
    """
    Step 2: User clicks the reset link and sets a new password.
    Uses Django's PasswordResetTokenGenerator to validate the token.
    """
    from django.contrib.auth.tokens import default_token_generator
    from django.utils.encoding import force_str
    from django.utils.http import urlsafe_base64_decode

    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    if user is None or not default_token_generator.check_token(user, token):
        messages.error(
            request,
            "This password reset link is invalid or has expired. "
            "Please request a new one.",
        )
        return redirect("franchise:forgot_password")

    form = FranchisePasswordResetForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        new_password = form.cleaned_data["password1"]

        try:
            validate_password(new_password, user)
        except ValidationError as e:
            form.add_error("password1", e)
            return render(
                request,
                "franchise/reset_password.html",
                {"form": form, "uidb64": uidb64, "token": token},
            )

        user.set_password(new_password)
        user.save()

        messages.success(
            request,
            "Your password has been reset successfully. You can now log in.",
        )
        return redirect("franchise:login")

    return render(
        request,
        "franchise/reset_password.html",
        {"form": form, "uidb64": uidb64, "token": token, "page_title": "Set New Password"},
    )


# ─── Profile ──────────────────────────────────────────────────────────────────


@portal_required
def franchise_profile(request):
    """View/edit the franchise profile."""
    if not hasattr(request.user, "franchise_profile"):
        messages.warning(request, "Profile is only available to franchise owners.")
        return redirect("franchise:staff_dashboard")

    profile = request.user.franchise_profile

    return render(
        request,
        "franchise/profile.html",
        {"profile": profile, "page_title": "Franchise Profile"},
    )
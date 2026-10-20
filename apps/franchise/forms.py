"""
Franchise portal forms.
"""

from django import forms
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.db.models import Q

from apps.students.models import Student

from .models import FranchiseApplication, FranchiseProfile, FranchiseStaff


class CertificateStudentSelectionForm(forms.Form):
    student = forms.ModelChoiceField(
        queryset=Student.objects.none(),
        label="Student",
        empty_label="Choose a student",
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    def __init__(self, *args, franchise, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["student"].queryset = (
            Student.objects.filter(franchise=franchise)
            .select_related("course")
            .order_by("full_name", "registration_number")
        )
        self.fields["student"].label_from_instance = (
            lambda student: (
                f"{student.full_name} — {student.registration_number} — "
                f"{student.course.name}"
            )
        )


class FranchiseProfilePhotoForm(forms.ModelForm):
    class Meta:
        model = FranchiseProfile
        fields = ["profile_image"]
        widgets = {
            "profile_image": forms.FileInput(
                attrs={"accept": "image/jpeg,image/png,image/webp"}
            )
        }


class FranchiseStaffPhotoForm(forms.ModelForm):
    class Meta:
        model = FranchiseStaff
        fields = ["profile_image"]
        widgets = {
            "profile_image": forms.FileInput(
                attrs={"accept": "image/jpeg,image/png,image/webp"}
            )
        }


class FranchiseRegistrationForm(forms.ModelForm):

    class Meta:
        model = FranchiseApplication

        fields = [
            "name",
            "mobile",
            "email",
            "city",
            "state",
            "business_name",
            "address",
            "experience",
            "message",
        ]

        widgets = {
            "address": forms.Textarea(attrs={"rows": 3}),
            "experience": forms.Textarea(attrs={"rows": 3}),
            "message": forms.Textarea(attrs={"rows": 4}),
        }

    def clean_email(self):
        email = self.cleaned_data["email"].lower().strip()

        if User.objects.filter(
            Q(username__iexact=email) | Q(email__iexact=email)
        ).exists():
            raise forms.ValidationError(
                "An account with this email already exists."
            )

        existing_application = (
            FranchiseApplication.objects
            .filter(
                email__iexact=email,
                status__in=["pending", "review", "contacted"],
            )
            .exists()
        )

        if existing_application:
            raise forms.ValidationError(
                "A franchise application with this email "
                "is already under review."
            )

        return email


class FranchiseLoginForm(forms.Form):

    email = forms.EmailField(
        widget=forms.EmailInput(attrs={"placeholder": "your@email.com"})
    )

    password = forms.CharField(
        widget=forms.PasswordInput(attrs={"placeholder": "Password"})
    )

    def __init__(self, *args, request=None, **kwargs):
        self.request = request
        self.user_cache = None
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned_data = super().clean()
        email = cleaned_data.get("email")
        password = cleaned_data.get("password")

        if email and password:
            email = email.strip().lower()

            application = (
                FranchiseApplication.objects
                .filter(email__iexact=email)
                .order_by("-created_at")
                .first()
            )

            if application:
                if application.status == "rejected":
                    raise forms.ValidationError(
                        "Your franchise application has been rejected."
                    )
                if application.status != "approved":
                    raise forms.ValidationError(
                        "Your franchise application is still "
                        "awaiting admin approval."
                    )

            user_candidate = User.objects.filter(
                Q(email__iexact=email) | Q(username__iexact=email)
            ).order_by("id").first()

            if (
                user_candidate
                and user_candidate.check_password(password)
                and not user_candidate.is_active
            ):
                raise forms.ValidationError(
                    "Your franchise account has not been activated yet."
                )

            if user_candidate and user_candidate.check_password(password):
                try:
                    staff_profile = user_candidate.franchise_staff_profile
                except FranchiseStaff.DoesNotExist:
                    staff_profile = None
                if staff_profile and not staff_profile.is_active:
                    raise forms.ValidationError(
                        "Your franchise staff account has been deactivated."
                    )

            user = authenticate(
                self.request,
                username=email,
                password=password,
            )

            if user is None:
                raise forms.ValidationError("Invalid email or password.")

            if user.is_superuser:
                raise forms.ValidationError(
                    "Use the Django Admin login for superuser accounts."
                )
            if user.is_staff:
                raise forms.ValidationError(
                    "This account cannot use the franchise portal."
                )

            if not user.is_active:
                raise forms.ValidationError(
                    "Your franchise account has not been activated yet."
                )

            if not hasattr(user, "franchise_profile"):
                try:
                    staff_profile = user.franchise_staff_profile
                except FranchiseStaff.DoesNotExist:
                    staff_profile = None
                if staff_profile is None:
                    raise forms.ValidationError(
                        "This account is not associated with an active franchise."
                    )

            self.user_cache = user
            cleaned_data["user"] = user

        return cleaned_data

    def get_user(self):
        return self.user_cache


class CertificateRequestConfirmForm(forms.Form):
    confirm = forms.BooleanField(
        required=True,
        label="I have reviewed the student and course details above.",
    )


class FranchiseSetPasswordForm(forms.Form):
    """Used for both franchise owner activation and staff invitation acceptance."""

    password1 = forms.CharField(
        label="New Password",
        widget=forms.PasswordInput(attrs={"placeholder": "Choose a strong password"}),
        min_length=8,
    )

    password2 = forms.CharField(
        label="Confirm Password",
        widget=forms.PasswordInput(attrs={"placeholder": "Repeat your password"}),
        min_length=8,
    )

    def clean(self):
        cleaned_data = super().clean()
        password1 = cleaned_data.get("password1")
        password2 = cleaned_data.get("password2")

        if password1 and password2 and password1 != password2:
            raise forms.ValidationError("Passwords do not match.")

        return cleaned_data


class FranchisePasswordChangeForm(forms.Form):
    """Form for an authenticated user to change their own password."""

    current_password = forms.CharField(
        label="Current Password",
        widget=forms.PasswordInput(attrs={"placeholder": "Current password"}),
    )

    new_password1 = forms.CharField(
        label="New Password",
        widget=forms.PasswordInput(attrs={"placeholder": "New password"}),
        min_length=8,
    )

    new_password2 = forms.CharField(
        label="Confirm New Password",
        widget=forms.PasswordInput(attrs={"placeholder": "Repeat new password"}),
        min_length=8,
    )

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def clean_current_password(self):
        current = self.cleaned_data.get("current_password")
        if self.user and not self.user.check_password(current):
            raise forms.ValidationError("Your current password is incorrect.")
        return current

    def clean(self):
        cleaned_data = super().clean()
        p1 = cleaned_data.get("new_password1")
        p2 = cleaned_data.get("new_password2")

        if p1 and p2 and p1 != p2:
            raise forms.ValidationError("New passwords do not match.")

        return cleaned_data


class FranchiseForgotPasswordForm(forms.Form):
    """Step 1: Enter email to request a password reset link."""

    email = forms.EmailField(
        label="Email Address",
        widget=forms.EmailInput(attrs={"placeholder": "your@email.com"}),
    )


class FranchisePasswordResetForm(forms.Form):
    """Step 2: Enter and confirm new password after clicking the reset link."""

    password1 = forms.CharField(
        label="New Password",
        widget=forms.PasswordInput(attrs={"placeholder": "Choose a strong password"}),
        min_length=8,
    )

    password2 = forms.CharField(
        label="Confirm Password",
        widget=forms.PasswordInput(attrs={"placeholder": "Repeat your password"}),
        min_length=8,
    )

    def clean(self):
        cleaned_data = super().clean()
        p1 = cleaned_data.get("password1")
        p2 = cleaned_data.get("password2")

        if p1 and p2 and p1 != p2:
            raise forms.ValidationError("Passwords do not match.")

        return cleaned_data


class FranchiseStaffInviteForm(forms.Form):
    """Form used by franchise owners to invite a new staff member."""

    name = forms.CharField(
        max_length=180,
        label="Full Name",
        widget=forms.TextInput(attrs={"placeholder": "Staff member's full name"}),
    )

    email = forms.EmailField(
        label="Email Address",
        widget=forms.EmailInput(attrs={"placeholder": "staff@email.com"}),
    )

    role = forms.ChoiceField(
        choices=FranchiseStaff.ROLE_CHOICES,
        label="Role",
    )

    def clean_email(self):
        return self.cleaned_data["email"].lower().strip()
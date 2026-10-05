from collections.abc import MutableMapping

from django import forms
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.db.models import Q

from .models import FranchiseApplication


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
            Q(username__iexact=email) |
            Q(email__iexact=email)
        ).exists():
            raise forms.ValidationError(
                "An account with this email already exists."
            )

        existing_application = (
            FranchiseApplication.objects
            .filter(
                email__iexact=email,
                status__in=[
                    "pending",
                    "review",
                    "contacted",
                ],
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

    email = forms.EmailField()

    password = forms.CharField(
        widget=forms.PasswordInput
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

            user = authenticate(
                self.request,
                username=email,
                password=password,
            )

            if user is None:
                raise forms.ValidationError(
                    "Invalid email or password."
                )

            if user.is_staff or user.is_superuser:
                raise forms.ValidationError(
                    "Use the Django Admin login for staff accounts."
                )

            if not user.is_active:
                raise forms.ValidationError(
                    "Your franchise account has not been activated yet."
                )

            self.user_cache = user
            cleaned_data["user"] = user

        return cleaned_data

    def get_user(self):
        return self.user_cache


class FranchiseSetPasswordForm(forms.Form):

    password1 = forms.CharField(
        label="New Password",
        widget=forms.PasswordInput,
        min_length=8,
    )

    password2 = forms.CharField(
        label="Confirm Password",
        widget=forms.PasswordInput,
        min_length=8,
    )

    def clean(self):
        cleaned_data = super().clean()

        password1 = cleaned_data.get("password1")
        password2 = cleaned_data.get("password2")

        if password1 and password2 and password1 != password2:
            raise forms.ValidationError(
                "Passwords do not match."
            )

        return cleaned_data


class cleaned_data(MutableMapping):
    """A dict-like container for validated form values."""

    def __init__(self, *args, **kwargs):
        self._store = {}
        self.update(*args, **kwargs)

    def __getitem__(self, key):
        return self._store[key]

    def __setitem__(self, key, value):
        self._store[str(key)] = value

    def __delitem__(self, key):
        del self._store[key]

    def __iter__(self):
        return iter(self._store)

    def __len__(self):
        return len(self._store)

    def get(self, key, default=None):
        return self._store.get(key, default)

    def update(self, *args, **kwargs):
        for mapping in args:
            if hasattr(mapping, "items"):
                items = mapping.items()
            else:
                items = mapping
            for key, value in items:
                self[key] = value
        for key, value in kwargs.items():
            self[key] = value

    def copy(self):
        return cleaned_data(self._store)

    def as_dict(self):
        return dict(self._store)
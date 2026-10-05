import secrets

from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from .forms import (
    FranchiseLoginForm,
    FranchiseRegistrationForm,
    FranchiseSetPasswordForm,
)
from .models import FranchiseActivationToken


def landing(request):
    return render(
        request,
        "franchise/landing.html",
    )


def register(request):

    if request.user.is_authenticated and hasattr(
        request.user,
        "franchise_profile",
    ):
        return redirect("franchise:dashboard")

    form = FranchiseRegistrationForm(
        request.POST or None
    )

    if request.method == "POST" and form.is_valid():

        application = form.save()

        messages.success(
            request,
            "Your franchise interest has been submitted successfully. "
            "Our team will review your application and contact you "
            "after approval.",
        )

        return redirect("franchise:landing")

    return render(
        request,
        "franchise/register.html",
        {
            "form": form,
        },
    )


def franchise_login(request):

    if request.user.is_authenticated:

        if hasattr(
            request.user,
            "franchise_profile",
        ):
            return redirect("franchise:dashboard")

        if (
            request.user.is_staff
            or request.user.is_superuser
        ):
            return redirect("admin:index")

        return redirect("core:home")

    if request.method == "POST":

        form = FranchiseLoginForm(
            request.POST,
            request=request,
        )

        if form.is_valid():

            user = form.get_user()

            login(request, user)

            return redirect(
                "franchise:dashboard"
            )

    else:
        form = FranchiseLoginForm(
            request=request
        )

    return render(
        request,
        "franchise/login.html",
        {
            "form": form,
        },
    )


def activate_account(request, token):

    activation = get_object_or_404(
        FranchiseActivationToken.objects.select_related(
            "application",
            "application__user",
        ),
        token=token,
    )

    if activation.used:
        messages.error(
            request,
            "This activation link has already been used.",
        )
        return redirect("franchise:login")

    application = activation.application

    if application.status != "approved":
        messages.error(
            request,
            "This franchise application has not been approved.",
        )
        return redirect("franchise:login")

    if not application.user:
        messages.error(
            request,
            "The franchise account has not been created yet.",
        )
        return redirect("franchise:login")

    user = application.user

    form = FranchiseSetPasswordForm(
        request.POST or None
    )

    if request.method == "POST" and form.is_valid():

        user.set_password(
            form.cleaned_data["password1"]
        )

        user.is_active = True
        user.save(
            update_fields=[
                "password",
                "is_active",
            ]
        )

        activation.used = True
        activation.save(
            update_fields=["used"]
        )

        login(
            request,
            user,
            backend="apps.franchise.backends.EmailOrUsernameBackend",
        )

        messages.success(
            request,
            "Your franchise account has been activated successfully.",
        )

        return redirect(
            "franchise:dashboard"
        )

    return render(
        request,
        "franchise/activate.html",
        {
            "form": form,
            "application": application,
        },
    )


@login_required
def dashboard(request):

    if not hasattr(
        request.user,
        "franchise_profile",
    ):
        messages.warning(
            request,
            "Your franchise account has not been approved.",
        )

        return redirect("core:home")

    return render(
        request,
        "franchise/dashboard.html",
        {
            "profile": request.user.franchise_profile,
            "applications": request.user.franchise_applications.all(),
        },
    )


def franchise_logout(request):

    if request.method == "POST":

        logout(request)

        messages.info(
            request,
            "You have been logged out.",
        )

    return redirect("core:home")
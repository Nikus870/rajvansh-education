"""
Student views for the Rajvans franchise portal.

All views enforce franchise data isolation:
  - franchise_required decorator ensures the user has a FranchiseProfile.
  - Querysets are always filtered to the logged-in user's franchise.
  - Parent administrators (is_superuser) can see all records.
"""

import csv
from functools import wraps

from django.contrib import messages
from django.contrib.auth import logout
from django.core.exceptions import ObjectDoesNotExist
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from .forms import StudentEditForm, StudentRegistrationForm, StudentSearchForm
from .models import Student
from apps.franchise.profile_images import serve_profile_image


# ─── Helpers ──────────────────────────────────────────────────────────────────


def franchise_required(view_func):
    """
    Decorator that ensures:
    1. The user is authenticated.
    2. The user has an active FranchiseProfile  OR  is a superuser
       (superusers can access franchise views for support purposes).
    """

    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            from django.urls import reverse
            return redirect(f"/franchise/login/?next={request.path}")

        is_franchise_owner = hasattr(request.user, "franchise_profile")
        try:
            staff_profile = request.user.franchise_staff_profile
        except ObjectDoesNotExist:
            staff_profile = None

        if staff_profile and not staff_profile.is_active:
            logout(request)
            messages.error(request, "Your staff account is inactive.")
            return redirect("franchise:login")

        is_franchise_staff = staff_profile is not None
        is_admin = request.user.is_superuser

        if not (is_franchise_owner or is_franchise_staff or is_admin):
            messages.warning(
                request,
                "You do not have access to the franchise portal.",
            )
            return redirect("core:home")

        return view_func(request, *args, **kwargs)

    return _wrapped


def get_franchise_profile(user):
    """
    Return the FranchiseProfile for the logged-in user.

    - Franchise owner  → their own profile.
    - Franchise staff  → the franchise they work for.
    - Superuser        → None (they can see all records).
    """
    if user.is_superuser:
        return None

    if hasattr(user, "franchise_profile"):
        return user.franchise_profile

    if hasattr(user, "franchise_staff_profile"):
        return user.franchise_staff_profile.franchise

    return None


def get_student_queryset(user):
    """
    Return a filtered queryset appropriate for the user's role.
    """
    qs = Student.objects.select_related(
        "course", "university", "franchise", "created_by"
    )

    franchise = get_franchise_profile(user)
    if franchise is not None:
        qs = qs.filter(franchise=franchise)

    return qs


def _csv_safe(value):
    if isinstance(value, str) and value.lstrip(" \t\r\n")[:1] in {"=", "+", "-", "@"}:
        return f"'{value}"
    return value


# ─── Views ────────────────────────────────────────────────────────────────────


@franchise_required
def register_student(request):
    """Register a new student under the logged-in user's franchise."""
    franchise = get_franchise_profile(request.user)

    # Only franchise owners and staff can register students; they must
    # belong to a franchise.
    if franchise is None and not request.user.is_superuser:
        messages.error(request, "You must be associated with a franchise to register students.")
        return redirect("franchise:dashboard")

    # Superusers registering through the portal shouldn't happen in normal
    # use — they use the admin. Guard it.
    if request.user.is_superuser and franchise is None:
        messages.error(
            request,
            "Parent administrators should use Django Admin to manage students.",
        )
        return redirect("franchise:dashboard")

    form = StudentRegistrationForm(
        request.POST or None,
        request.FILES or None,
    )

    if request.method == "POST" and form.is_valid():
        student = form.save(commit=False)
        student.franchise = franchise
        student.created_by = request.user
        student.save()

        messages.success(
            request,
            f"Student {student.full_name} registered successfully. "
            f"Registration No: {student.registration_number}",
        )
        if request.GET.get("next") == "certificate_request":
            return redirect(
                reverse(
                    "franchise:certificate_request_create",
                    args=(student.pk,),
                )
            )
        return redirect("students:list")

    return render(
        request,
        "students/register.html",
        {"form": form, "page_title": "Register Student"},
    )


@franchise_required
def student_list(request):
    """
    Paginated, searchable, filterable list of students.

    Franchise users see only their own franchise's students.
    Parent administrators see all students.
    """
    franchise = get_franchise_profile(request.user)
    qs = get_student_queryset(request.user)

    form = StudentSearchForm(request.GET or None)

    if form.is_valid():
        q = form.cleaned_data.get("q")
        course = form.cleaned_data.get("course")
        university = form.cleaned_data.get("university")
        study_mode = form.cleaned_data.get("study_mode")
        admission_status = form.cleaned_data.get("admission_status")
        date_from = form.cleaned_data.get("date_from")
        date_to = form.cleaned_data.get("date_to")

        if q:
            qs = qs.filter(
                Q(full_name__icontains=q)
                | Q(registration_number__icontains=q)
                | Q(mobile__icontains=q)
            )
        if course:
            qs = qs.filter(course=course)
        if university:
            qs = qs.filter(university=university)
        if study_mode:
            qs = qs.filter(study_mode=study_mode)
        if admission_status:
            qs = qs.filter(admission_status=admission_status)
        if date_from:
            qs = qs.filter(created_at__date__gte=date_from)
        if date_to:
            qs = qs.filter(created_at__date__lte=date_to)

    paginator = Paginator(qs, 25)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(
        request,
        "students/list.html",
        {
            "page_obj": page_obj,
            "form": form,
            "total": qs.count(),
            "page_title": "All Students",
            "is_admin_view": request.user.is_superuser,
        },
    )


@franchise_required
def student_detail(request, pk):
    """View details of a single student."""
    qs = get_student_queryset(request.user)
    student = get_object_or_404(qs, pk=pk)

    return render(
        request,
        "students/detail.html",
        {"student": student, "page_title": f"Student – {student.full_name}"},
    )


@franchise_required
def student_edit(request, pk):
    """Edit a student's details."""
    qs = get_student_queryset(request.user)
    student = get_object_or_404(qs, pk=pk)

    form = StudentEditForm(
        request.POST or None,
        request.FILES or None,
        instance=student,
    )

    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, f"Student {student.full_name} updated successfully.")
        return redirect("students:detail", pk=student.pk)

    return render(
        request,
        "students/edit.html",
        {
            "form": form,
            "student": student,
            "page_title": f"Edit – {student.full_name}",
        },
    )


@franchise_required
def student_profile_image(request, pk):
    student = get_object_or_404(get_student_queryset(request.user), pk=pk)
    return serve_profile_image(student.profile_image)


@franchise_required
def student_export_csv(request):
    """
    Export filtered student list to CSV.

    Applies the same filters as student_list.
    Respects franchise isolation.
    """
    qs = get_student_queryset(request.user)

    # Apply same filters
    form = StudentSearchForm(request.GET or None)
    if form.is_valid():
        q = form.cleaned_data.get("q")
        course = form.cleaned_data.get("course")
        university = form.cleaned_data.get("university")
        study_mode = form.cleaned_data.get("study_mode")
        admission_status = form.cleaned_data.get("admission_status")
        date_from = form.cleaned_data.get("date_from")
        date_to = form.cleaned_data.get("date_to")

        if q:
            qs = qs.filter(
                Q(full_name__icontains=q)
                | Q(registration_number__icontains=q)
                | Q(mobile__icontains=q)
            )
        if course:
            qs = qs.filter(course=course)
        if university:
            qs = qs.filter(university=university)
        if study_mode:
            qs = qs.filter(study_mode=study_mode)
        if admission_status:
            qs = qs.filter(admission_status=admission_status)
        if date_from:
            qs = qs.filter(created_at__date__gte=date_from)
        if date_to:
            qs = qs.filter(created_at__date__lte=date_to)

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="students.csv"'

    writer = csv.writer(response)
    writer.writerow([
        "Registration No.",
        "Full Name",
        "Guardian Name",
        "Date of Birth",
        "Gender",
        "Mobile",
        "Email",
        "Course",
        "University",
        "Study Mode",
        "Previous Qualification",
        "Admission Date",
        "Admission Status",
        "Fee Status",
        "Franchise",
        "Registered By",
        "Created At",
    ])

    for s in qs.iterator():
        writer.writerow([_csv_safe(value) for value in [
            s.registration_number,
            s.full_name,
            s.guardian_name,
            s.date_of_birth or "",
            s.get_gender_display() if s.gender else "",
            s.mobile,
            s.email,
            s.course.name,
            s.university.name,
            s.get_study_mode_display(),
            s.get_previous_qualification_display() if s.previous_qualification else "",
            s.admission_date or "",
            s.get_admission_status_display(),
            s.get_fee_status_display(),
            str(s.franchise),
            s.created_by.get_full_name() if s.created_by else "",
            s.created_at.strftime("%Y-%m-%d %H:%M"),
        ]])

    return response

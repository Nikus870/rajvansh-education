import logging

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET

from apps.students.models import Student
from apps.students.views import get_franchise_profile

from .forms import CertificateRequestConfirmForm
from .models import CertificateRequest
from .views import portal_required

logger = logging.getLogger(__name__)


@portal_required
def certificate_requests(request):
    franchise = get_franchise_profile(request.user)
    if franchise is None:
        raise PermissionDenied

    query = request.GET.get("q", "").strip()
    students = Student.objects.none()
    if query:
        students = (
            Student.objects.filter(franchise=franchise)
            .filter(Q(full_name__icontains=query) | Q(registration_number__icontains=query))
            .exclude(
                Q(certificate_requests__status=CertificateRequest.STATUS_PENDING)
                | Q(
                    certificate_requests__status=CertificateRequest.STATUS_APPROVED,
                    certificate_requests__is_revoked=False,
                )
            )
            .select_related("course", "university")
            .distinct()
            .order_by("full_name", "pk")
        )

    history = (
        CertificateRequest.objects.filter(franchise=franchise)
        .select_related("student", "student__course", "student__university")
        .order_by("-requested_at")
    )
    return render(
        request,
        "franchise/certificate_requests.html",
        {
            "history": history,
            "student_results": Paginator(students, 25).get_page(
                request.GET.get("student_page")
            ),
            "query": query,
        },
    )


@portal_required
def certificate_request_create(request, student_id):
    franchise = get_franchise_profile(request.user)
    if franchise is None:
        raise PermissionDenied
    student = get_object_or_404(
        Student.objects.select_related("course", "university", "franchise"),
        pk=student_id,
        franchise=franchise,
    )
    open_request = CertificateRequest.objects.filter(student=student).filter(
        Q(status=CertificateRequest.STATUS_PENDING)
        | Q(status=CertificateRequest.STATUS_APPROVED, is_revoked=False)
    ).exists()
    form = CertificateRequestConfirmForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        if open_request:
            messages.warning(
                request,
                "A pending request or active certificate already exists for this student.",
            )
            return redirect("franchise:certificate_requests")
        try:
            with transaction.atomic():
                CertificateRequest.objects.create(
                    student=student,
                    franchise=franchise,
                    requested_by=request.user,
                )
        except IntegrityError:
            messages.warning(
                request,
                "A pending request or active certificate already exists for this student.",
            )
        else:
            messages.success(request, "Certificate request submitted for superuser review.")
        return redirect("franchise:certificate_requests")

    return render(
        request,
        "franchise/certificate_request_confirm.html",
        {
            "student": student,
            "form": form,
            "already_requested": open_request,
        },
    )


def _certificate_file_response(certificate_request, *, attachment=True):
    if (
        certificate_request.status != CertificateRequest.STATUS_APPROVED
        or certificate_request.is_revoked
        or not certificate_request.certificate_file
    ):
        raise Http404
    try:
        file_obj = certificate_request.certificate_file.open("rb")
    except (FileNotFoundError, OSError):
        logger.exception(
            "Certificate file is missing or inaccessible for request ID %s.",
            certificate_request.pk,
        )
        raise Http404("Certificate file is unavailable.")
    return FileResponse(
        file_obj,
        as_attachment=attachment,
        filename=f"{certificate_request.certificate_number}.pdf",
        content_type="application/pdf",
    )


@portal_required
@require_GET
def certificate_download(request, request_id):
    if request.user.is_superuser:
        certificate_request = get_object_or_404(
            CertificateRequest.objects.select_related("student"),
            pk=request_id,
        )
    else:
        franchise = get_franchise_profile(request.user)
        if franchise is None:
            raise PermissionDenied
        certificate_request = get_object_or_404(
            CertificateRequest.objects.select_related("student"),
            pk=request_id,
            franchise=franchise,
        )
    return _certificate_file_response(certificate_request)


@require_GET
def certificate_verify(request, token):
    certificate_request = (
        CertificateRequest.objects.select_related("student", "student__course")
        .filter(verification_token=token)
        .first()
    )
    valid = bool(
        certificate_request
        and certificate_request.status == CertificateRequest.STATUS_APPROVED
        and not certificate_request.is_revoked
    )
    return render(
        request,
        "franchise/certificate_verify.html",
        {
            "valid": valid,
            "certificate": certificate_request if valid else None,
        },
    )


@require_GET
def admin_certificate_download(request, request_id):
    if not request.user.is_authenticated or not request.user.is_superuser:
        raise PermissionDenied
    certificate_request = get_object_or_404(CertificateRequest, pk=request_id)
    return _certificate_file_response(certificate_request)

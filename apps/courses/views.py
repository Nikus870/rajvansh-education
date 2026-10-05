from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, render

from .models import Course


def course_list(request):
    """
    Public Courses page.

    Shows only active courses that have been added/managed
    through Django Admin.

    No search or filtering is applied on this page.
    """

    qs = (
        Course.objects
        .filter(active=True)
        .select_related("category", "university")
        .order_by("name")
    )

    paginator = Paginator(qs, 9)

    page_obj = paginator.get_page(
        request.GET.get("page")
    )

    return render(
        request,
        "courses/list.html",
        {
            "page_obj": page_obj,
        },
    )


def course_detail(request, slug):
    course = get_object_or_404(
        Course.objects.select_related(
            "category",
            "university",
        ),
        slug=slug,
        active=True,
    )

    return render(
        request,
        "courses/detail.html",
        {
            "course": course,
        },
    )
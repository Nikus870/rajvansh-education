from calendar import month_name
from datetime import date, datetime, time

from django.db.models import Count, Q
from django.db.models.functions import TruncMonth
from django.utils import timezone

from apps.students.models import Student


MILESTONES = (
    (10, "First Step"),
    (25, "Growing Franchise"),
    (50, "Rising Star"),
    (100, "Top Achiever"),
)


def _month_start(value):
    return date(value.year, value.month, 1)


def _add_months(value, count):
    month_index = value.year * 12 + value.month - 1 + count
    return date(month_index // 12, month_index % 12 + 1, 1)


def _local_midnight(value, current_timezone):
    return timezone.make_aware(
        datetime.combine(value, time.min),
        current_timezone,
    )


def get_student_growth_analytics(franchise, as_of=None):
    """Return registration analytics scoped to one franchise."""
    today = as_of or timezone.localdate()
    current_month = _month_start(today)
    previous_month = _add_months(current_month, -1)
    next_month = _add_months(current_month, 1)
    chart_start = _add_months(current_month, -5)
    current_timezone = timezone.get_current_timezone()

    students = Student.objects.filter(franchise=franchise)
    counts = students.aggregate(
        total=Count("pk"),
        this_month=Count(
            "pk",
            filter=Q(
                created_at__gte=_local_midnight(current_month, current_timezone),
                created_at__lt=_local_midnight(next_month, current_timezone),
            ),
        ),
        previous_month=Count(
            "pk",
            filter=Q(
                created_at__gte=_local_midnight(previous_month, current_timezone),
                created_at__lt=_local_midnight(current_month, current_timezone),
            ),
        ),
    )

    monthly_counts = {
        row["month"].date().replace(day=1): row["total"]
        for row in students.filter(
            created_at__gte=_local_midnight(chart_start, current_timezone),
            created_at__lt=_local_midnight(next_month, current_timezone),
        )
        .annotate(month=TruncMonth("created_at", tzinfo=current_timezone))
        .values("month")
        .annotate(total=Count("pk"))
    }

    chart_months = [_add_months(chart_start, offset) for offset in range(6)]
    chart_labels = [
        f"{month_name[month.month]} {month.year}" for month in chart_months
    ]
    chart_counts = [monthly_counts.get(month, 0) for month in chart_months]
    chart_data = [
        {"label": label, "count": count}
        for label, count in zip(chart_labels, chart_counts)
    ]

    previous_count = counts["previous_month"]
    growth_percentage = (
        (counts["this_month"] - previous_count) * 100 / previous_count
        if previous_count
        else None
    )

    reached_milestones = [
        {"count": threshold, "label": label}
        for threshold, label in MILESTONES
        if counts["total"] >= threshold
    ]
    next_milestone = next(
        (
            {"count": threshold, "label": label}
            for threshold, label in MILESTONES
            if counts["total"] < threshold
        ),
        None,
    )
    if next_milestone:
        next_milestone["remaining"] = next_milestone["count"] - counts["total"]

    target = franchise.monthly_student_target
    target_progress = round(counts["this_month"] * 100 / target)

    return {
        **counts,
        "growth_percentage": growth_percentage,
        "chart_labels": chart_labels,
        "chart_counts": chart_counts,
        "chart_data": chart_data,
        "target": target,
        "target_remaining": max(target - counts["this_month"], 0),
        "target_progress": target_progress,
        "target_progress_bar": min(target_progress, 100),
        "reached_milestones": reached_milestones,
        "next_milestone": next_milestone,
    }

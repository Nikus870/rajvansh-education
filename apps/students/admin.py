from django.contrib import admin

from .models import Student


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = (
        "registration_number",
        "full_name",
        "mobile",
        "course",
        "university",
        "study_mode",
        "admission_status",
        "fee_status",
        "franchise",
        "created_by",
        "created_at",
    )

    list_filter = (
        "admission_status",
        "fee_status",
        "study_mode",
        "franchise",
        "course",
        "university",
        "created_at",
    )

    search_fields = (
        "registration_number",
        "full_name",
        "mobile",
        "email",
        "franchise__business_name",
        "franchise__user__email",
    )

    readonly_fields = (
        "registration_number",
        "franchise",
        "created_by",
        "created_at",
        "updated_at",
    )

    raw_id_fields = ("created_by",)

    date_hierarchy = "created_at"

    fieldsets = (
        (
            "Identification",
            {
                "fields": (
                    "registration_number",
                    "franchise",
                    "created_by",
                )
            },
        ),
        (
            "Personal Information",
            {
                "fields": (
                    "full_name",
                    "guardian_name",
                    "date_of_birth",
                    "gender",
                    "mobile",
                    "email",
                    "address",
                )
            },
        ),
        (
            "Academic Details",
            {
                "fields": (
                    "course",
                    "university",
                    "study_mode",
                    "previous_qualification",
                    "admission_date",
                )
            },
        ),
        (
            "Status",
            {
                "fields": (
                    "admission_status",
                    "fee_status",
                    "remarks",
                )
            },
        ),
        (
            "Timestamps",
            {
                "fields": ("created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )

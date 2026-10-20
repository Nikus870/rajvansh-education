from django.urls import path

from . import certificate_views, views

app_name = "franchise"

urlpatterns = [
    # Public pages
    path("", views.landing, name="landing"),
    path("register/", views.register, name="register"),

    # Authentication
    path("login/", views.franchise_login, name="login"),
    path("logout/", views.franchise_logout, name="logout"),
    path("activate/<str:token>/", views.activate_account, name="activate"),

    # Dashboards
    path("dashboard/", views.dashboard, name="dashboard"),
    path("dashboard/staff/", views.staff_dashboard, name="staff_dashboard"),

    # Course certificate requests
    path("certificates/", certificate_views.certificate_requests, name="certificate_requests"),
    path(
        "certificates/request/",
        certificate_views.certificate_request_select,
        name="certificate_request_select",
    ),
    path(
        "certificates/request/<int:student_id>/",
        certificate_views.certificate_request_create,
        name="certificate_request_create",
    ),
    path(
        "certificates/<int:request_id>/download/",
        certificate_views.certificate_download,
        name="certificate_download",
    ),
    path(
        "certificates/verify/<str:token>/",
        certificate_views.certificate_verify,
        name="certificate_verify",
    ),

    # Staff management (franchise owner only)
    path("staff/", views.staff_list, name="staff_list"),
    path("staff/invite/", views.staff_invite, name="staff_invite"),
    path("staff/<int:pk>/toggle/", views.staff_toggle_active, name="staff_toggle"),
    path("staff/<int:pk>/resend-invite/", views.staff_resend_invitation, name="staff_resend_invitation"),
    path("staff/accept/<str:token>/", views.accept_staff_invitation, name="accept_staff_invitation"),

    # Profile
    path("profile/", views.franchise_profile, name="profile"),
    path("profile/photo/", views.profile_photo, name="profile_photo"),

    # Password management
    path("change-password/", views.change_password, name="change_password"),
    path("forgot-password/", views.forgot_password, name="forgot_password"),
    path("reset-password/<str:uidb64>/<str:token>/", views.reset_password, name="reset_password"),
]
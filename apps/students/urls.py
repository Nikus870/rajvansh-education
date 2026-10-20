from django.urls import path

from . import views

app_name = "students"

urlpatterns = [
    path("<int:pk>/photo/", views.student_profile_image, name="profile_image"),
    path("", views.student_list, name="list"),
    path("register/", views.register_student, name="register"),
    path("export/csv/", views.student_export_csv, name="export_csv"),
    path("<int:pk>/", views.student_detail, name="detail"),
    path("<int:pk>/edit/", views.student_edit, name="edit"),
]

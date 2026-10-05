from django.urls import path
from . import views

app_name = "franchise"

urlpatterns = [
    path("", views.landing, name="landing"),
    path("register/", views.register, name="register"),
    path("login/", views.franchise_login, name="login"),
    path("activate/<str:token>/", views.activate_account, name="activate"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("logout/", views.franchise_logout, name="logout"),
]
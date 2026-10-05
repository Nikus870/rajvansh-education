from django.urls import path
from . import views
app_name="universities"
urlpatterns=[path("",views.university_list,name="list"),path("<slug:slug>/",views.university_detail,name="detail")]

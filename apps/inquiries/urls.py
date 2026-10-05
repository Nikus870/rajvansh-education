from django.urls import path
from . import views
app_name="inquiries"
urlpatterns=[path("",views.inquiry,name="inquiry"),path("consultation/",views.consultation,name="consultation"),path("success/",views.success,name="success")]

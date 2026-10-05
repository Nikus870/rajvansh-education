from django.urls import path
from . import views
app_name="content"
urlpatterns=[path("faq/",views.faq,name="faq"),path("testimonials/",views.testimonials,name="testimonials")]

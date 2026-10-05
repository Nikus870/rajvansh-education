from django.urls import path
from . import views
app_name="core"
urlpatterns=[path("",views.home,name="home"),path("about/",views.about,name="about"),path("contact/",views.contact,name="contact"),path("faq/",views.faq,name="faq"),path("testimonials/",views.testimonials,name="testimonials"),path("privacy-policy/",views.legal_page,{"slug":"privacy-policy"},name="privacy"),path("terms-and-conditions/",views.legal_page,{"slug":"terms-and-conditions"},name="terms"),path("robots.txt",views.robots,name="robots")]

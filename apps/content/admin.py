from django.contrib import admin
from .models import FAQ,Testimonial,SitePage
@admin.register(FAQ)
class FAQAdmin(admin.ModelAdmin): list_display=("question","category","display_order","active"); list_filter=("active","category"); search_fields=("question","answer")
@admin.register(Testimonial)
class TestimonialAdmin(admin.ModelAdmin): list_display=("student_name","course","university","active"); list_filter=("active",); search_fields=("student_name","content")
@admin.register(SitePage)
class SitePageAdmin(admin.ModelAdmin): list_display=("title","slug","active","updated_at"); search_fields=("title","content"); prepopulated_fields={"slug":("title",)}

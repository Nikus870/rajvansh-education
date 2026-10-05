from django.contrib import admin
from .models import Inquiry,CareerConsultation,ContactMessage
@admin.register(Inquiry)
class InquiryAdmin(admin.ModelAdmin): list_display=("name","mobile","course","university","status","created_at"); list_filter=("status","study_mode"); search_fields=("name","mobile","email","message"); autocomplete_fields=("course","university")
@admin.register(CareerConsultation)
class CareerConsultationAdmin(admin.ModelAdmin): list_display=("name","mobile","area_of_interest","status","created_at"); list_filter=("status","preferred_study_mode"); search_fields=("name","mobile","email","career_goal"); autocomplete_fields=("preferred_course",)
@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin): list_display=("name","mobile","email","created_at"); search_fields=("name","mobile","email","message")

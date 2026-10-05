from django.contrib import admin
from .models import University
@admin.register(University)
class UniversityAdmin(admin.ModelAdmin): list_display=("name","location","active","updated_at"); list_filter=("active",); search_fields=("name","location","description"); prepopulated_fields={"slug":("name",)}

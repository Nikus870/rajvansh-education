from django.contrib import admin
from .models import WebsiteSettings,AdmissionSettings,Statistic,StudyModeInfo
@admin.register(WebsiteSettings)
class WebsiteSettingsAdmin(admin.ModelAdmin): list_display=("website_name","phone","email","updated_at")
@admin.register(AdmissionSettings)
class AdmissionSettingsAdmin(admin.ModelAdmin): list_display=("is_open","deadline","updated_at")
@admin.register(Statistic)
class StatisticAdmin(admin.ModelAdmin): list_display=("value","label","display_order","active"); list_filter=("active",); ordering=("display_order",)

@admin.register(StudyModeInfo)
class StudyModeInfoAdmin(admin.ModelAdmin): list_display=("mode","title","display_order","active"); list_filter=("active",); ordering=("display_order",)

from django.contrib import admin
from .models import Course,CourseCategory
@admin.register(CourseCategory)
class CourseCategoryAdmin(admin.ModelAdmin): list_display=("name","active"); list_filter=("active",); search_fields=("name",); prepopulated_fields={"slug":("name",)}
@admin.register(Course)
class CourseAdmin(admin.ModelAdmin): list_display=("name","category","university","admission_status","featured","active"); list_filter=("active","featured","admission_status","regular_available","odl_available"); search_fields=("name","short_description","full_description"); prepopulated_fields={"slug":("name",)}; autocomplete_fields=("category","university")

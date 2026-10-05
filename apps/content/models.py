from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from pathlib import Path
class FAQ(models.Model):
 question=models.CharField(max_length=240); answer=models.TextField(); category=models.CharField(max_length=100,blank=True); display_order=models.PositiveIntegerField(default=0); active=models.BooleanField(default=True); created_at=models.DateTimeField(auto_now_add=True); updated_at=models.DateTimeField(auto_now=True)
 class Meta: ordering=["display_order","id"]
 def __str__(self): return self.question
class Testimonial(models.Model):
 student_name=models.CharField(max_length=120); course=models.CharField(max_length=180,blank=True); university=models.CharField(max_length=180,blank=True); photo=models.ImageField(upload_to="testimonials/",blank=True,null=True); content=models.TextField(); active=models.BooleanField(default=False); created_at=models.DateTimeField(auto_now_add=True); updated_at=models.DateTimeField(auto_now=True)
 def __str__(self): return self.student_name
 def clean(self):
  if self.photo and getattr(self.photo,"size",0)>settings.MAX_UPLOAD_SIZE_MB*1024*1024: raise ValidationError("Testimonial photo exceeds the configured size limit.")
  if self.photo and Path(self.photo.name).suffix.lower() not in {".jpg",".jpeg",".png",".webp"}: raise ValidationError("Testimonial photo must be JPG, JPEG, PNG or WebP.")
class SitePage(models.Model):
 title=models.CharField(max_length=180); slug=models.SlugField(unique=True); content=models.TextField(); meta_description=models.CharField(max_length=160,blank=True); active=models.BooleanField(default=True); updated_at=models.DateTimeField(auto_now=True)
 def __str__(self): return self.title

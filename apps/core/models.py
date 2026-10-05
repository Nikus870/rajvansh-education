from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from pathlib import Path
class WebsiteSettings(models.Model):
 website_name=models.CharField(max_length=160,default="Rajvans Group of Educations"); logo=models.ImageField(upload_to="site/",blank=True,null=True); phone=models.CharField(max_length=40,default="YOUR_PHONE",blank=True); email=models.EmailField(default="YOUR_EMAIL@example.invalid",blank=True); address=models.TextField(default="YOUR_ADDRESS",blank=True); maps_url=models.URLField(blank=True); maps_embed_url=models.URLField(blank=True); working_hours=models.CharField(max_length=180,default="YOUR_WORKING_HOURS",blank=True); facebook_url=models.URLField(blank=True); instagram_url=models.URLField(blank=True); youtube_url=models.URLField(blank=True); linkedin_url=models.URLField(blank=True); footer_text=models.TextField(default="Flexible education options with career guidance and student support.",blank=True); hero_title=models.CharField(max_length=180,default="घर बैठे करें डिग्री पूरी"); hero_subtitle=models.TextField(default="Explore flexible education options, course pathways and student support from one place."); updated_at=models.DateTimeField(auto_now=True)
 def save(self,*a,**k): self.pk=1; super().save(*a,**k)
 @classmethod
 def get_solo(cls): return cls.objects.get_or_create(pk=1)[0]
 def __str__(self): return self.website_name
 def clean(self):
  if self.logo and getattr(self.logo,"size",0)>settings.MAX_UPLOAD_SIZE_MB*1024*1024: raise ValidationError("Logo exceeds the configured size limit.")
  if self.logo and Path(self.logo.name).suffix.lower() not in {".jpg",".jpeg",".png",".webp"}: raise ValidationError("Logo must be JPG, JPEG, PNG or WebP.")
class AdmissionSettings(models.Model):
 is_open=models.BooleanField(default=True); admission_message=models.CharField(max_length=220,default="Admissions are currently open. Contact us for current course availability."); deadline=models.DateField(blank=True,null=True); updated_at=models.DateTimeField(auto_now=True)
 def save(self,*a,**k): self.pk=1; super().save(*a,**k)
 @classmethod
 def get_solo(cls): return cls.objects.get_or_create(pk=1)[0]
 def __str__(self): return "Admissions Open" if self.is_open else "Admissions Closed"
class Statistic(models.Model):
 label=models.CharField(max_length=100); value=models.CharField(max_length=40); icon=models.CharField(max_length=60,default="bi-bar-chart"); display_order=models.PositiveIntegerField(default=0); active=models.BooleanField(default=True)
 class Meta: ordering=["display_order","id"]
 def __str__(self): return f"{self.value} {self.label}"

class StudyModeInfo(models.Model):
 mode=models.CharField(max_length=80)
 title=models.CharField(max_length=140)
 icon=models.CharField(max_length=60,default="bi-mortarboard")
 description=models.TextField()
 display_order=models.PositiveIntegerField(default=0)
 active=models.BooleanField(default=True)
 class Meta: ordering=["display_order","id"]
 def __str__(self): return self.title

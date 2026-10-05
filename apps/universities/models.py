# pyright: reportMissingModuleSource=false
from django.db import models  # type: ignore
from django.conf import settings  # type: ignore
from django.core.exceptions import ValidationError  # type: ignore
from pathlib import Path
from django.urls import reverse  # type: ignore
class University(models.Model):
 name=models.CharField(max_length=180); slug=models.SlugField(unique=True); logo=models.ImageField(upload_to="universities/logos/",blank=True,null=True); cover_image=models.ImageField(upload_to="universities/covers/",blank=True,null=True); description=models.TextField(); website=models.URLField(blank=True); location=models.CharField(max_length=180,blank=True); additional_information=models.TextField(blank=True); active=models.BooleanField(default=True); created_at=models.DateTimeField(auto_now_add=True); updated_at=models.DateTimeField(auto_now=True)
 class Meta: ordering=["name"]
 def __str__(self): return self.name
 def get_absolute_url(self): return reverse("universities:detail",kwargs={"slug":self.slug})
 def clean(self):
  for f in (self.logo,self.cover_image):
   if f and getattr(f,"size",0)>settings.MAX_UPLOAD_SIZE_MB*1024*1024: raise ValidationError("Uploaded image exceeds the configured size limit.")
   if f and Path(f.name).suffix.lower() not in {".jpg",".jpeg",".png",".webp"}: raise ValidationError("University images must be JPG, JPEG, PNG or WebP.")

from django.db import models
from django.core.validators import MinValueValidator
from django.core.exceptions import ValidationError
from django.conf import settings
from pathlib import Path
from django.urls import reverse
from apps.universities.models import University
class CourseCategory(models.Model):
 name=models.CharField(max_length=120); slug=models.SlugField(unique=True); description=models.TextField(blank=True); active=models.BooleanField(default=True); created_at=models.DateTimeField(auto_now_add=True); updated_at=models.DateTimeField(auto_now=True)
 class Meta: ordering=["name"]
 def __str__(self): return self.name
class Course(models.Model):
 STATUS=[("open","Admission Open"),("closed","Admissions Closed"),("enquiry","Enquire for Current Status")]
 name=models.CharField(max_length=180); slug=models.SlugField(unique=True); category=models.ForeignKey(CourseCategory,on_delete=models.PROTECT,related_name="courses"); university=models.ForeignKey(University,on_delete=models.PROTECT,related_name="courses",blank=True,null=True); image=models.ImageField(upload_to="courses/",blank=True,null=True); short_description=models.CharField(max_length=300); full_description=models.TextField(); eligibility=models.TextField(blank=True); duration=models.CharField(max_length=80,blank=True); fee=models.DecimalField(max_digits=10,decimal_places=2,blank=True,null=True,validators=[MinValueValidator(0)]); regular_available=models.BooleanField(default=False); odl_available=models.BooleanField(default=True); admission_status=models.CharField(max_length=20,choices=STATUS,default="enquiry"); featured=models.BooleanField(default=False); brochure=models.FileField(upload_to="brochures/",blank=True,null=True); active=models.BooleanField(default=True); created_at=models.DateTimeField(auto_now_add=True); updated_at=models.DateTimeField(auto_now=True)
 class Meta: ordering=["-featured","name"]
 def __str__(self): return self.name
 def get_absolute_url(self): return reverse("courses:detail",kwargs={"slug":self.slug})
 @property
 def study_mode_label(self): return "Regular + ODL" if self.regular_available and self.odl_available else "Regular" if self.regular_available else "ODL / Distance"
 def clean(self):
  for f in (self.image,self.brochure):
   if f and getattr(f,"size",0)>settings.MAX_UPLOAD_SIZE_MB*1024*1024: raise ValidationError("Uploaded file exceeds the configured size limit.")
  if self.image and Path(self.image.name).suffix.lower() not in {".jpg",".jpeg",".png",".webp"}: raise ValidationError("Course image must be JPG, JPEG, PNG or WebP.")
  if self.brochure and Path(self.brochure.name).suffix.lower()!=".pdf": raise ValidationError("Brochure must be a PDF.")

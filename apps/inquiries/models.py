from django.db import models
class Inquiry(models.Model):
 STATUS=[("new","New"),("contacted","Contacted"),("progress","In Progress"),("converted","Converted"),("closed","Closed")]; MODES=[("regular","Regular"),("odl","ODL / Distance"),("both","Either / Both"),("unsure","Not sure")]
 name=models.CharField(max_length=120); mobile=models.CharField(max_length=30); email=models.EmailField(blank=True); course=models.ForeignKey("courses.Course",on_delete=models.SET_NULL,null=True,blank=True,related_name="inquiries"); university=models.ForeignKey("universities.University",on_delete=models.SET_NULL,null=True,blank=True,related_name="inquiries"); study_mode=models.CharField(max_length=20,choices=MODES,default="unsure"); message=models.TextField(); status=models.CharField(max_length=20,choices=STATUS,default="new"); created_at=models.DateTimeField(auto_now_add=True); updated_at=models.DateTimeField(auto_now=True)
 class Meta: ordering=["-created_at"]
 def __str__(self): return f"{self.name} - {self.mobile}"
class CareerConsultation(models.Model):
 name=models.CharField(max_length=120); mobile=models.CharField(max_length=30); email=models.EmailField(blank=True); highest_qualification=models.CharField(max_length=180); passing_year=models.PositiveIntegerField(blank=True,null=True); area_of_interest=models.CharField(max_length=180); career_goal=models.CharField(max_length=300); preferred_study_mode=models.CharField(max_length=20,choices=Inquiry.MODES[:1]+[("odl","ODL / Distance"),("unsure","Not sure")],default="unsure"); preferred_course=models.ForeignKey("courses.Course",on_delete=models.SET_NULL,null=True,blank=True,related_name="consultations"); message=models.TextField(blank=True); created_at=models.DateTimeField(auto_now_add=True); status=models.CharField(max_length=20,choices=Inquiry.STATUS,default="new")
 def __str__(self): return self.name
class ContactMessage(models.Model):
 name=models.CharField(max_length=120); mobile=models.CharField(max_length=30); email=models.EmailField(blank=True); message=models.TextField(); created_at=models.DateTimeField(auto_now_add=True)

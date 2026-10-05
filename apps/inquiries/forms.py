from django import forms
from .models import Inquiry,CareerConsultation,ContactMessage
from apps.courses.models import Course
from apps.universities.models import University
class Styled(forms.ModelForm):
 def __init__(self,*a,**k):
  super().__init__(*a,**k)
  for f in self.fields.values(): f.widget.attrs["class"]=(f.widget.attrs.get("class","")+" form-control").strip()
class InquiryForm(Styled):
 class Meta: model=Inquiry; fields=["name","mobile","email","course","university","study_mode","message"]; widgets={"message":forms.Textarea(attrs={"rows":5})}
 def __init__(self,*a,**k): super().__init__(*a,**k); self.fields["course"].queryset=Course.objects.filter(active=True); self.fields["university"].queryset=University.objects.filter(active=True)
class ConsultationForm(Styled):
 class Meta: model=CareerConsultation; fields=["name","mobile","email","highest_qualification","passing_year","area_of_interest","career_goal","preferred_study_mode","preferred_course","message"]; widgets={"message":forms.Textarea(attrs={"rows":4})}
 def __init__(self,*a,**k): super().__init__(*a,**k); self.fields["preferred_course"].queryset=Course.objects.filter(active=True)
class ContactForm(Styled):
 class Meta: model=ContactMessage; fields=["name","mobile","email","message"]; widgets={"message":forms.Textarea(attrs={"rows":5})}

from django import forms
from .models import CourseCategory
from apps.universities.models import University
class CourseFilterForm(forms.Form):
 q=forms.CharField(required=False); category=forms.ModelChoiceField(queryset=CourseCategory.objects.none(),required=False); university=forms.ModelChoiceField(queryset=University.objects.none(),required=False); study_mode=forms.ChoiceField(choices=[("","Any study mode"),("regular","Regular"),("odl","ODL / Distance")],required=False); min_fee=forms.DecimalField(required=False,min_value=0); max_fee=forms.DecimalField(required=False,min_value=0); duration=forms.CharField(required=False)
 def __init__(self,*a,**k):
  super().__init__(*a,**k); self.fields["category"].queryset=CourseCategory.objects.filter(active=True); self.fields["university"].queryset=University.objects.filter(active=True)

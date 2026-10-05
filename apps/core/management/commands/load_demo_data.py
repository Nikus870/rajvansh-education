from django.core.management.base import BaseCommand
from apps.core.models import WebsiteSettings,AdmissionSettings,Statistic
from apps.content.models import FAQ,SitePage
from apps.courses.models import CourseCategory,Course
class Command(BaseCommand):
 def handle(self,*a,**k):
  WebsiteSettings.get_solo(); AdmissionSettings.get_solo()
  for i,(l,v,ic) in enumerate([("Years of service","15+","bi-award"),("Students supported","50,000+","bi-people"),("Associated universities","100+","bi-building"),("Courses","250+","bi-journal-bookmark")]): Statistic.objects.update_or_create(label=l,defaults={"value":v,"icon":ic,"display_order":i,"active":True})
  c,_=CourseCategory.objects.get_or_create(slug="sample-category",defaults={"name":"SAMPLE DATA — Category"}); Course.objects.get_or_create(slug="sample-course",defaults={"name":"SAMPLE DATA — Course","category":c,"short_description":"Demo only.","full_description":"SAMPLE DATA — Replace before production.","duration":"Demo","regular_available":True,"odl_available":True,"active":True,"featured":True})
  FAQ.objects.get_or_create(question="SAMPLE DATA — How do I enquire?",defaults={"answer":"Replace with approved FAQ.","active":True})
  for s,t in [("about","About Rajvans — SAMPLE DATA"),("privacy-policy","Privacy Policy — SAMPLE DATA"),("terms-and-conditions","Terms & Conditions — SAMPLE DATA")]: SitePage.objects.get_or_create(slug=s,defaults={"title":t,"content":"SAMPLE DATA — Replace with client-approved content."})
  self.stdout.write(self.style.SUCCESS("Demo data loaded; replace SAMPLE DATA before production."))

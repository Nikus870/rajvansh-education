from django.contrib.sitemaps import Sitemap
from .models import University
class UniversitySitemap(Sitemap):
 def items(self): return University.objects.filter(active=True)

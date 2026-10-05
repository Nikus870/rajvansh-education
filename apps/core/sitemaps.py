from django.contrib.sitemaps import Sitemap
from django.urls import reverse
class StaticViewSitemap(Sitemap):
 def items(self): return ["core:home","core:about","core:contact","core:faq","core:testimonials","courses:list","universities:list","inquiries:consultation","franchise:landing"]
 def location(self,item): return reverse(item)

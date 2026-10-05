from django.shortcuts import render
from .models import FAQ,Testimonial
def faq(request): return render(request,"content/faq.html",{"faqs":FAQ.objects.filter(active=True)})
def testimonials(request): return render(request,"content/testimonials.html",{"testimonials":Testimonial.objects.filter(active=True)})

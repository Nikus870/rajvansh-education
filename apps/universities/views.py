from django.shortcuts import get_object_or_404,render
from .models import University
def university_list(request): return render(request,"universities/list.html",{"universities":University.objects.filter(active=True)})
def university_detail(request,slug):
 u=get_object_or_404(University,slug=slug,active=True); return render(request,"universities/detail.html",{"university":u,"courses":u.courses.filter(active=True).select_related("category")})

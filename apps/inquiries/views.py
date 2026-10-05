from django.contrib import messages
from django.shortcuts import redirect, render
from .forms import InquiryForm, ConsultationForm
from apps.courses.models import Course


def inquiry(request):
    initial = {}
    if request.method == "GET":
        course_param = request.GET.get("course")
        if course_param:
            course = None
            if str(course_param).isdigit():
                course = Course.objects.filter(pk=int(course_param), active=True).first()
            if not course:
                course = Course.objects.filter(slug=course_param, active=True).first()
            if course:
                initial["course"] = course
                if course.university:
                    initial["university"] = course.university

    form = InquiryForm(request.POST or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Thank you. Your enquiry has been submitted.")
        return redirect("inquiries:success")
    return render(request, "inquiries/inquiry.html", {"form": form})


def consultation(request):
    form = ConsultationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Your consultation request has been received.")
        return redirect("inquiries:success")
    return render(request, "inquiries/consultation.html", {"form": form})


def success(request):
    return render(request, "inquiries/success.html")

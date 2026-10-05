from types import SimpleNamespace

from django.contrib import messages
from django.http import Http404
from django.shortcuts import redirect, render

from .models import Statistic, StudyModeInfo

from apps.courses.models import Course
from apps.universities.models import University
from apps.content.models import SitePage, Testimonial, FAQ
from apps.content.views import faq, testimonials
from apps.inquiries.forms import ContactForm


FALLBACK_PAGES = {
    "about": {
        "title": "About Rajvans Group of Educations",
        "meta_description": (
            "Learn about Rajvans Group of Educations, our courses, "
            "distance education pathways, and academic counseling."
        ),
        "content": (
            "Welcome to Rajvans Group of Educations.\n\n"
            "We are committed to providing accessible and high-quality "
            "education guidance to learners across India. Our dedicated "
            "academic counselors assist students in choosing the right "
            "courses, universities, and study modes including Regular, "
            "Distance (ODL), and Online degree programs.\n\n"
            "With partnerships across accredited universities, we empower "
            "students to achieve their academic and career goals with confidence."
        ),
    },

    "privacy-policy": {
        "title": "Privacy Policy",
        "meta_description": (
            "Privacy policy and data protection practices at "
            "Rajvans Group of Educations."
        ),
        "content": (
            "Rajvans Group of Educations respects your privacy and is "
            "committed to protecting your personal information.\n\n"
            "1. Information Collection: We collect information you provide "
            "directly through our enquiry, consultation, and franchise "
            "registration forms.\n\n"
            "2. Use of Information: The information is used solely to respond "
            "to your academic enquiries, process franchise applications, "
            "and guide your educational journey.\n\n"
            "3. Data Protection: We implement reasonable security practices "
            "to safeguard personal data and do not sell or rent user details "
            "to third parties.\n\n"
            "4. Contact Us: For questions or requests regarding your personal "
            "information, please get in touch via our contact page."
        ),
    },

    "terms-and-conditions": {
        "title": "Terms and Conditions",
        "meta_description": (
            "Terms of use and service conditions for Rajvans Group "
            "of Educations."
        ),
        "content": (
            "Welcome to Rajvans Group of Educations. By accessing and using "
            "our website and services, you agree to comply with the following terms:\n\n"
            "1. Educational Guidance: Information on courses, eligibility, "
            "fees, and university affiliations is for advisory purposes and "
            "subject to university verification.\n\n"
            "2. User Obligations: You agree to submit truthful, accurate "
            "details when submitting inquiries or registration applications.\n\n"
            "3. Intellectual Property: All materials, logos, and content on "
            "this site are property of Rajvans Group of Educations or their "
            "respective owners.\n\n"
            "4. Amendments: Terms and conditions may be updated periodically "
            "to align with university policies and regulatory changes."
        ),
    },
}


def home(request):
    return render(
        request,
        "core/home.html",
        {
            "featured_courses": (
                Course.objects
                .filter(active=True, featured=True)
                .select_related("category", "university")[:6]
            ),

            "universities": (
                University.objects
                .filter(active=True)[:6]
            ),

            "statistics": (
                Statistic.objects
                .filter(active=True)[:4]
            ),

            "study_modes": (
                StudyModeInfo.objects
                .filter(active=True)
            ),

            "testimonials": (
                Testimonial.objects
                .filter(active=True)[:6]
            ),

            # FAQ section on homepage
            "faqs": (
                FAQ.objects
                .filter(active=True)
                .order_by("display_order", "id")
            ),
        },
    )


def faq(request):
    from apps.content.models import FAQ

    faqs = (
        FAQ.objects
        .filter(active=True)
        .order_by("display_order", "id")
    )

    return render(
        request,
        "content/faq.html",
        {"faqs": faqs},
    )


def testimonials(request):
    testimonials_list = (
        Testimonial.objects
        .filter(active=True)
        .order_by("-created_at")
    )

    return render(
        request,
        "content/testimonials.html",
        {"testimonials": testimonials_list},
    )

def about(request):
    page = SitePage.objects.filter(
        slug="about",
        active=True,
    ).first()

    if not page:
        page = SimpleNamespace(
            **FALLBACK_PAGES["about"]
        )

    return render(
        request,
        "core/about.html",
        {"page": page},
    )


def contact(request):
    form = ContactForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(
            request,
            "Your message has been received.",
        )
        return redirect("core:contact")

    return render(
        request,
        "core/contact.html",
        {"form": form},
    )


def legal_page(request, slug):
    page = SitePage.objects.filter(
        slug=slug,
        active=True,
    ).first()

    if not page:
        if slug in FALLBACK_PAGES:
            page = SimpleNamespace(
                **FALLBACK_PAGES[slug]
            )
        else:
            raise Http404("Page not found.")

    return render(
        request,
        "content/site_page.html",
        {"page": page},
    )


def robots(request):
    return render(
        request,
        "core/robots.txt",
        content_type="text/plain",
    )
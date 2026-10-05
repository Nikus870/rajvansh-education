from django.contrib.auth.models import User
from django.test import TestCase

from apps.courses.models import CourseCategory, Course
from apps.franchise.models import FranchiseApplication
from apps.inquiries.models import Inquiry, CareerConsultation
from apps.universities.models import University


class SmokeTests(TestCase):

    def setUp(self):
        university = University.objects.create(
            name="Test University",
            slug="test-university",
            description="Test",
        )

        category = CourseCategory.objects.create(
            name="Test Category",
            slug="test-category",
        )

        self.course = Course.objects.create(
            name="Test Course",
            slug="test-course",
            category=category,
            university=university,
            short_description="Test",
            full_description="Test",
            duration="2 years",
            fee=10000,
            regular_available=True,
            odl_available=True,
            active=True,
        )

    def test_public(self):
        urls = [
            "/",
            "/courses/",
            "/courses/test-course/",
            "/universities/",
            "/universities/test-university/",
            "/inquiry/",
            "/inquiry/consultation/",
            "/inquiry/success/",
            "/franchise/",
            "/franchise/register/",
            "/franchise/login/",
            "/contact/",
            "/faq/",
            "/testimonials/",
            "/about/",
            "/privacy-policy/",
            "/terms-and-conditions/",
            "/robots.txt",
        ]

        for url in urls:
            response = self.client.get(url)

            self.assertEqual(
                response.status_code,
                200,
                url,
            )

    def test_inquiry(self):
        response = self.client.post(
            "/inquiry/",
            {
                "name": "Test",
                "mobile": "9999999999",
                "email": "a@b.com",
                "course": self.course.pk,
                "study_mode": "regular",
                "message": "Hi",
            },
        )

        self.assertRedirects(
            response,
            "/inquiry/success/",
        )

        self.assertEqual(
            Inquiry.objects.count(),
            1,
        )

    def test_consultation(self):
        response = self.client.post(
            "/inquiry/consultation/",
            {
                "name": "Test",
                "mobile": "9999999999",
                "email": "a@b.com",
                "highest_qualification": "BSc",
                "passing_year": 2025,
                "area_of_interest": "Tech",
                "career_goal": "AI",
                "preferred_study_mode": "odl",
                "preferred_course": self.course.pk,
                "message": "Guide",
            },
        )

        self.assertRedirects(
            response,
            "/inquiry/success/",
        )

        self.assertEqual(
            CareerConsultation.objects.count(),
            1,
        )

    def test_franchise_registration_creates_pending_application(self):
        """
        Registration is now an interest/application submission.

        It must NOT immediately create a user account or redirect
        the visitor to the franchise dashboard.
        """

        response = self.client.post(
            "/franchise/register/",
            {
                "name": "Partner",
                "mobile": "9999999999",
                "email": "partner@x.com",
                "city": "Kota",
                "state": "Rajasthan",
            },
        )

        self.assertRedirects(
            response,
            "/franchise/",
        )

        self.assertEqual(
            FranchiseApplication.objects.count(),
            1,
        )

        application = FranchiseApplication.objects.get()

        self.assertEqual(
            application.email,
            "partner@x.com",
        )

        self.assertEqual(
            application.status,
            "pending",
        )

        # No account is created before admin approval
        self.assertFalse(
            User.objects.filter(
                email__iexact="partner@x.com"
            ).exists()
        )

        # Visitor is not automatically authenticated
        self.assertFalse(
            response.wsgi_request.user.is_authenticated
        )

    def test_staff_block(self):
        """
        Staff/superuser accounts must not use the franchise login.
        """

        User.objects.create_superuser(
            username="admin",
            email="admin@x.com",
            password="StrongPass123!",
        )

        response = self.client.post(
            "/franchise/login/",
            {
                "email": "admin@x.com",
                "password": "StrongPass123!",
            },
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        self.assertContains(
            response,
            "Use the Django Admin login",
        )
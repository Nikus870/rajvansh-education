from django.contrib.auth.models import User
from django.http import Http404
from django.test import RequestFactory, TestCase

from apps.content.models import SitePage
from apps.courses.models import Course, CourseCategory
from apps.franchise.models import FranchiseApplication, FranchiseProfile
from apps.universities.models import University


class KnownIssuesTests(TestCase):

    def setUp(self):
        self.university = University.objects.create(
            name="Sample University",
            slug="sample-university",
            description="University description",
            active=True,
        )

        self.category = CourseCategory.objects.create(
            name="Management",
            slug="management",
            active=True,
        )

        self.course = Course.objects.create(
            name="MBA in Finance",
            slug="mba-in-finance",
            category=self.category,
            university=self.university,
            short_description="Top MBA course",
            full_description="Full MBA details",
            duration="2 Years",
            fee=50000,
            regular_available=True,
            odl_available=True,
            active=True,
        )

    def test_course_enquiry_param_selection(self):
        """Ensure ?course=<id> selects the course in the enquiry form."""

        # Query by ID
        response = self.client.get(
            f"/inquiry/?course={self.course.pk}"
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            f'value="{self.course.pk}" selected',
        )

        # Query by slug
        response_slug = self.client.get(
            f"/inquiry/?course={self.course.slug}"
        )

        self.assertEqual(response_slug.status_code, 200)
        self.assertContains(
            response_slug,
            f'value="{self.course.pk}" selected',
        )

        # Invalid value should not crash
        response_invalid = self.client.get(
            "/inquiry/?course=invalid-slug-9999"
        )

        self.assertEqual(response_invalid.status_code, 200)

    def test_site_pages_missing_fallback(self):
        """
        Site pages must correctly handle missing records
        with fallback content.
        """

        SitePage.objects.all().delete()

        # About
        res_about = self.client.get("/about/")

        self.assertEqual(res_about.status_code, 200)
        self.assertContains(
            res_about,
            "Welcome to Rajvans Group of Educations.",
        )
        self.assertNotContains(
            res_about,
            "Create the About page in Admin.",
        )

        # Privacy Policy
        res_privacy = self.client.get("/privacy-policy/")

        self.assertEqual(res_privacy.status_code, 200)
        self.assertContains(
            res_privacy,
            "Privacy Policy",
        )
        self.assertContains(
            res_privacy,
            "Data Protection",
        )

        # Terms
        res_terms = self.client.get("/terms-and-conditions/")

        self.assertEqual(res_terms.status_code, 200)
        self.assertContains(
            res_terms,
            "Terms and Conditions",
        )
        self.assertContains(
            res_terms,
            "Educational Guidance",
        )

        # Unknown legal slug
        from apps.core.views import legal_page

        factory = RequestFactory()
        request = factory.get("/unknown-slug/")

        with self.assertRaises(Http404):
            legal_page(
                request,
                "non-existent-legal-page",
            )

    def test_franchise_registration_creates_application_only(self):
        """
        Franchise registration should create an application only.

        No Django user or FranchiseProfile should be created until
        an administrator approves the application.
        """

        response = self.client.post(
            "/franchise/register/",
            {
                "name": "Partner One",
                "mobile": "9876543210",
                "email": "partner1@example.com",
                "city": "Jaipur",
                "state": "Rajasthan",
                "business_name": "Partner Business",
                "address": "Jaipur",
                "experience": "5 years",
                "message": "Interested in franchise.",
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
            "partner1@example.com",
        )

        self.assertEqual(
            application.status,
            "pending",
        )

        # No account should be created during registration
        self.assertFalse(
            User.objects.filter(
                email__iexact="partner1@example.com"
            ).exists()
        )

        self.assertFalse(
            FranchiseProfile.objects.exists()
        )

    def test_franchise_registration_duplicate_pending_email_case_insensitive(self):
        """
        A second pending/review/contacted application using the same
        email should be rejected case-insensitively.
        """

        FranchiseApplication.objects.create(
            name="Existing Partner",
            mobile="9876543210",
            email="partner1@example.com",
            city="Jaipur",
            state="Rajasthan",
            status="pending",
        )

        response = self.client.post(
            "/franchise/register/",
            {
                "name": "Partner Duplicate",
                "mobile": "9876543211",
                "email": "PARTNER1@EXAMPLE.COM",
                "city": "Jaipur",
                "state": "Rajasthan",
            },
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        self.assertContains(
            response,
            "A franchise application with this email is already under review.",
        )

        self.assertEqual(
            FranchiseApplication.objects.count(),
            1,
        )

    def test_franchise_registration_existing_user_email_case_insensitive(self):
        """
        Registration must reject an email already used by an existing
        Django user, even if the casing is different.
        """

        User.objects.create_user(
            username="staff_member",
            email="staff@example.com",
            password="Password123!",
        )

        response = self.client.post(
            "/franchise/register/",
            {
                "name": "Partner Staff Email",
                "mobile": "9876543212",
                "email": "STAFF@EXAMPLE.COM",
                "city": "Jaipur",
                "state": "Rajasthan",
            },
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        self.assertContains(
            response,
            "An account with this email already exists.",
        )

        self.assertEqual(
            FranchiseApplication.objects.count(),
            0,
        )

    def test_franchise_login_and_logout_flow(self):
        """
        Approved/active franchise users can log in using their email.

        Staff users must not use the franchise login.
        """

        user = User.objects.create_user(
            username="partner@test.com",
            email="partner@test.com",
            password="PartnerPass123!",
            first_name="Franchise",
            is_active=True,
        )

        FranchiseProfile.objects.create(
            user=user,
            mobile="9876543210",
            city="Kota",
            state="Rajasthan",
            business_name="Kota Learning Hub",
        )

        FranchiseApplication.objects.create(
            user=user,
            name="Franchise Partner",
            mobile="9876543210",
            email="partner@test.com",
            city="Kota",
            state="Rajasthan",
            business_name="Kota Learning Hub",
            status="approved",
        )

        # Invalid credentials
        res_fail = self.client.post(
            "/franchise/login/",
            {
                "email": "partner@test.com",
                "password": "WrongPassword",
            },
        )

        self.assertEqual(
            res_fail.status_code,
            200,
        )

        self.assertContains(
            res_fail,
            "Invalid email or password.",
        )

        # Successful mixed-case email login
        res_ok = self.client.post(
            "/franchise/login/",
            {
                "email": "PARTNER@TEST.COM",
                "password": "PartnerPass123!",
            },
        )

        self.assertRedirects(
            res_ok,
            "/franchise/dashboard/",
        )

        # Dashboard
        res_dash = self.client.get(
            "/franchise/dashboard/"
        )

        self.assertEqual(
            res_dash.status_code,
            200,
        )

        self.assertContains(
            res_dash,
            "Welcome, Franchise",
        )

        self.assertContains(
            res_dash,
            "Kota Learning Hub",
        )

        self.assertContains(
            res_dash,
            'action="/franchise/logout/"',
        )

        # Safe POST logout
        res_logout = self.client.post(
            "/franchise/logout/"
        )

        self.assertRedirects(
            res_logout,
            "/",
        )

        # Dashboard after logout
        res_dash_after = self.client.get(
            "/franchise/dashboard/"
        )

        self.assertEqual(
            res_dash_after.status_code,
            302,
        )

        self.assertTrue(
            "/franchise/login/" in res_dash_after.url
            or "/login/" in res_dash_after.url
        )

    def test_course_list_shows_active_admin_courses_without_filter_form(self):
        """
        Explore Courses should show active courses managed through Admin.

        The old filter/search form is intentionally not part of this page.
        """

        course_two = Course.objects.create(
            name="BBA in Marketing",
            slug="bba-in-marketing",
            category=self.category,
            university=self.university,
            short_description="Marketing course",
            full_description="Advanced marketing program",
            duration="3 Years",
            fee=65000,
            regular_available=True,
            odl_available=False,
            active=True,
        )

        response = self.client.get(
            "/courses/"
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        # Both active admin-created courses are visible
        self.assertContains(
            response,
            self.course.name,
        )

        self.assertContains(
            response,
            course_two.name,
        )

        # Old filter form/context should not exist
        self.assertNotIn(
            "form",
            response.context,
        )

        self.assertNotContains(
            response,
            'name="q"',
        )

    def test_course_list_excludes_inactive_courses(self):
        """
        Inactive courses should not appear on the public Courses page.
        """

        inactive_course = Course.objects.create(
            name="Inactive Course",
            slug="inactive-course",
            category=self.category,
            university=self.university,
            short_description="Inactive course",
            full_description="Inactive course details",
            duration="2 Years",
            fee=40000,
            regular_available=True,
            odl_available=True,
            active=False,
        )

        response = self.client.get(
            "/courses/"
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        self.assertContains(
            response,
            self.course.name,
        )

        self.assertNotContains(
            response,
            inactive_course.name,
        )

    def test_duplicate_routing_both_work(self):
        """
        FAQ and Testimonial routes in both core and content should work.
        """

        for path in [
            "/faq/",
            "/testimonials/",
            "/content/faq/",
            "/content/testimonials/",
        ]:
            response = self.client.get(path)

            self.assertEqual(
                response.status_code,
                200,
                f"Route {path} failed with {response.status_code}",
            )
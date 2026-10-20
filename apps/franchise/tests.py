from unittest.mock import patch
from datetime import date, datetime, time
from io import BytesIO

from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from django.core.files.storage import InMemoryStorage
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from PIL import Image
from pypdf import PdfReader

from apps.courses.models import Course, CourseCategory
from apps.franchise.analytics import get_student_growth_analytics
from apps.franchise.certificate_service import (
    CERTIFICATE_TEMPLATE_HEIGHT,
    CERTIFICATE_TEMPLATE_WIDTH,
    CERTIFICATE_TEMPLATE_PATH,
    approve_certificate_request,
    reject_certificate_request,
    revoke_certificate_request,
)
from apps.franchise.certificate_storage import PrivateStorageProxy, get_certificate_storage
from apps.franchise.models import (
    CertificateRequest,
    FranchiseProfile,
    FranchiseStaff,
)
from apps.students.models import Student
from apps.universities.models import University


class StudentGrowthAnalyticsTests(TestCase):
    def setUp(self):
        self.university = University.objects.create(
            name="Growth University",
            slug="growth-university",
            description="Analytics test institution",
        )
        category = CourseCategory.objects.create(
            name="Growth Category",
            slug="growth-category",
        )
        self.course = Course.objects.create(
            name="Growth Course",
            slug="growth-course",
            category=category,
            university=self.university,
            short_description="Course",
            full_description="Course description",
        )
        self.owner = User.objects.create_user(
            username="growth-owner",
            password="safe-test-password",
        )
        self.franchise = FranchiseProfile.objects.create(
            user=self.owner,
            mobile="9999999901",
            city="Kota",
            state="Rajasthan",
            monthly_student_target=4,
        )
        self.staff_user = User.objects.create_user(
            username="growth-staff",
            password="safe-test-password",
        )
        self.staff = FranchiseStaff.objects.create(
            franchise=self.franchise,
            user=self.staff_user,
            name="Growth Staff",
            email="growth-staff@example.com",
        )
        self.other_owner = User.objects.create_user(
            username="other-growth-owner",
            password="safe-test-password",
        )
        self.other_franchise = FranchiseProfile.objects.create(
            user=self.other_owner,
            mobile="9999999902",
            city="Ajmer",
            state="Rajasthan",
        )
        self.analytics_date = date(2026, 6, 15)

    def create_student(self, franchise=None, created_at=None, name="Analytics Student"):
        student = Student.objects.create(
            full_name=name,
            mobile="9999999903",
            course=self.course,
            university=self.university,
            franchise=franchise or self.franchise,
            created_by=self.owner,
        )
        if created_at:
            local_timestamp = timezone.make_aware(
                datetime.combine(created_at, time(12)),
                timezone.get_current_timezone(),
            )
            Student.objects.filter(pk=student.pk).update(created_at=local_timestamp)
        return student

    def test_total_current_and_previous_month_counts_and_growth(self):
        self.create_student(created_at=date(2026, 6, 1))
        self.create_student(created_at=date(2026, 6, 15))
        self.create_student(created_at=date(2026, 6, 30))
        self.create_student(created_at=date(2026, 5, 5))
        self.create_student(created_at=date(2026, 5, 25))
        self.create_student(created_at=date(2026, 4, 10))

        analytics = get_student_growth_analytics(
            self.franchise,
            as_of=self.analytics_date,
        )

        self.assertEqual(analytics["total"], 6)
        self.assertEqual(analytics["this_month"], 3)
        self.assertEqual(analytics["previous_month"], 2)
        self.assertEqual(analytics["growth_percentage"], 50)

    def test_chart_has_six_calendar_months_and_includes_empty_months(self):
        self.create_student(created_at=date(2026, 1, 10))
        self.create_student(created_at=date(2026, 3, 10))
        self.create_student(created_at=date(2026, 3, 20))
        self.create_student(created_at=date(2026, 5, 10))
        self.create_student(created_at=date(2026, 5, 20))
        self.create_student(created_at=date(2026, 6, 10))

        analytics = get_student_growth_analytics(
            self.franchise,
            as_of=self.analytics_date,
        )

        self.assertEqual(
            analytics["chart_labels"],
            ["January 2026", "February 2026", "March 2026",
             "April 2026", "May 2026", "June 2026"],
        )
        self.assertEqual(analytics["chart_counts"], [1, 0, 2, 0, 2, 1])
        self.assertEqual(len(analytics["chart_data"]), 6)

    def test_zero_previous_month_has_no_growth_percentage(self):
        self.create_student(created_at=date(2026, 6, 10))

        analytics = get_student_growth_analytics(
            self.franchise,
            as_of=self.analytics_date,
        )

        self.assertIsNone(analytics["growth_percentage"])

    def test_empty_dataset_returns_zero_counts_and_full_chart(self):
        analytics = get_student_growth_analytics(
            self.franchise,
            as_of=self.analytics_date,
        )

        self.assertEqual(analytics["total"], 0)
        self.assertEqual(analytics["this_month"], 0)
        self.assertEqual(analytics["previous_month"], 0)
        self.assertIsNone(analytics["growth_percentage"])
        self.assertEqual(analytics["chart_counts"], [0, 0, 0, 0, 0, 0])
        self.assertEqual(analytics["target_remaining"], 4)
        self.assertEqual(analytics["target_progress"], 0)
        self.assertEqual(analytics["reached_milestones"], [])
        self.assertEqual(analytics["next_milestone"]["remaining"], 10)

    def test_target_progress_remaining_and_progress_bar_cap(self):
        for _ in range(3):
            self.create_student(created_at=date(2026, 6, 10))

        analytics = get_student_growth_analytics(
            self.franchise,
            as_of=self.analytics_date,
        )
        self.assertEqual(analytics["target"], 4)
        self.assertEqual(analytics["target_remaining"], 1)
        self.assertEqual(analytics["target_progress"], 75)
        self.assertEqual(analytics["target_progress_bar"], 75)

        self.create_student(created_at=date(2026, 6, 12))
        self.create_student(created_at=date(2026, 6, 13))
        analytics = get_student_growth_analytics(
            self.franchise,
            as_of=self.analytics_date,
        )
        self.assertEqual(analytics["target_remaining"], 0)
        self.assertEqual(analytics["target_progress"], 125)
        self.assertEqual(analytics["target_progress_bar"], 100)

    def test_milestones_and_next_milestone_are_derived_from_total(self):
        for _ in range(26):
            self.create_student(created_at=date(2026, 4, 10))

        analytics = get_student_growth_analytics(
            self.franchise,
            as_of=self.analytics_date,
        )

        self.assertEqual(
            [item["label"] for item in analytics["reached_milestones"]],
            ["First Step", "Growing Franchise"],
        )
        self.assertEqual(analytics["next_milestone"]["label"], "Rising Star")
        self.assertEqual(analytics["next_milestone"]["remaining"], 24)

    def test_owner_and_active_staff_only_receive_their_own_franchise_data(self):
        self.create_student(name="Private Franchise Student")
        self.create_student(
            franchise=self.other_franchise,
            name="Another Franchise Student",
        )

        with patch(
            "apps.franchise.analytics.timezone.localdate",
            return_value=timezone.localdate(),
        ):
            self.client.force_login(self.owner)
            owner_response = self.client.get(
                reverse("franchise:dashboard"),
                {"franchise_id": self.other_franchise.pk},
            )
            self.assertEqual(owner_response.status_code, 200)
            self.assertEqual(owner_response.context["stats"]["total_students"], 1)
            self.assertEqual(owner_response.context["analytics"]["total"], 1)
            self.assertContains(owner_response, "Monthly Registrations")
            self.assertContains(owner_response, "student-growth-labels")
            self.assertContains(owner_response, "studentGrowthChart")
            self.assertNotContains(owner_response, "Another Franchise Student")

            self.client.force_login(self.staff_user)
            staff_response = self.client.get(
                reverse("franchise:staff_dashboard"),
                {"franchise_id": self.other_franchise.pk},
            )
            self.assertEqual(staff_response.status_code, 200)
            self.assertEqual(staff_response.context["stats"]["total_students"], 1)
            self.assertEqual(staff_response.context["analytics"]["total"], 1)
            self.assertContains(staff_response, "Monthly Registrations")
            self.assertNotContains(staff_response, "Another Franchise Student")


class CertificateRequestTests(TestCase):
    def setUp(self):
        self.university = University.objects.create(
            name="Verified University",
            slug="verified-university",
            description="Test institution",
        )
        category = CourseCategory.objects.create(
            name="Test Category",
            slug="certificate-test-category",
        )
        self.course = Course.objects.create(
            name="Test Course",
            slug="certificate-test-course",
            category=category,
            university=self.university,
            short_description="Course",
            full_description="Course description",
        )
        self.owner_user = User.objects.create_user(
            username="owner",
            email="owner@example.com",
            password="StrongPass123!",
        )
        self.franchise = FranchiseProfile.objects.create(
            user=self.owner_user,
            mobile="9999999991",
            city="Kota",
            state="Rajasthan",
            business_name="Kota Learning Centre",
        )
        self.staff_user = User.objects.create_user(
            username="staff",
            email="staff@example.com",
            password="StrongPass123!",
        )
        self.staff = FranchiseStaff.objects.create(
            franchise=self.franchise,
            user=self.staff_user,
            name="Branch Staff",
            email="staff@example.com",
        )
        self.admin_user = User.objects.create_superuser(
            username="admin",
            email="admin@example.com",
            password="StrongPass123!",
        )
        self.student = self.create_student(
            self.franchise,
            self.owner_user,
            "Test Student",
            "RG-CERT-STUDENT-1",
        )
        self.request = CertificateRequest.objects.create(
            student=self.student,
            franchise=self.franchise,
            requested_by=self.owner_user,
        )
        self.created_certificate_names = []

    def tearDown(self):
        storage = CertificateRequest._meta.get_field("certificate_file").storage
        for name in self.created_certificate_names:
            if storage.exists(name):
                storage.delete(name)
        if self.student.profile_image:
            image_storage = self.student.profile_image.storage
            if image_storage.exists(self.student.profile_image.name):
                image_storage.delete(self.student.profile_image.name)

    def create_student(self, franchise, creator, name, registration_number):
        student = Student.objects.create(
            full_name=name,
            mobile="9999999992",
            course=self.course,
            university=self.university,
            franchise=franchise,
            created_by=creator,
            admission_status="enrolled",
        )
        Student.objects.filter(pk=student.pk).update(
            registration_number=registration_number
        )
        student.refresh_from_db()
        return student

    def approve(self, certificate_request):
        certificate_request.eligibility_verified = True
        certificate_request.eligibility_remarks = "Verified against the completion record."
        certificate_request.save(
            update_fields=("eligibility_verified", "eligibility_remarks")
        )
        approved = approve_certificate_request(
            certificate_request.pk,
            self.admin_user,
            lambda token: f"/franchise/certificates/verify/{token}/",
        )
        self.created_certificate_names.append(approved.certificate_file.name)
        return approved

    def test_anonymous_users_cannot_access_certificate_request_pages(self):
        response = self.client.get(reverse("franchise:certificate_requests"))
        self.assertEqual(response.status_code, 302)

    def test_franchise_owner_can_access_own_history_and_students(self):
        self.client.force_login(self.owner_user)
        response = self.client.get(
            reverse("franchise:certificate_requests"),
            {"q": self.student.registration_number},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.student.registration_number)
        self.assertContains(response, self.request.get_status_display())

    def test_active_franchise_staff_can_access_certificate_requests(self):
        self.client.force_login(self.staff_user)
        response = self.client.get(reverse("franchise:certificate_requests"))
        self.assertEqual(response.status_code, 200)

    def test_existing_student_picker_lists_only_authenticated_franchise_students(self):
        other_user = User.objects.create_user(
            username="other-picker-owner",
            password="StrongPass123!",
        )
        other_franchise = FranchiseProfile.objects.create(
            user=other_user,
            mobile="9999999994",
            city="Ajmer",
            state="Rajasthan",
        )
        other_student = self.create_student(
            other_franchise,
            other_user,
            "Private Other Student",
            "RG-CERT-STUDENT-PICKER",
        )
        self.client.force_login(self.owner_user)
        response = self.client.get(reverse("franchise:certificate_request_select"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.student.registration_number)
        self.assertNotContains(response, other_student.registration_number)

        response = self.client.post(
            reverse("franchise:certificate_request_select"),
            {"student": other_student.pk},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Select a valid choice")

    def test_existing_student_selection_continues_to_review(self):
        self.request.delete()
        self.client.force_login(self.staff_user)
        response = self.client.post(
            reverse("franchise:certificate_request_select"),
            {"student": self.student.pk},
        )
        self.assertRedirects(
            response,
            reverse(
                "franchise:certificate_request_create",
                args=(self.student.pk,),
            ),
        )
        review = self.client.get(response.url)
        self.assertEqual(review.status_code, 200)
        self.assertContains(review, self.student.registration_number)

    def test_add_student_reuses_registration_form_and_returns_to_certificate_review(self):
        self.client.force_login(self.owner_user)
        response = self.client.post(
            f"{reverse('students:register')}?next=certificate_request",
            {
                "full_name": "New Certificate Student",
                "mobile": "9999999876",
                "course": self.course.pk,
                "university": self.university.pk,
                "study_mode": "odl",
                "admission_status": "enrolled",
                "fee_status": "pending",
            },
        )
        student = Student.objects.get(full_name="New Certificate Student")
        self.assertEqual(student.franchise, self.franchise)
        self.assertEqual(student.created_by, self.owner_user)
        self.assertRedirects(
            response,
            reverse("franchise:certificate_request_create", args=(student.pk,)),
        )
        self.assertFalse(CertificateRequest.objects.filter(student=student).exists())
        self.assertEqual(self.client.get(response.url).status_code, 200)

    def test_franchise_cannot_request_another_franchises_student(self):
        other_user = User.objects.create_user(
            username="other-owner",
            password="StrongPass123!",
        )
        other_franchise = FranchiseProfile.objects.create(
            user=other_user,
            mobile="9999999993",
            city="Jaipur",
            state="Rajasthan",
        )
        other_student = self.create_student(
            other_franchise,
            other_user,
            "Other Student",
            "RG-CERT-STUDENT-2",
        )
        self.client.force_login(self.owner_user)
        response = self.client.get(
            reverse(
                "franchise:certificate_request_create",
                args=(other_student.pk,),
            )
        )
        self.assertEqual(response.status_code, 404)

    def test_request_creation_uses_authenticated_franchise_and_user(self):
        self.request.delete()
        self.client.force_login(self.staff_user)
        response = self.client.post(
            reverse(
                "franchise:certificate_request_create",
                args=(self.student.pk,),
            ),
            {"confirm": "on"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Request submitted for review")
        self.assertContains(response, "does not confirm course completion")
        request = CertificateRequest.objects.get(
            student=self.student,
            status=CertificateRequest.STATUS_PENDING,
        )
        self.assertEqual(request.franchise, self.franchise)
        self.assertEqual(request.requested_by, self.staff_user)

    def test_request_creation_database_error_shows_safe_message(self):
        self.request.delete()
        self.client.force_login(self.owner_user)
        with patch(
            "apps.franchise.certificate_views.CertificateRequest.objects.create",
            side_effect=OSError("database details must not reach the response"),
        ):
            response = self.client.post(
                reverse(
                    "franchise:certificate_request_create",
                    args=(self.student.pk,),
                ),
                {"confirm": "on"},
            )
        self.assertEqual(response.status_code, 503)
        self.assertContains(
            response,
            "We could not save this request right now",
            status_code=503,
        )
        self.assertNotContains(response, "database details", status_code=503)

    def test_duplicate_pending_requests_are_prevented_by_database_constraint(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                CertificateRequest.objects.create(
                    student=self.student,
                    franchise=self.franchise,
                    requested_by=self.owner_user,
                )

    def test_duplicate_submission_links_to_existing_request(self):
        self.client.force_login(self.owner_user)
        response = self.client.post(
            reverse(
                "franchise:certificate_request_create",
                args=(self.student.pk,),
            ),
            {"confirm": "on"},
        )
        self.assertRedirects(
            response,
            f"{reverse('franchise:certificate_requests')}#certificate-request-{self.request.pk}",
        )
        self.assertEqual(
            CertificateRequest.objects.filter(
                student=self.student,
                status=CertificateRequest.STATUS_PENDING,
            ).count(),
            1,
        )
        history = self.client.get(reverse("franchise:certificate_requests"))
        self.assertContains(history, f'id="certificate-request-{self.request.pk}"')

    def test_franchise_user_cannot_approve_a_request(self):
        with self.assertRaises(PermissionError):
            approve_certificate_request(
                self.request.pk,
                self.owner_user,
                lambda token: "/verify/",
            )
        self.request.refresh_from_db()
        self.assertEqual(self.request.status, CertificateRequest.STATUS_PENDING)

    def test_superuser_must_verify_eligibility_before_approval(self):
        with self.assertRaisesMessage(ValueError, "Verify course eligibility"):
            approve_certificate_request(
                self.request.pk,
                self.admin_user,
                lambda token: "/verify/",
            )
        self.request.refresh_from_db()
        self.assertEqual(self.request.status, CertificateRequest.STATUS_PENDING)
        self.assertFalse(self.request.certificate_file)

    def test_superuser_must_record_eligibility_evidence(self):
        self.request.eligibility_verified = True
        self.request.save(update_fields=("eligibility_verified",))
        with self.assertRaisesMessage(ValueError, "Record the eligibility evidence"):
            approve_certificate_request(
                self.request.pk,
                self.admin_user,
                lambda token: "/verify/",
            )
        self.request.refresh_from_db()
        self.assertEqual(self.request.status, CertificateRequest.STATUS_PENDING)

    def test_only_superuser_can_reject_and_rejected_requests_cannot_download(self):
        with self.assertRaises(PermissionError):
            reject_certificate_request(self.request.pk, self.owner_user)
        rejected = reject_certificate_request(self.request.pk, self.admin_user)
        self.assertEqual(rejected.status, CertificateRequest.STATUS_REJECTED)
        self.client.force_login(self.owner_user)
        response = self.client.get(
            reverse("franchise:certificate_download", args=(rejected.pk,))
        )
        self.assertEqual(response.status_code, 404)

    def test_pending_requests_cannot_be_downloaded(self):
        self.client.force_login(self.owner_user)
        response = self.client.get(
            reverse("franchise:certificate_download", args=(self.request.pk,))
        )
        self.assertEqual(response.status_code, 404)

    def test_owner_cannot_download_another_franchises_certificate(self):
        other_user = User.objects.create_user(
            username="other-owner",
            password="StrongPass123!",
        )
        other_franchise = FranchiseProfile.objects.create(
            user=other_user,
            mobile="9999999993",
            city="Jaipur",
            state="Rajasthan",
        )
        other_student = self.create_student(
            other_franchise,
            other_user,
            "Other Student",
            "RG-CERT-STUDENT-3",
        )
        other_request = CertificateRequest.objects.create(
            student=other_student,
            franchise=other_franchise,
            requested_by=other_user,
            eligibility_verified=True,
        )
        other_request = self.approve(other_request)
        self.client.force_login(self.owner_user)
        response = self.client.get(
            reverse("franchise:certificate_download", args=(other_request.pk,))
        )
        self.assertEqual(response.status_code, 404)

    def test_superuser_approval_generates_unique_certificate_and_valid_pdf(self):
        self.student.guardian_name = "Test Guardian"
        self.student.save(update_fields=("guardian_name",))
        self.course.duration = "12 months"
        self.course.save(update_fields=("duration",))
        photo = BytesIO()
        Image.new("RGB", (240, 360), (55, 150, 110)).save(photo, format="PNG")
        self.student.profile_image.save(
            "certificate-student.png",
            ContentFile(photo.getvalue()),
            save=True,
        )

        approved = self.approve(self.request)
        self.assertEqual(approved.status, CertificateRequest.STATUS_APPROVED)
        self.assertTrue(approved.certificate_number)
        self.assertIsNotNone(approved.reviewed_at)
        self.assertEqual(approved.reviewed_by, self.admin_user)
        self.assertIsNotNone(approved.issued_at)
        certificate_number = approved.certificate_number

        with approved.certificate_file.open("rb") as certificate_file:
            pdf_bytes = certificate_file.read()
        with self.assertRaises(ValueError):
            approved.certificate_file.url
        self.assertTrue(pdf_bytes.startswith(b"%PDF-"))
        self.assertIn(b"startxref", pdf_bytes)
        self.assertTrue(pdf_bytes.rstrip().endswith(b"%%EOF"))
        reader = PdfReader(approved.certificate_file.path)
        self.assertEqual(len(reader.pages), 1)
        page = reader.pages[0]
        self.assertAlmostEqual(
            float(page.mediabox.width) / float(page.mediabox.height),
            CERTIFICATE_TEMPLATE_WIDTH / CERTIFICATE_TEMPLATE_HEIGHT,
            places=5,
        )
        self.assertTrue(CERTIFICATE_TEMPLATE_PATH.is_file())
        self.assertEqual(len(page.images), 2)
        self.assertIn(
            (CERTIFICATE_TEMPLATE_WIDTH, CERTIFICATE_TEMPLATE_HEIGHT),
            {image.image.size for image in page.images},
        )
        page_text = page.extract_text()
        for certificate_value in (
            self.student.full_name,
            self.student.guardian_name,
            self.student.registration_number,
            self.course.name,
            self.university.name,
            self.course.duration,
            approved.certificate_number,
            approved.issued_at.strftime("%d %B %Y"),
            "/franchise/certificates/verify/",
        ):
            self.assertIn(certificate_value, page_text)
        text_positions = {}

        def record_text_position(text, matrix, text_matrix, font_dict, font_size):
            if self.student.full_name in text:
                text_positions["student_name"] = (text_matrix[4], text_matrix[5])

        page.extract_text(visitor_text=record_text_position)
        self.assertIn("student_name", text_positions)
        name_x, name_y = text_positions["student_name"]
        expected_scale = float(page.mediabox.height) / CERTIFICATE_TEMPLATE_HEIGHT
        self.assertGreaterEqual(name_x, 205 * expected_scale)
        self.assertLess(name_x, (205 + 1585) * expected_scale / 2)
        self.assertAlmostEqual(
            name_y,
            (CERTIFICATE_TEMPLATE_HEIGHT - 1139) * expected_scale,
            delta=2,
        )
        with self.assertRaisesMessage(ValueError, "Only pending"):
            approve_certificate_request(
                approved.pk,
                self.admin_user,
                lambda token: "/verify/",
            )
        approved.refresh_from_db()
        self.assertEqual(approved.certificate_number, certificate_number)

    def test_certificate_name_supports_devanagari_text(self):
        self.student.full_name = "राजवंश विद्यार्थी"
        self.student.save(update_fields=("full_name",))
        approved = self.approve(self.request)

        with approved.certificate_file.open("rb") as certificate_file:
            reader = PdfReader(certificate_file)
            self.assertIn(
                self.student.full_name,
                reader.pages[0].extract_text(),
            )

    def test_approved_certificate_download_and_verification(self):
        approved = self.approve(self.request)
        self.client.force_login(self.owner_user)
        download = self.client.get(
            reverse("franchise:certificate_download", args=(approved.pk,))
        )
        self.assertEqual(download.status_code, 200)
        self.assertEqual(download["Content-Type"], "application/pdf")
        download.close()

        verified = self.client.get(
            reverse(
                "franchise:certificate_verify",
                kwargs={"token": approved.verification_token},
            )
        )
        self.assertContains(verified, "Certificate verified")
        self.assertContains(verified, approved.certificate_number)
        self.assertNotContains(verified, self.franchise.business_name)

        approved = revoke_certificate_request(approved.pk, self.admin_user)
        self.assertEqual(approved.revoked_by, self.admin_user)
        self.assertIsNotNone(approved.revoked_at)
        self.assertEqual(
            self.client.get(
                reverse("franchise:certificate_download", args=(approved.pk,))
            ).status_code,
            404,
        )
        revoked_verification = self.client.get(
            reverse(
                "franchise:certificate_verify",
                kwargs={"token": approved.verification_token},
            )
        )
        self.assertContains(revoked_verification, "Certificate not valid")

    def test_pdf_generation_failure_keeps_request_pending(self):
        self.request.eligibility_verified = True
        self.request.eligibility_remarks = "Verified against the completion record."
        self.request.save(
            update_fields=("eligibility_verified", "eligibility_remarks")
        )
        with patch(
            "apps.franchise.certificate_service.generate_certificate_pdf",
            side_effect=RuntimeError("PDF backend unavailable"),
        ):
            with self.assertRaises(RuntimeError):
                approve_certificate_request(
                    self.request.pk,
                    self.admin_user,
                    lambda token: "/verify/",
                )
        self.request.refresh_from_db()
        self.assertEqual(self.request.status, CertificateRequest.STATUS_PENDING)
        self.assertFalse(self.request.certificate_file)
        self.assertIsNone(self.request.certificate_number)
        self.assertIsNone(self.request.reviewed_at)

    def test_storage_save_failure_keeps_request_pending(self):
        self.request.eligibility_verified = True
        self.request.eligibility_remarks = "Verified against the completion record."
        self.request.save(
            update_fields=("eligibility_verified", "eligibility_remarks")
        )
        storage = CertificateRequest._meta.get_field("certificate_file").storage
        with patch.object(storage, "_save", side_effect=OSError("storage unavailable")):
            with self.assertRaises(OSError):
                approve_certificate_request(
                    self.request.pk,
                    self.admin_user,
                    lambda token: "/verify/",
                )
        self.request.refresh_from_db()
        self.assertEqual(self.request.status, CertificateRequest.STATUS_PENDING)
        self.assertFalse(self.request.certificate_file)
        self.assertIsNone(self.request.certificate_number)

    def test_storage_read_failure_returns_safe_temporary_error(self):
        approved = self.approve(self.request)
        self.client.force_login(self.owner_user)
        with patch.object(
            approved.certificate_file.storage,
            "open",
            side_effect=OSError("storage credentials"),
        ):
            response = self.client.get(
                reverse("franchise:certificate_download", args=(approved.pk,))
            )
        self.assertEqual(response.status_code, 503)
        self.assertContains(
            response,
            "temporarily unavailable",
            status_code=503,
        )
        self.assertNotContains(response, "storage credentials", status_code=503)

    @override_settings(
        CERTIFICATE_STORAGE_BACKEND="django.core.files.storage.InMemoryStorage",
        CERTIFICATE_STORAGE_OPTIONS={},
    )
    def test_configured_storage_backend_remains_private(self):
        storage = get_certificate_storage()
        self.assertIsInstance(storage, PrivateStorageProxy)
        stored_name = storage.save("certificate.pdf", ContentFile(b"%PDF-test"))
        self.addCleanup(storage.delete, stored_name)
        with storage.open(stored_name, "rb") as certificate_file:
            self.assertEqual(certificate_file.read(), b"%PDF-test")
        with self.assertRaises(ValueError):
            storage.url(stored_name)

    def test_approved_requests_prevent_another_active_certificate(self):
        approved = self.approve(self.request)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                CertificateRequest.objects.create(
                    student=self.student,
                    franchise=self.franchise,
                    status=CertificateRequest.STATUS_APPROVED,
                )
        revoke_certificate_request(approved.pk, self.admin_user)
        replacement = CertificateRequest.objects.create(
            student=self.student,
            franchise=self.franchise,
            requested_by=self.owner_user,
        )
        self.assertEqual(replacement.status, CertificateRequest.STATUS_PENDING)

    def test_rejected_request_can_be_resubmitted_without_losing_history(self):
        reject_certificate_request(self.request.pk, self.admin_user)
        replacement = CertificateRequest.objects.create(
            student=self.student,
            franchise=self.franchise,
            requested_by=self.owner_user,
        )
        self.assertEqual(
            CertificateRequest.objects.filter(student=self.student).count(),
            2,
        )
        self.assertEqual(replacement.status, CertificateRequest.STATUS_PENDING)

    def test_separate_approved_requests_receive_different_certificate_numbers(self):
        first = self.approve(self.request)
        another_student = self.create_student(
            self.franchise,
            self.owner_user,
            "Second Student",
            "RG-CERT-STUDENT-4",
        )
        another_request = CertificateRequest.objects.create(
            student=another_student,
            franchise=self.franchise,
            requested_by=self.owner_user,
            eligibility_verified=True,
        )
        second = self.approve(another_request)
        self.assertNotEqual(first.certificate_number, second.certificate_number)

    def test_franchise_login_dashboard_and_homepage_navigation(self):
        home = self.client.get(reverse("core:home"))
        self.assertNotContains(home, "Franchise Login")
        self.assertNotContains(home, f'href="{reverse("franchise:login")}"')
        about = self.client.get(reverse("core:about"))
        self.assertContains(about, "Franchise Login")
        self.assertContains(about, f'href="{reverse("franchise:login")}"')
        self.assertEqual(self.client.get(reverse("franchise:login")).status_code, 200)

        self.client.force_login(self.owner_user)
        dashboard = self.client.get(reverse("franchise:dashboard"))
        self.assertEqual(dashboard.status_code, 200)
        self.assertContains(dashboard, "Course Certificates")

        self.client.force_login(self.staff_user)
        staff_dashboard = self.client.get(reverse("franchise:staff_dashboard"))
        self.assertEqual(staff_dashboard.status_code, 200)
        self.assertContains(staff_dashboard, "Course Certificates")

    def test_admin_access_remains_superuser_only(self):
        self.client.force_login(self.owner_user)
        response = self.client.get("/admin/franchise/certificaterequest/")
        self.assertIn(response.status_code, (302, 403))

        self.client.force_login(self.admin_user)
        response = self.client.get("/admin/franchise/certificaterequest/")
        self.assertEqual(response.status_code, 200)
        detail = self.client.get(
            f"/admin/franchise/certificaterequest/{self.request.pk}/change/"
        )
        self.assertEqual(detail.status_code, 200)
        self.assertContains(detail, "Eligibility verified")
        self.request.eligibility_verified = True
        self.request.eligibility_remarks = "Verified against official completion evidence."
        self.request.save(
            update_fields=("eligibility_verified", "eligibility_remarks")
        )
        response = self.client.post(
            reverse("admin:franchise_certificaterequest_changelist"),
            {
                "action": "approve_requests",
                "_selected_action": [str(self.request.pk)],
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.request.refresh_from_db()
        self.assertEqual(self.request.status, CertificateRequest.STATUS_APPROVED)
        approved = self.request
        self.created_certificate_names.append(approved.certificate_file.name)
        download = self.client.get(
            reverse(
                "admin:franchise_certificaterequest_download_certificate",
                args=(approved.pk,),
            )
        )
        self.assertEqual(download.status_code, 200)
        download.close()
        response = self.client.post(
            reverse("admin:franchise_certificaterequest_changelist"),
            {
                "action": "revoke_certificates",
                "_selected_action": [str(approved.pk)],
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        approved.refresh_from_db()
        self.assertTrue(approved.is_revoked)
        self.assertEqual(approved.revoked_by, self.admin_user)
        self.assertIsNotNone(approved.revoked_at)
        self.assertEqual(
            self.client.get(
                reverse(
                    "admin:franchise_certificaterequest_download_certificate",
                    args=(approved.pk,),
                )
            ).status_code,
            404,
        )

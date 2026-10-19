from unittest.mock import patch

from django.contrib.auth.models import User
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse
from pypdf import PdfReader

from apps.courses.models import Course, CourseCategory
from apps.franchise.certificate_service import (
    approve_certificate_request,
    reject_certificate_request,
)
from apps.franchise.models import (
    CertificateRequest,
    FranchiseProfile,
    FranchiseStaff,
)
from apps.students.models import Student
from apps.universities.models import University


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
        self.assertRedirects(response, reverse("franchise:certificate_requests"))
        request = CertificateRequest.objects.get(
            student=self.student,
            status=CertificateRequest.STATUS_PENDING,
        )
        self.assertEqual(request.franchise, self.franchise)
        self.assertEqual(request.requested_by, self.staff_user)

    def test_duplicate_pending_requests_are_prevented_by_database_constraint(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                CertificateRequest.objects.create(
                    student=self.student,
                    franchise=self.franchise,
                    requested_by=self.owner_user,
                )

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
        self.assertIn(self.student.full_name, reader.pages[0].extract_text())
        with self.assertRaisesMessage(ValueError, "Only pending"):
            approve_certificate_request(
                approved.pk,
                self.admin_user,
                lambda token: "/verify/",
            )
        approved.refresh_from_db()
        self.assertEqual(approved.certificate_number, certificate_number)

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

        approved.is_revoked = True
        approved.save(update_fields=("is_revoked",))
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

    def test_approved_requests_prevent_another_active_certificate(self):
        approved = self.approve(self.request)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                CertificateRequest.objects.create(
                    student=self.student,
                    franchise=self.franchise,
                    status=CertificateRequest.STATUS_APPROVED,
                )
        approved.is_revoked = True
        approved.save(update_fields=("is_revoked",))
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
        approved = self.approve(self.request)
        download = self.client.get(
            reverse(
                "admin:franchise_certificaterequest_download_certificate",
                args=(approved.pk,),
            )
        )
        self.assertEqual(download.status_code, 200)
        download.close()

import datetime
from unittest.mock import Mock, patch
from django.contrib import admin
from django.contrib.auth.models import User
from django.contrib.auth.tokens import default_token_generator
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.courses.models import Course, CourseCategory
from apps.franchise.models import (
    FranchiseActivationToken,
    FranchiseApplication,
    FranchiseProfile,
    FranchiseStaff,
    FranchiseStaffInvitation,
)
from apps.franchise.admin import FranchiseStaffAdmin
from apps.franchise.admin import _send_activation_email
from apps.students.models import Student
from apps.universities.models import University


class FranchiseUpgradeIntegrationTests(TestCase):
    def setUp(self):
        # 1. Base university and course
        self.university = University.objects.create(
            name="Apex State University",
            slug="apex-state-university",
            description="Leading university",
            active=True,
        )
        self.category = CourseCategory.objects.create(
            name="Information Technology",
            slug="information-technology",
            active=True,
        )
        self.course = Course.objects.create(
            name="BCA Online",
            slug="bca-online",
            category=self.category,
            university=self.university,
            short_description="Bachelor of Computer Applications",
            full_description="Full curriculum",
            duration="3 Years",
            fee=45000,
            regular_available=True,
            odl_available=True,
            active=True,
        )

        # 2. Franchise 1 (Jaipur)
        self.owner1_user = User.objects.create_user(
            username="owner1@jaipur.com",
            email="owner1@jaipur.com",
            password="StrongPassword123!",
            first_name="Ramesh",
            last_name="Sharma",
            is_active=True,
        )
        self.franchise1 = FranchiseProfile.objects.create(
            user=self.owner1_user,
            mobile="9829012345",
            city="Jaipur",
            state="Rajasthan",
            business_name="Jaipur Central Branch",
        )

        # 3. Franchise 2 (Jodhpur)
        self.owner2_user = User.objects.create_user(
            username="owner2@jodhpur.com",
            email="owner2@jodhpur.com",
            password="StrongPassword123!",
            first_name="Suresh",
            last_name="Verma",
            is_active=True,
        )
        self.franchise2 = FranchiseProfile.objects.create(
            user=self.owner2_user,
            mobile="9829054321",
            city="Jodhpur",
            state="Rajasthan",
            business_name="Jodhpur Tech Center",
        )

        # 4. Superuser (Parent Administrator)
        self.admin_user = User.objects.create_superuser(
            username="admin@rajvans.com",
            email="admin@rajvans.com",
            password="AdminSecretPass123!",
            first_name="Rajvans",
            last_name="Admin",
        )

        # 5. Franchise 1 Staff member
        self.staff1_user = User.objects.create_user(
            username="staff1@jaipur.com",
            email="staff1@jaipur.com",
            password="StaffPass123!",
            first_name="Pooja",
            last_name="Gupta",
            is_active=True,
        )
        self.staff1 = FranchiseStaff.objects.create(
            franchise=self.franchise1,
            user=self.staff1_user,
            name="Pooja Gupta",
            email="staff1@jaipur.com",
            role="counsellor",
            is_active=True,
        )

    # ── Authentication & Role Redirection Tests ───────────────────────────────

    def test_franchise_owner_login_redirects_to_franchise_dashboard(self):
        response = self.client.post(
            reverse("franchise:login"),
            {"email": "owner1@jaipur.com", "password": "StrongPassword123!"},
        )
        self.assertRedirects(response, reverse("franchise:dashboard"))

    def test_homepage_hides_franchise_login_but_other_pages_keep_link(self):
        self.client.force_login(self.admin_user)
        home_response = self.client.get(reverse("core:home"))
        self.assertNotContains(
            home_response,
            f'href="{reverse("franchise:login")}"',
        )
        about_response = self.client.get(reverse("core:about"))
        self.assertContains(
            about_response,
            f'href="{reverse("franchise:login")}"',
        )
        self.client.logout()

        login_response = self.client.get(reverse("franchise:login"))
        self.assertEqual(login_response.status_code, 200)

    def test_authenticated_superuser_stays_on_franchise_login_page(self):
        self.client.force_login(self.admin_user)

        response = self.client.get(reverse("franchise:login"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Django Admin accounts do not automatically")

    def test_franchise_login_next_cannot_redirect_to_admin(self):
        owner_response = self.client.post(
            f'{reverse("franchise:login")}?next={reverse("admin:index")}',
            {
                "email": "owner1@jaipur.com",
                "password": "StrongPassword123!",
                "next": reverse("admin:index"),
            },
        )
        self.assertRedirects(owner_response, reverse("franchise:dashboard"))

        self.client.logout()
        staff_response = self.client.post(
            f'{reverse("franchise:login")}?next={reverse("admin:index")}',
            {
                "email": "staff1@jaipur.com",
                "password": "StaffPass123!",
                "next": reverse("admin:index"),
            },
        )
        self.assertRedirects(staff_response, reverse("franchise:staff_dashboard"))

    @override_settings(RESEND_API_KEY="test-resend-key")
    @patch(
        "apps.franchise.admin.resend.Emails.send",
        return_value={"id": "test-email-id"},
    )
    def test_public_approval_activation_and_owner_login_workflow(self, _send_email):
        response = self.client.post(
            reverse("franchise:register"),
            {
                "name": "New Franchise Owner",
                "mobile": "9876543210",
                "email": "new-owner@example.com",
                "city": "Jaipur",
                "state": "Rajasthan",
                "business_name": "New Jaipur Branch",
            },
        )
        self.assertRedirects(response, reverse("franchise:landing"))

        application = FranchiseApplication.objects.get(
            email="new-owner@example.com"
        )
        self.assertEqual(application.status, "pending")
        self.assertIsNone(application.user)

        self.client.force_login(self.admin_user)
        response = self.client.post(
            reverse("admin:franchise_franchiseapplication_changelist"),
            {
                "action": "approve_applications",
                "_selected_action": [str(application.pk)],
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)

        application.refresh_from_db()
        self.assertEqual(application.status, "approved")
        owner = application.user
        self.assertFalse(owner.is_active)
        self.assertFalse(owner.is_staff)
        self.assertFalse(owner.is_superuser)

        activation = application.activation_token
        self.client.logout()
        response = self.client.post(
            reverse("franchise:activate", kwargs={"token": activation.token}),
            {
                "password1": "ActivationPassJf782!x",
                "password2": "ActivationPassJf782!x",
            },
        )
        self.assertRedirects(response, reverse("franchise:dashboard"))
        owner.refresh_from_db()
        activation.refresh_from_db()
        self.assertTrue(owner.is_active)
        self.assertFalse(owner.is_staff)
        self.assertFalse(owner.is_superuser)
        self.assertTrue(activation.used)

        self.client.logout()
        response = self.client.post(
            reverse("franchise:login"),
            {
                "email": "new-owner@example.com",
                "password": "ActivationPassJf782!x",
            },
        )
        self.assertRedirects(response, reverse("franchise:dashboard"))

    def test_only_active_superusers_can_access_django_admin(self):
        legacy_staff_user = User.objects.create_user(
            username="legacy-staff",
            email="legacy-staff@example.com",
            password="LegacyStaffPass123!",
            is_staff=True,
        )

        for user in (self.owner1_user, self.staff1_user, legacy_staff_user):
            with self.subTest(user=user.username):
                self.client.force_login(user)
                response = self.client.get(reverse("admin:index"))
                self.assertEqual(response.status_code, 302)
                self.assertTrue(response.url.startswith(reverse("admin:login")))

        self.client.force_login(legacy_staff_user)
        response = self.client.get(reverse("franchise:login"))
        self.assertRedirects(response, reverse("core:home"))

        self.client.force_login(self.admin_user)
        response = self.client.get(reverse("admin:index"))
        self.assertEqual(response.status_code, 200)

    def test_franchise_staff_login_redirects_to_staff_dashboard(self):
        response = self.client.post(
            reverse("franchise:login"),
            {"email": "staff1@jaipur.com", "password": "StaffPass123!"},
        )
        self.assertRedirects(response, reverse("franchise:staff_dashboard"))

    def test_privileged_application_account_cannot_be_activated(self):
        self.owner1_user.is_staff = True
        self.owner1_user.save(update_fields=["is_staff"])
        application = FranchiseApplication.objects.create(
            name="Misconfigured Owner",
            email="misconfigured-owner@example.com",
            mobile="9876543220",
            city="Jaipur",
            state="Rajasthan",
            status="approved",
            user=self.owner1_user,
        )
        token = FranchiseActivationToken.objects.create(
            application=application,
            token="privileged-owner-activation-token",
        )

        response = self.client.post(
            reverse("franchise:activate", kwargs={"token": token.token}),
            {
                "password1": "ActivationPassJf782!x",
                "password2": "ActivationPassJf782!x",
            },
        )

        self.assertRedirects(response, reverse("franchise:login"))
        self.owner1_user.refresh_from_db()
        token.refresh_from_db()
        self.assertTrue(self.owner1_user.is_active)
        self.assertTrue(self.owner1_user.is_staff)
        self.assertFalse(token.used)

    def test_inactive_user_cannot_login(self):
        self.owner1_user.is_active = False
        self.owner1_user.save()
        response = self.client.post(
            reverse("franchise:login"),
            {"email": "owner1@jaipur.com", "password": "StrongPassword123!"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "has not been activated yet")
        self.client.force_login(self.owner1_user)
        response = self.client.get(reverse("franchise:dashboard"))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith(reverse("franchise:login")))

    def test_unapproved_applicant_cannot_access_dashboard(self):
        unapproved_user = User.objects.create_user(
            username="applicant@pending.com",
            email="applicant@pending.com",
            password="PendingPass123!",
        )
        self.client.force_login(unapproved_user)
        response = self.client.get(reverse("franchise:dashboard"))
        # Should be redirected to home with warning message
        self.assertRedirects(response, reverse("core:home"))

    # ── Activation Workflow & Token Expiry Tests ──────────────────────────────

    def test_activation_workflow_success(self):
        app = FranchiseApplication.objects.create(
            name="Vikram Singh",
            email="vikram@udaipur.com",
            mobile="9829099999",
            city="Udaipur",
            state="Rajasthan",
            status="approved",
        )
        user = User.objects.create_user(
            username="vikram@udaipur.com",
            email="vikram@udaipur.com",
            is_active=False,
        )
        app.user = user
        app.save()
        FranchiseProfile.objects.create(
            user=user,
            mobile=app.mobile,
            city=app.city,
            state=app.state,
        )

        token = FranchiseActivationToken.objects.create(
            application=app,
            token="test-valid-token-12345",
        )

        # Post new password
        response = self.client.post(
            reverse("franchise:activate", kwargs={"token": token.token}),
            {"password1": "NewPassUdaipur123!", "password2": "NewPassUdaipur123!"},
        )
        self.assertRedirects(response, reverse("franchise:dashboard"))

        user.refresh_from_db()
        self.assertTrue(user.is_active)
        self.assertTrue(user.check_password("NewPassUdaipur123!"))
        token.refresh_from_db()
        self.assertTrue(token.used)

        self.client.logout()
        repeated_response = self.client.post(
            reverse("franchise:activate", kwargs={"token": token.token}),
            {
                "password1": "AnotherPassUdaipur123!",
                "password2": "AnotherPassUdaipur123!",
            },
        )
        self.assertRedirects(repeated_response, reverse("franchise:login"))
        user.refresh_from_db()
        self.assertTrue(user.check_password("NewPassUdaipur123!"))

    def test_activation_rejects_application_user_email_mismatch(self):
        app = FranchiseApplication.objects.create(
            name="Mismatched Applicant",
            email="applicant@example.com",
            mobile="9829011111",
            city="Jaipur",
            state="Rajasthan",
            status="approved",
        )
        user = User.objects.create_user(
            username="other-account@example.com",
            email="other-account@example.com",
            password="OriginalPass123!",
            is_active=False,
        )
        app.user = user
        app.save(update_fields=["user"])
        token = FranchiseActivationToken.objects.create(
            application=app,
            token="mismatched-activation-token",
        )

        response = self.client.post(
            reverse("franchise:activate", kwargs={"token": token.token}),
            {"password1": "NewPassUdaipur123!", "password2": "NewPassUdaipur123!"},
        )

        self.assertRedirects(response, reverse("franchise:login"))
        user.refresh_from_db()
        token.refresh_from_db()
        self.assertFalse(user.is_active)
        self.assertTrue(user.check_password("OriginalPass123!"))
        self.assertFalse(token.used)

    def test_expired_activation_token_rejected(self):
        app = FranchiseApplication.objects.create(
            name="Late User",
            email="late@user.com",
            mobile="9829088888",
            city="Ajmer",
            state="Rajasthan",
            status="approved",
        )
        token = FranchiseActivationToken.objects.create(
            application=app,
            token="expired-token-54321",
        )
        # Artificially age the token past 24 hours
        token.created_at = timezone.now() - datetime.timedelta(hours=25)
        token.save()

        response = self.client.get(reverse("franchise:activate", kwargs={"token": token.token}))
        self.assertRedirects(response, reverse("franchise:login"))

    @override_settings(RESEND_API_KEY="test-resend-key")
    @patch(
        "apps.franchise.admin.resend.Emails.send",
        return_value={"id": "test-email-id"},
    )
    def test_admin_activation_resend_renews_expired_token(self, _send_email):
        app = FranchiseApplication.objects.create(
            name="Expired Applicant",
            email="expired@applicant.com",
            mobile="9829088887",
            city="Ajmer",
            state="Rajasthan",
            status="approved",
            user=self.owner1_user,
        )
        token = FranchiseActivationToken.objects.create(
            application=app,
            token="old-expired-token",
        )
        token.created_at = timezone.now() - datetime.timedelta(hours=25)
        token.save(update_fields=["created_at"])
        request = Mock()
        request.build_absolute_uri.side_effect = lambda path: f"https://example.test{path}"

        self.assertTrue(_send_activation_email(request, app, renew=True))

        token.refresh_from_db()
        self.assertNotEqual(token.token, "old-expired-token")
        self.assertFalse(token.is_expired)
        self.assertFalse(token.used)

    def test_staff_invitation_acceptance_is_single_use_and_time_limited(self):
        staff = FranchiseStaff.objects.create(
            franchise=self.franchise1,
            name="Invitee Person",
            email="invitee@jaipur.com",
        )
        invitation = FranchiseStaffInvitation.objects.create(
            staff=staff,
            token="single-use-invitation",
        )
        accept_url = reverse(
            "franchise:accept_staff_invitation",
            kwargs={"token": invitation.token},
        )
        password_data = {
            "password1": "InviteeStrongPass123!",
            "password2": "InviteeStrongPass123!",
        }

        response = self.client.post(accept_url, password_data)
        self.assertRedirects(response, reverse("franchise:staff_dashboard"))
        staff.refresh_from_db()
        invitation.refresh_from_db()
        self.assertTrue(invitation.used)
        self.assertTrue(staff.user.check_password(password_data["password1"]))

        reused_response = self.client.post(accept_url, password_data)
        self.assertEqual(reused_response.status_code, 302)
        self.assertEqual(reused_response.url, reverse("franchise:login"))

        expired_staff = FranchiseStaff.objects.create(
            franchise=self.franchise1,
            name="Expired Invitee",
            email="expired-invitee@jaipur.com",
        )
        expired_invitation = FranchiseStaffInvitation.objects.create(
            staff=expired_staff,
            token="expired-staff-invitation",
        )
        expired_invitation.created_at = timezone.now() - datetime.timedelta(hours=25)
        expired_invitation.save(update_fields=["created_at"])
        expired_response = self.client.post(
            reverse(
                "franchise:accept_staff_invitation",
                kwargs={"token": expired_invitation.token},
            ),
            password_data,
        )
        self.assertEqual(expired_response.status_code, 302)
        self.assertEqual(expired_response.url, reverse("franchise:login"))
        self.assertFalse(User.objects.filter(username=expired_staff.email).exists())

    def test_staff_invitation_cannot_reset_existing_privileged_account(self):
        privileged_user = User.objects.create_superuser(
            username="collision@jaipur.com",
            email="different-address@example.com",
            password="OriginalAdminPass123!",
        )
        staff = FranchiseStaff.objects.create(
            franchise=self.franchise1,
            name="Collision User",
            email="collision@jaipur.com",
        )
        invitation = FranchiseStaffInvitation.objects.create(
            staff=staff,
            token="collision-invitation-token",
        )

        response = self.client.post(
            reverse(
                "franchise:accept_staff_invitation",
                kwargs={"token": invitation.token},
            ),
            {"password1": "AttackerPass123!", "password2": "AttackerPass123!"},
        )

        self.assertRedirects(response, reverse("franchise:login"))
        privileged_user.refresh_from_db()
        invitation.refresh_from_db()
        self.assertTrue(privileged_user.is_superuser)
        self.assertTrue(privileged_user.check_password("OriginalAdminPass123!"))
        self.assertFalse(invitation.used)

    def test_staff_invitation_creation_rejects_existing_username(self):
        User.objects.create_user(
            username="username-collision@jaipur.com",
            email="different-address@example.com",
            password="ExistingPass123!",
        )
        self.client.force_login(self.owner1_user)

        response = self.client.post(
            reverse("franchise:staff_invite"),
            {
                "name": "Collision User",
                "email": "username-collision@jaipur.com",
                "role": "counsellor",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "already associated with an account")
        self.assertFalse(
            FranchiseStaff.objects.filter(email="username-collision@jaipur.com").exists()
        )

    def test_deactivated_staff_cannot_login_or_continue_existing_session(self):
        self.staff1.is_active = False
        self.staff1.save(update_fields=["is_active"])

        response = self.client.post(
            reverse("franchise:login"),
            {"email": "staff1@jaipur.com", "password": "StaffPass123!"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "staff account has been deactivated")

        self.client.force_login(self.staff1_user)
        response = self.client.get(reverse("students:list"))
        self.assertRedirects(response, reverse("franchise:login"))

    def test_staff_admin_form_synchronizes_user_active_state(self):
        self.client.force_login(self.admin_user)
        model_admin = FranchiseStaffAdmin(FranchiseStaff, admin.site)
        staff = FranchiseStaff.objects.get(pk=self.staff1.pk)
        staff.is_active = False
        model_admin.save_model(
            Mock(),
            staff,
            Mock(),
            change=True,
        )

        self.staff1_user.refresh_from_db()
        self.assertFalse(self.staff1_user.is_active)

    # ── Password Reset Workflow Tests ─────────────────────────────────────────

    def test_forgot_password_generates_console_email(self):
        mail.outbox = []
        response = self.client.post(
            reverse("franchise:forgot_password"),
            {"email": "owner1@jaipur.com"},
        )
        self.assertRedirects(response, reverse("franchise:login"))
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Password Reset", mail.outbox[0].subject)
        self.assertIn("owner1@jaipur.com", mail.outbox[0].to)

    def test_forgot_password_response_does_not_disclose_unknown_email(self):
        mail.outbox = []

        known_response = self.client.post(
            reverse("franchise:forgot_password"),
            {"email": "owner1@jaipur.com"},
            follow=True,
        )
        known_messages = [str(message) for message in known_response.context["messages"]]

        unknown_response = self.client.post(
            reverse("franchise:forgot_password"),
            {"email": "not-registered@example.com"},
            follow=True,
        )
        unknown_messages = [
            str(message) for message in unknown_response.context["messages"]
        ]

        self.assertEqual(known_response.redirect_chain, unknown_response.redirect_chain)
        self.assertEqual(known_messages, unknown_messages)
        self.assertEqual(len(mail.outbox), 1)

    def test_password_reset_token_expires_after_one_hour_and_is_single_use(self):
        from django.conf import settings
        from django.utils.http import urlsafe_base64_encode
        from django.utils.encoding import force_bytes
        from django.utils import timezone

        self.assertEqual(settings.PASSWORD_RESET_TIMEOUT, 3600)
        uid = urlsafe_base64_encode(force_bytes(self.owner1_user.pk))
        token_time = datetime.datetime.now() - datetime.timedelta(hours=2)
        with patch.object(default_token_generator, "_now", return_value=token_time):
            token = default_token_generator.make_token(self.owner1_user)

        response = self.client.get(
            reverse(
                "franchise:reset_password",
                kwargs={"uidb64": uid, "token": token},
            )
        )
        self.assertRedirects(response, reverse("franchise:forgot_password"))

        token = default_token_generator.make_token(self.owner1_user)
        reset_url = reverse(
            "franchise:reset_password",
            kwargs={"uidb64": uid, "token": token},
        )
        response = self.client.post(
            reset_url,
            {"password1": "NewSecurePass123!", "password2": "NewSecurePass123!"},
        )
        self.assertRedirects(response, reverse("franchise:login"))
        self.owner1_user.refresh_from_db()
        self.assertTrue(self.owner1_user.check_password("NewSecurePass123!"))
        reuse_response = self.client.get(reset_url)
        self.assertEqual(reuse_response.status_code, 302)
        self.assertEqual(reuse_response.url, reverse("franchise:forgot_password"))

    def test_password_reset_does_not_activate_inactive_account(self):
        from django.utils.encoding import force_bytes
        from django.utils.http import urlsafe_base64_encode

        self.owner1_user.is_active = False
        self.owner1_user.save(update_fields=["is_active"])
        uid = urlsafe_base64_encode(force_bytes(self.owner1_user.pk))
        token = default_token_generator.make_token(self.owner1_user)
        reset_url = reverse(
            "franchise:reset_password",
            kwargs={"uidb64": uid, "token": token},
        )

        response = self.client.post(
            reset_url,
            {"password1": "NewSecurePass123!", "password2": "NewSecurePass123!"},
        )

        self.assertRedirects(response, reverse("franchise:login"))
        self.owner1_user.refresh_from_db()
        self.assertFalse(self.owner1_user.is_active)
        self.assertTrue(self.owner1_user.check_password("NewSecurePass123!"))

    # ── Strict Franchise Data Isolation Tests ────────────────────────────────

    def test_student_registration_assigns_correct_franchise(self):
        self.client.force_login(self.owner1_user)
        response = self.client.post(
            reverse("students:register"),
            {
                "full_name": "Aakash Sharma",
                "guardian_name": "Ramesh Sharma",
                "mobile": "9988776655",
                "email": "aakash@student.com",
                "course": self.course.pk,
                "university": self.university.pk,
                "study_mode": "odl",
                "admission_status": "admitted",
                "fee_status": "paid",
            },
        )
        self.assertRedirects(response, reverse("students:list"))

        student = Student.objects.get(email="aakash@student.com")
        self.assertEqual(student.franchise, self.franchise1)
        self.assertEqual(student.created_by, self.owner1_user)
        self.assertTrue(student.registration_number.startswith("RG-"))

    def test_anonymous_and_unapproved_users_cannot_access_student_endpoints(self):
        student = Student.objects.create(
            full_name="Protected Student",
            mobile="9111111144",
            course=self.course,
            university=self.university,
            franchise=self.franchise1,
        )
        protected_urls = [
            reverse("students:list"),
            reverse("students:register"),
            reverse("students:export_csv"),
            reverse("students:detail", kwargs={"pk": student.pk}),
            reverse("students:edit", kwargs={"pk": student.pk}),
        ]

        for url in protected_urls:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 302)
                self.assertTrue(response.url.startswith(reverse("franchise:login")))

        response = self.client.post(
            reverse("students:register"),
            {
                "full_name": "Unauthorized Student",
                "mobile": "9111111155",
                "course": self.course.pk,
                "university": self.university.pk,
                "study_mode": "regular",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Student.objects.filter(full_name="Unauthorized Student").exists())

        applicant = User.objects.create_user(
            username="waiting-applicant@example.com",
            email="waiting-applicant@example.com",
            password="WaitingPass123!",
        )
        self.client.force_login(applicant)
        for url in protected_urls:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertRedirects(response, reverse("core:home"))

        response = self.client.post(
            reverse("students:edit", kwargs={"pk": student.pk}),
            {"full_name": "Tampered", "mobile": "9111111144"},
        )
        self.assertRedirects(response, reverse("core:home"))
        student.refresh_from_db()
        self.assertEqual(student.full_name, "Protected Student")

    def test_student_list_date_filters_are_rendered_and_applied(self):
        matching = Student.objects.create(
            full_name="Date Filter Match",
            mobile="9111111122",
            course=self.course,
            university=self.university,
            franchise=self.franchise1,
        )
        Student.objects.create(
            full_name="Date Filter Other",
            mobile="9111111133",
            course=self.course,
            university=self.university,
            franchise=self.franchise1,
        )
        matching.created_at = timezone.now() - datetime.timedelta(days=5)
        matching.save(update_fields=["created_at"])
        self.client.force_login(self.owner1_user)

        response = self.client.get(
            reverse("students:list"),
            {
                "date_from": (timezone.localdate() - datetime.timedelta(days=6)).isoformat(),
                "date_to": (timezone.localdate() - datetime.timedelta(days=4)).isoformat(),
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="date_from"')
        self.assertContains(response, 'name="date_to"')
        self.assertContains(response, matching.registration_number)
        self.assertEqual(response.context["total"], 1)

    def test_franchise_cannot_view_or_edit_other_franchise_students(self):
        # Create student belonging to Franchise 1
        s1 = Student.objects.create(
            full_name="Student One",
            mobile="9111111111",
            course=self.course,
            university=self.university,
            study_mode="odl",
            franchise=self.franchise1,
            created_by=self.owner1_user,
        )

        # Log in as Franchise 2 owner
        self.client.force_login(self.owner2_user)

        # 1. Student list should not show Franchise 1's student
        list_res = self.client.get(reverse("students:list"))
        self.assertNotContains(list_res, s1.registration_number)

        # 2. Direct detail access must return 404
        detail_res = self.client.get(reverse("students:detail", kwargs={"pk": s1.pk}))
        self.assertEqual(detail_res.status_code, 404)

        # 3. Direct edit access must return 404
        edit_res = self.client.get(reverse("students:edit", kwargs={"pk": s1.pk}))
        self.assertEqual(edit_res.status_code, 404)

        # A forged POST must also stay inside the tenant-scoped queryset.
        post_res = self.client.post(
            reverse("students:edit", kwargs={"pk": s1.pk}),
            {"full_name": "Tampered", "mobile": "9111111111"},
        )
        self.assertEqual(post_res.status_code, 404)
        s1.refresh_from_db()
        self.assertEqual(s1.full_name, "Student One")

    def test_franchise_staff_cannot_access_another_franchises_students(self):
        other_franchise_student = Student.objects.create(
            full_name="Other Franchise Student",
            mobile="9222222299",
            course=self.course,
            university=self.university,
            franchise=self.franchise2,
        )
        self.client.force_login(self.staff1_user)

        list_response = self.client.get(reverse("students:list"))
        self.assertNotContains(list_response, other_franchise_student.registration_number)

        detail_response = self.client.get(
            reverse("students:detail", kwargs={"pk": other_franchise_student.pk})
        )
        self.assertEqual(detail_response.status_code, 404)

        edit_response = self.client.post(
            reverse("students:edit", kwargs={"pk": other_franchise_student.pk}),
            {"full_name": "Changed by Other Franchise", "mobile": "9222222299"},
        )
        self.assertEqual(edit_response.status_code, 404)
        other_franchise_student.refresh_from_db()
        self.assertEqual(other_franchise_student.full_name, "Other Franchise Student")

        export_response = self.client.get(reverse("students:export_csv"))
        self.assertEqual(export_response.status_code, 200)
        self.assertNotIn(
            "Other Franchise Student",
            export_response.content.decode("utf-8"),
        )

    def test_parent_admin_can_view_all_students(self):
        # Student 1 in Jaipur
        s1 = Student.objects.create(
            full_name="Jaipur Student",
            mobile="9111111111",
            course=self.course,
            university=self.university,
            franchise=self.franchise1,
        )
        # Student 2 in Jodhpur
        s2 = Student.objects.create(
            full_name="Jodhpur Student",
            mobile="9222222222",
            course=self.course,
            university=self.university,
            franchise=self.franchise2,
        )

        # Superuser views student list
        self.client.force_login(self.admin_user)
        response = self.client.get(reverse("students:list"))
        self.assertContains(response, s1.registration_number)
        self.assertContains(response, s2.registration_number)

    def test_csv_export_respects_franchise_isolation(self):
        Student.objects.create(
            full_name="Jaipur Student Export",
            mobile="9111111111",
            course=self.course,
            university=self.university,
            franchise=self.franchise1,
        )
        Student.objects.create(
            full_name="Jodhpur Student Export",
            mobile="9222222222",
            course=self.course,
            university=self.university,
            franchise=self.franchise2,
        )

        # Owner 1 exports CSV
        self.client.force_login(self.owner1_user)
        response = self.client.get(reverse("students:export_csv"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/csv")
        content = response.content.decode("utf-8")
        self.assertIn("Jaipur Student Export", content)
        self.assertNotIn("Jodhpur Student Export", content)

    def test_csv_export_escapes_spreadsheet_formulas(self):
        student = Student.objects.create(
            full_name="=HYPERLINK(\"https://example.invalid\")",
            mobile="9111111111",
            email="@SUM(1,1)",
            course=self.course,
            university=self.university,
            franchise=self.franchise1,
        )
        self.client.force_login(self.owner1_user)

        response = self.client.get(reverse("students:export_csv"))

        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")
        self.assertIn("'=HYPERLINK", content)
        self.assertIn("'@SUM", content)
        self.assertIn(student.registration_number, content)

    # ── Staff Management Tests ───────────────────────────────────────────────

    def test_franchise_owner_can_invite_staff(self):
        mail.outbox = []
        self.client.force_login(self.owner1_user)
        response = self.client.post(
            reverse("franchise:staff_invite"),
            {
                "name": "Karan Mehra",
                "email": "karan@jaipur.com",
                "role": "data_entry",
            },
        )
        self.assertRedirects(response, reverse("franchise:staff_list"))
        self.assertTrue(
            FranchiseStaff.objects.filter(email="karan@jaipur.com", franchise=self.franchise1).exists()
        )
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Invitation to join", mail.outbox[0].subject)

    def test_staff_cannot_access_owner_staff_management(self):
        self.client.force_login(self.staff1_user)
        management_urls = [
            reverse("franchise:staff_list"),
            reverse("franchise:staff_invite"),
            reverse("franchise:staff_toggle", kwargs={"pk": self.staff1.pk}),
            reverse("franchise:staff_resend_invitation", kwargs={"pk": self.staff1.pk}),
        ]
        for url in management_urls:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertRedirects(response, reverse("franchise:staff_dashboard"))
                response = self.client.post(url, {})
                self.assertRedirects(response, reverse("franchise:staff_dashboard"))


    def test_deactivated_staff_cannot_login(self):
        self.staff1.is_active = False
        self.staff1.save()
        self.staff1_user.is_active = False
        self.staff1_user.save()

        response = self.client.post(
            reverse("franchise:login"),
            {"email": "staff1@jaipur.com", "password": "StaffPass123!"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "has not been activated yet")

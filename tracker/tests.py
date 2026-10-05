from datetime import date

from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

from .models import (Group, GroupMembership, Interview, InterviewRound, InterviewStatus, User)


class Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user("admin", password="pw12345!", is_admin=True)
        cls.alice = User.objects.create_user("alice", password="pw12345!", is_student=True)
        cls.bob = User.objects.create_user("bob", password="pw12345!", is_student=True)
        cls.group = Group.objects.create(name="Batch A", admin=cls.admin)
        for s in (cls.alice, cls.bob):
            GroupMembership.objects.create(group=cls.group, student=s)
        cls.iv = Interview.objects.create(student=cls.alice, group=cls.group, company_name="Acme",
                                          role="Dev", date_of_interview=date.today())


class ModelTests(Base):
    def test_default_status_and_badge(self):
        self.assertEqual(self.iv.final_status, "in-progress")
        InterviewStatus.objects.create(interview=self.iv, final_status="selected")
        self.iv.refresh_from_db()
        self.assertEqual(self.iv.final_label, "Selected")

    def test_duplicate_membership_rejected(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            GroupMembership.objects.create(group=self.group, student=self.alice)

    def test_progress(self):
        InterviewRound.objects.create(interview=self.iv, round_number=1, description="x", status="cleared")
        InterviewRound.objects.create(interview=self.iv, round_number=2, description="y")
        self.assertEqual(self.iv.progress, "1/2 cleared")

    def test_superuser_is_admin(self):
        self.assertTrue(User.objects.create_superuser("root", password="x").is_admin)


class AuthTests(Base):
    def test_login_redirects_by_role(self):
        r = self.client.post(reverse("login"), {"username": "admin", "password": "pw12345!"})
        self.assertRedirects(r, reverse("admin_dashboard"))
        self.client.logout()
        r = self.client.post(reverse("login"), {"username": "alice", "password": "pw12345!"})
        self.assertRedirects(r, reverse("student_dashboard"))

    def test_register_creates_student(self):
        r = self.client.post(reverse("register"), {
            "username": "dave", "email": "d@example.com",
            "password1": "S7rong-pass-99", "password2": "S7rong-pass-99"})
        self.assertRedirects(r, reverse("student_dashboard"))
        self.assertTrue(User.objects.get(username="dave").is_student)

    def test_anonymous_redirected(self):
        r = self.client.get(reverse("student_dashboard"))
        self.assertEqual(r.status_code, 302)


class PermissionTests(Base):
    def test_student_cannot_open_admin_pages(self):
        self.client.force_login(self.alice)
        for name in ("admin_dashboard", "admin_groups", "admin_students"):
            self.assertEqual(self.client.get(reverse(name)).status_code, 403)
        self.assertEqual(self.client.get(reverse("admin_group_detail", args=[self.group.pk])).status_code, 403)
        self.assertEqual(self.client.get(
            reverse("admin_student_detail", args=[self.alice.pk])).status_code, 403)

    def test_admin_cannot_open_student_pages(self):
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(reverse("student_dashboard")).status_code, 403)

    def test_student_cannot_see_others_interview(self):
        self.client.force_login(self.bob)
        url = reverse("student_interview_detail", args=[self.iv.pk])
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(self.client.post(reverse("round_add", args=[self.iv.pk]),
                                          {"description": "hack"}).status_code, 404)
        self.assertEqual(self.client.post(reverse("interview_delete", args=[self.iv.pk])).status_code, 404)

    def test_other_admin_cannot_open_group(self):
        other = User.objects.create_user("admin2", password="pw12345!", is_admin=True)
        self.client.force_login(other)
        self.assertEqual(self.client.get(reverse("admin_group_detail", args=[self.group.pk])).status_code, 404)


class ViewTests(Base):
    def test_main_pages_render_for_each_role(self):
        self.client.force_login(self.admin)
        for name, args in (
            ("admin_dashboard", ()),
            ("admin_groups", ()),
            ("admin_students", ()),
            ("admin_group_detail", (self.group.pk,)),
            ("admin_student_detail", (self.alice.pk,)),
        ):
            response = self.client.get(reverse(name, args=args))
            self.assertEqual(response.status_code, 200, name)
            self.assertContains(response, "/static/css/app.css")
            self.assertNotContains(response, "cdn.tailwindcss.com")

        self.client.force_login(self.alice)
        for name, args in (
            ("student_dashboard", ()),
            ("student_interviews", ()),
            ("student_interview_detail", (self.iv.pk,)),
        ):
            self.assertEqual(self.client.get(reverse(name, args=args)).status_code, 200, name)

    def test_student_directory_is_scoped_to_admin_groups(self):
        unassigned = User.objects.create_user("unassigned", is_student=True)
        self.client.force_login(self.admin)

        response = self.client.get(reverse("admin_students"))

        self.assertContains(response, "alice")
        self.assertContains(response, "bob")
        self.assertNotContains(response, "unassigned")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            self.client.get(reverse("admin_student_detail", args=[unassigned.pk])).status_code,
            404,
        )

    def test_students_created_by_admin_are_in_directory(self):
        self.client.force_login(self.admin)
        response = self.client.post(reverse("admin_dashboard"), {
            "username": "created-student",
            "email": "created@example.com",
            "password1": "T7rong-pass-99",
            "password2": "T7rong-pass-99",
        })

        student = User.objects.get(username="created-student")
        self.assertEqual(student.created_by, self.admin)
        self.assertRedirects(response, reverse("admin_dashboard"))
        self.assertEqual(self.client.get(reverse("admin_students")).status_code, 200)
        self.assertEqual(
            self.client.get(reverse("admin_student_detail", args=[student.pk])).status_code,
            200,
        )

    def test_other_admin_cannot_view_student_details(self):
        other = User.objects.create_user("admin2", is_admin=True)
        self.client.force_login(other)
        self.assertEqual(
            self.client.get(reverse("admin_student_detail", args=[self.alice.pk])).status_code,
            404,
        )

    def test_admin_creates_group_and_adds_member(self):
        self.client.force_login(self.admin)
        r = self.client.post(reverse("admin_groups"), {"name": "Batch B", "description": ""})
        g = Group.objects.get(name="Batch B")
        self.assertRedirects(r, reverse("admin_group_detail", args=[g.pk]))
        self.client.post(reverse("admin_group_detail", args=[g.pk]), {"student": self.alice.pk})
        self.assertTrue(g.memberships.filter(student=self.alice).exists())

    def test_student_adds_interview_only_for_own_group(self):
        outsider_group = Group.objects.create(name="Other", admin=self.admin)
        self.client.force_login(self.alice)
        data = {"company_name": "Globex", "role": "QA", "date_of_interview": "2026-01-10"}
        r = self.client.post(reverse("student_interviews"), {**data, "group": outsider_group.pk})
        self.assertEqual(r.status_code, 200)  # form error, nothing created
        self.assertFalse(Interview.objects.filter(company_name="Globex").exists())
        self.client.post(reverse("student_interviews"), {**data, "group": self.group.pk})
        self.assertTrue(Interview.objects.filter(company_name="Globex", student=self.alice).exists())

    def test_student_saves_hr_contact_details(self):
        self.client.force_login(self.alice)
        response = self.client.post(reverse("student_interviews"), {
            "group": self.group.pk,
            "company_name": "Globex",
            "role": "QA",
            "date_of_interview": "2026-01-10",
            "hr_name": "Jordan Lee",
            "hr_contact_number": "+1 555 0123",
            "hr_email": "jordan@example.com",
        })

        interview = Interview.objects.get(company_name="Globex")
        self.assertRedirects(
            response, reverse("student_interview_detail", args=[interview.pk]))
        self.assertEqual(interview.hr_name, "Jordan Lee")
        self.assertEqual(interview.hr_contact_number, "+1 555 0123")
        self.assertEqual(interview.hr_email, "jordan@example.com")
        self.assertContains(
            self.client.get(reverse("student_interview_detail", args=[interview.pk])),
            "jordan@example.com",
        )

    def test_removing_student_from_group_deletes_only_that_groups_interviews(self):
        InterviewRound.objects.create(
            interview=self.iv, round_number=1, description="Technical")
        InterviewStatus.objects.create(interview=self.iv, final_status="selected")
        another_group = Group.objects.create(name="Batch B", admin=self.admin)
        GroupMembership.objects.create(group=another_group, student=self.alice)
        other_interview = Interview.objects.create(
            student=self.alice,
            group=another_group,
            company_name="Other company",
            role="Engineer",
            date_of_interview=date.today(),
        )
        self.client.force_login(self.admin)

        response = self.client.post(
            reverse("member_remove", args=[self.group.pk, self.alice.pk]))

        self.assertRedirects(response, reverse("admin_group_detail", args=[self.group.pk]))
        self.assertFalse(Interview.objects.filter(pk=self.iv.pk).exists())
        self.assertFalse(InterviewRound.objects.filter(interview_id=self.iv.pk).exists())
        self.assertFalse(InterviewStatus.objects.filter(interview_id=self.iv.pk).exists())
        self.assertTrue(Interview.objects.filter(pk=other_interview.pk).exists())
        self.assertTrue(GroupMembership.objects.filter(
            group=another_group, student=self.alice).exists())

    def test_deleting_membership_directly_also_removes_interviews(self):
        membership = GroupMembership.objects.get(group=self.group, student=self.alice)

        membership.delete()

        self.assertFalse(Interview.objects.filter(pk=self.iv.pk).exists())

    def test_ajax_add_rounds_and_validation(self):
        self.client.force_login(self.alice)
        url = reverse("round_add", args=[self.iv.pk])
        self.assertEqual(self.client.post(url, {"description": "Coding test"}).status_code, 201)
        self.client.post(url, {"description": "HR"})
        self.assertEqual(list(self.iv.rounds.values_list("round_number", flat=True)), [1, 2])
        self.assertEqual(self.client.post(url, {"description": "  "}).status_code, 400)

    def test_csrf_enforced_on_ajax(self):
        from django.test import Client
        c = Client(enforce_csrf_checks=True)
        c.force_login(self.alice)
        self.assertEqual(c.post(reverse("round_add", args=[self.iv.pk]), {"description": "x"}).status_code, 403)

    def test_final_status_requires_completed_rounds(self):
        self.client.force_login(self.alice)
        url = reverse("interview_status", args=[self.iv.pk])
        self.client.post(url, {"final_status": "selected"})
        self.assertFalse(InterviewStatus.objects.filter(interview=self.iv).exists())  # no rounds
        rnd = InterviewRound.objects.create(interview=self.iv, round_number=1, description="x")
        self.client.post(url, {"final_status": "selected"})
        self.assertFalse(InterviewStatus.objects.filter(interview=self.iv).exists())  # pending round
        self.client.post(reverse("round_update", args=[rnd.pk]), {"status": "cleared"})
        self.client.post(url, {"final_status": "selected"})
        self.assertEqual(InterviewStatus.objects.get(interview=self.iv).final_status, "selected")

    def test_pending_round_reopens_finalized_interview(self):
        self.client.force_login(self.alice)
        rnd = InterviewRound.objects.create(
            interview=self.iv, round_number=1, description="Technical", status="cleared")
        InterviewStatus.objects.create(interview=self.iv, final_status="selected")

        response = self.client.post(
            reverse("round_update", args=[rnd.pk]), {"status": "pending"})

        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(response.content, {
            "status": "pending",
            "badge": "status-pending",
            "final_status": "in-progress",
            "final_label": "In progress",
        })
        self.assertFalse(InterviewStatus.objects.filter(interview=self.iv).exists())

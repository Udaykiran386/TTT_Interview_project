from datetime import date, timedelta

from django.core.management.base import BaseCommand

from tracker.models import (Group, GroupMembership, Interview, InterviewRound, InterviewStatus, User)

PASSWORD = "demo12345"


class Command(BaseCommand):
    help = "Create demo data: 1 admin, 3 students, 1 group, 2 interviews."

    def handle(self, *args, **opts):
        admin, _ = User.objects.get_or_create(
            username="admin", defaults={"email": "admin@example.com", "is_admin": True})
        students = []
        for n in ("alice", "bob", "carol"):
            u, _ = User.objects.get_or_create(
                username=n, defaults={"email": f"{n}@example.com", "is_student": True})
            students.append(u)
        for u in [admin, *students]:
            u.set_password(PASSWORD)
            u.save()

        group, _ = Group.objects.get_or_create(
            name="Batch 2026", admin=admin, defaults={"description": "Final-year placement batch"})
        for s in students:
            GroupMembership.objects.get_or_create(group=group, student=s)

        today = date.today()
        specs = [
            (students[0], "Acme Corp", "Backend Engineer", today - timedelta(days=10), "selected",
             [("Online coding test", "cleared"), ("Technical interview", "cleared"), ("HR round", "cleared")]),
            (students[1], "Globex", "Data Analyst", today - timedelta(days=3), None,
             [("Aptitude test", "cleared"), ("Technical interview", "pending")]),
        ]
        for student, company, role, day, final, rounds in specs:
            iv, created = Interview.objects.get_or_create(
                student=student, group=group, company_name=company,
                defaults={"role": role, "date_of_interview": day})
            if not created:
                continue
            for i, (desc, st) in enumerate(rounds, 1):
                InterviewRound.objects.create(interview=iv, round_number=i, description=desc, status=st)
            if final:
                InterviewStatus.objects.create(interview=iv, final_status=final)
        self.stdout.write(self.style.SUCCESS(
            f"Seeded. Logins: admin / alice / bob / carol, password '{PASSWORD}'."))

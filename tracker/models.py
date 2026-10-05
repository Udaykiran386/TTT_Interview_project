from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models.signals import post_delete
from django.dispatch import receiver


class User(AbstractUser):
    is_admin = models.BooleanField(default=False)
    is_student = models.BooleanField(default=False)
    created_by = models.ForeignKey(
        "self",
        blank=True,
        limit_choices_to={"is_admin": True},
        null=True,
        on_delete=models.SET_NULL,
        related_name="students_created",
    )

    def save(self, *args, **kwargs):
        if self.is_superuser:
            self.is_admin = True
        super().save(*args, **kwargs)


class Group(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    admin = models.ForeignKey(User, on_delete=models.CASCADE, related_name="groups_created",
                              limit_choices_to={"is_admin": True})
    students = models.ManyToManyField(User, through="GroupMembership", related_name="student_groups")

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.name


class GroupMembership(models.Model):
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name="memberships")
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name="memberships",
                                limit_choices_to={"is_student": True})
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("group", "student")

    def __str__(self):
        return f"{self.student} in {self.group}"


BADGES = {
    "selected": "status-selected",
    "not-selected": "status-not-selected",
    "in-progress": "status-in-progress",
    "pending": "status-pending",
    "cleared": "status-cleared",
    "rejected": "status-rejected",
}


class Interview(models.Model):
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name="interviews")
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name="interviews")
    company_name = models.CharField(max_length=150)
    role = models.CharField(max_length=150)
    date_of_interview = models.DateField()
    hr_name = models.CharField(max_length=150, blank=True)
    hr_contact_number = models.CharField(max_length=30, blank=True)
    hr_email = models.EmailField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date_of_interview", "-created_at"]

    def __str__(self):
        return f"{self.company_name} - {self.role}"

    @property
    def final_status(self):
        try:
            return self.status.final_status
        except InterviewStatus.DoesNotExist:
            return "in-progress"

    @property
    def final_label(self):
        return self.final_status.replace("-", " ").capitalize()

    @property
    def badge(self):
        return BADGES[self.final_status]

    @property
    def progress(self):
        rounds = list(self.rounds.all())
        return f"{sum(r.status == 'cleared' for r in rounds)}/{len(rounds)} cleared"


@receiver(post_delete, sender=GroupMembership)
def delete_group_interviews(sender, instance, **kwargs):
    Interview.objects.filter(
        group_id=instance.group_id,
        student_id=instance.student_id,
    ).delete()


class InterviewRound(models.Model):
    PENDING, CLEARED, REJECTED = "pending", "cleared", "rejected"
    STATUS_CHOICES = [(PENDING, "Pending"), (CLEARED, "Cleared"), (REJECTED, "Rejected")]

    interview = models.ForeignKey(Interview, on_delete=models.CASCADE, related_name="rounds")
    round_number = models.PositiveIntegerField()
    description = models.CharField(max_length=255)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=PENDING)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["round_number"]
        unique_together = ("interview", "round_number")

    def __str__(self):
        return f"{self.interview} - round {self.round_number}"

    @property
    def badge(self):
        return BADGES[self.status]


class InterviewStatus(models.Model):
    SELECTED, NOT_SELECTED = "selected", "not-selected"
    FINAL_CHOICES = [(SELECTED, "Selected"), (NOT_SELECTED, "Not selected")]

    interview = models.OneToOneField(Interview, on_delete=models.CASCADE, related_name="status")
    final_status = models.CharField(max_length=15, choices=FINAL_CHOICES)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.interview}: {self.final_status}"

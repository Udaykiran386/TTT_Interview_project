from django import forms
from django.contrib.auth.forms import UserCreationForm

from .models import Group, GroupMembership, Interview, InterviewRound, InterviewStatus, User

INPUT = "form-control"


class Styled:
    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        for f in self.fields.values():
            f.widget.attrs.setdefault("class", INPUT)


class StudentForm(Styled, UserCreationForm):
    """Used for self-registration and for admins adding students."""
    email = forms.EmailField(required=True)

    class Meta:
        model = User
        fields = ("username", "email")

    def save(self, commit=True):
        user = super().save(commit=False)
        user.is_student = True
        user.email = self.cleaned_data["email"]
        if commit:
            user.save()
        return user


class GroupForm(Styled, forms.ModelForm):
    class Meta:
        model = Group
        fields = ("name", "description")
        widgets = {"description": forms.Textarea(attrs={"rows": 3})}

    def clean_name(self):
        name = self.cleaned_data["name"].strip()
        if len(name) < 2:
            raise forms.ValidationError("Enter at least 2 characters.")
        return name


class AddMemberForm(Styled, forms.Form):
    student = forms.ModelChoiceField(queryset=User.objects.none())

    def __init__(self, *a, group, **k):
        super().__init__(*a, **k)
        self.group = group
        self.fields["student"].queryset = User.objects.filter(is_student=True).exclude(
            memberships__group=group)

    def save(self):
        return GroupMembership.objects.create(group=self.group, student=self.cleaned_data["student"])


class InterviewForm(Styled, forms.ModelForm):
    class Meta:
        model = Interview
        fields = (
            "group", "company_name", "role", "date_of_interview",
            "hr_name", "hr_contact_number", "hr_email",
        )
        widgets = {"date_of_interview": forms.DateInput(attrs={"type": "date"})}
        labels = {
            "hr_name": "HR contact name",
            "hr_contact_number": "HR contact number",
            "hr_email": "HR email address",
        }
        help_texts = {"hr_email": "Enter the HR contact’s email address."}

    def __init__(self, *a, student, **k):
        super().__init__(*a, **k)
        self.fields["group"].queryset = Group.objects.filter(memberships__student=student)
        self.fields["group"].empty_label = "Select a group"


class RoundForm(Styled, forms.ModelForm):
    class Meta:
        model = InterviewRound
        fields = ("description",)

    def clean_description(self):
        d = self.cleaned_data["description"].strip()
        if not d:
            raise forms.ValidationError("Describe the round.")
        return d


class RoundStatusForm(forms.ModelForm):
    class Meta:
        model = InterviewRound
        fields = ("status",)


class FinalStatusForm(Styled, forms.ModelForm):
    class Meta:
        model = InterviewStatus
        fields = ("final_status",)

    def __init__(self, *a, interview, **k):
        super().__init__(*a, **k)
        self.interview = interview
        self.fields["final_status"].choices = [
            ("", "Choose a result"),
            *self.fields["final_status"].choices,
        ]

    def clean_final_status(self):
        rounds = list(self.interview.rounds.all())
        if not rounds:
            raise forms.ValidationError("Add at least one round first.")
        if any(r.status == InterviewRound.PENDING for r in rounds):
            raise forms.ValidationError("Complete all rounds before setting the final result.")
        return self.cleaned_data["final_status"]

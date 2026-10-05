from functools import wraps

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Max, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.views.decorators.http import require_POST

from .forms import (AddMemberForm, FinalStatusForm, GroupForm, InterviewForm, RoundForm,
                    RoundStatusForm, StudentForm)
from .models import (Group, GroupMembership, Interview, InterviewRound, InterviewStatus, User)


def role_required(flag):
    def deco(view):
        @wraps(view)
        def wrapper(request, *a, **k):
            if not getattr(request.user, flag):
                raise PermissionDenied
            return view(request, *a, **k)
        return login_required(wrapper)
    return deco


admin_required = role_required("is_admin")
student_required = role_required("is_student")


def dashboard_for(user):
    return "admin_dashboard" if user.is_admin else "student_dashboard"


class RoleLoginView(LoginView):
    redirect_authenticated_user = True

    def get_default_redirect_url(self):
        from django.urls import reverse
        return reverse(dashboard_for(self.request.user))


def home(request):
    return redirect(dashboard_for(request.user) if request.user.is_authenticated else "login")


def register(request):
    form = StudentForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        login(request, form.save())
        return redirect("student_dashboard")
    return render(request, "registration/register.html", {"form": form})


# ---------- Admin ----------
@admin_required
def admin_dashboard(request):
    form = StudentForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        student = form.save(commit=False)
        student.created_by = request.user
        student.save()
        messages.success(request, "Student added.")
        return redirect("admin_dashboard")
    interviews = (Interview.objects.filter(group__admin=request.user)
                  .select_related("student", "group", "status").prefetch_related("rounds"))
    students = User.objects.filter(is_student=True).filter(
        Q(memberships__group__admin=request.user) | Q(created_by=request.user)
    ).distinct()
    stats = {
        "students": students.count(),
        "groups": request.user.groups_created.count(),
        "interviews": interviews.count(),
        "selected": interviews.filter(status__final_status="selected").count(),
    }
    return render(request, "tracker/admin/dashboard.html", {
        "form": form, "stats": stats, "interviews": interviews[:20],
        "students": students.order_by("username")[:8]})


@admin_required
@require_POST
def student_delete(request, pk):
    student = get_object_or_404(
        User.objects.filter(is_student=True).filter(
            Q(memberships__group__admin=request.user) | Q(created_by=request.user)
        ).distinct(),
        pk=pk,
    )
    student.delete()
    messages.success(request, "Student removed.")
    return redirect("admin_dashboard")


@admin_required
def admin_students(request):
    students = (User.objects.filter(is_student=True).filter(
        Q(memberships__group__admin=request.user) | Q(created_by=request.user)
    ).distinct().prefetch_related("memberships__group"))
    return render(request, "tracker/admin/students.html", {"students": students})


@admin_required
def admin_student_detail(request, pk):
    student = get_object_or_404(
        User.objects.filter(is_student=True).filter(
            Q(memberships__group__admin=request.user) | Q(created_by=request.user)
        ).distinct().prefetch_related("memberships__group"),
        pk=pk,
    )
    interviews = (Interview.objects.filter(
        student=student, group__admin=request.user
    ).select_related("group", "status").prefetch_related("rounds"))
    return render(request, "tracker/admin/student_detail.html", {
        "student": student,
        "memberships": student.memberships.filter(
            group__admin=request.user).select_related("group"),
        "interviews": interviews,
    })


@admin_required
def admin_groups(request):
    form = GroupForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        group = form.save(commit=False)
        group.admin = request.user
        group.save()
        messages.success(request, "Group created.")
        return redirect("admin_group_detail", pk=group.pk)
    return render(request, "tracker/admin/groups.html", {
        "form": form, "groups": request.user.groups_created.prefetch_related("memberships")})


@admin_required
def admin_group_detail(request, pk):
    group = get_object_or_404(Group, pk=pk, admin=request.user)
    form = AddMemberForm(request.POST or None, group=group)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Student added to group.")
        return redirect("admin_group_detail", pk=pk)
    return render(request, "tracker/admin/group_detail.html", {
        "group": group, "form": form,
        "memberships": group.memberships.select_related("student"),
        "interviews": group.interviews.select_related("student", "status").prefetch_related("rounds")})


@admin_required
@require_POST
def group_delete(request, pk):
    get_object_or_404(Group, pk=pk, admin=request.user).delete()
    messages.success(request, "Group deleted.")
    return redirect("admin_groups")


@admin_required
@require_POST
def member_remove(request, pk, student_id):
    group = get_object_or_404(Group, pk=pk, admin=request.user)
    membership = get_object_or_404(GroupMembership, group=group, student_id=student_id)
    with transaction.atomic():
        removed_interviews = Interview.objects.filter(
            group=group, student_id=student_id
        ).count()
        membership.delete()
    messages.success(
        request,
        f"Student removed from group. {removed_interviews} related interview"
        f"{'' if removed_interviews == 1 else 's'} and their rounds were deleted.",
    )
    return redirect("admin_group_detail", pk=pk)


# ---------- Student ----------
def _own_interview(request, pk):
    return get_object_or_404(Interview.objects.select_related("group"), pk=pk, student=request.user)


@student_required
def student_dashboard(request):
    interviews = request.user.interviews.select_related("group", "status").prefetch_related("rounds")
    return render(request, "tracker/student/dashboard.html", {
        "groups": request.user.student_groups.all(), "interviews": interviews[:5],
        "total": interviews.count(),
        "selected": interviews.filter(status__final_status="selected").count(),
        "in_progress": interviews.filter(status__isnull=True).count()})


@student_required
def student_interviews(request):
    form = InterviewForm(request.POST or None, student=request.user)
    if request.method == "POST" and form.is_valid():
        iv = form.save(commit=False)
        iv.student = request.user
        iv.save()
        messages.success(request, "Interview added. Now add its rounds.")
        return redirect("student_interview_detail", pk=iv.pk)
    return render(request, "tracker/student/interviews.html", {
        "form": form,
        "interviews": request.user.interviews.select_related("group", "status").prefetch_related("rounds")})


@student_required
def student_interview_detail(request, pk):
    iv = _own_interview(request, pk)
    return render(request, "tracker/student/interview_detail.html", {
        "iv": iv, "round_form": RoundForm(),
        "status_form": FinalStatusForm(instance=getattr(iv, "status", None), interview=iv),
        "round_choices": InterviewRound.STATUS_CHOICES})


@student_required
@require_POST
def interview_status(request, pk):
    iv = _own_interview(request, pk)
    form = FinalStatusForm(request.POST, instance=getattr(iv, "status", None), interview=iv)
    if form.is_valid():
        obj = form.save(commit=False)
        obj.interview = iv
        obj.save()
        messages.success(request, "Final result saved.")
    else:
        for err in form.errors.values():
            messages.error(request, " ".join(err))
    return redirect("student_interview_detail", pk=pk)


@student_required
@require_POST
def interview_delete(request, pk):
    _own_interview(request, pk).delete()
    messages.success(request, "Interview deleted.")
    return redirect("student_interviews")


@student_required
@require_POST
def round_add(request, pk):
    """AJAX: CSRF-protected via the X-CSRFToken header."""
    iv = _own_interview(request, pk)
    form = RoundForm(request.POST)
    if not form.is_valid():
        return JsonResponse({"errors": form.errors.get_json_data()}, status=400)
    with transaction.atomic():
        nxt = (iv.rounds.aggregate(m=Max("round_number"))["m"] or 0) + 1
        rnd = InterviewRound.objects.create(
            interview=iv, round_number=nxt, description=form.cleaned_data["description"])
        InterviewStatus.objects.filter(interview=iv).delete()  # new round reopens the interview
    html = render_to_string("tracker/student/_round_row.html", {
        "r": rnd, "round_choices": InterviewRound.STATUS_CHOICES}, request=request)
    return JsonResponse({"html": html}, status=201)


@student_required
@require_POST
def round_update(request, pk):
    rnd = get_object_or_404(InterviewRound, pk=pk, interview__student=request.user)
    form = RoundStatusForm(request.POST, instance=rnd)
    if not form.is_valid():
        return JsonResponse({"errors": form.errors.get_json_data()}, status=400)
    form.save()
    if rnd.interview.rounds.filter(status=InterviewRound.PENDING).exists():
        InterviewStatus.objects.filter(interview=rnd.interview).delete()
    return JsonResponse({
        "status": rnd.status,
        "badge": rnd.badge,
        "final_status": rnd.interview.final_status,
        "final_label": rnd.interview.final_label,
    })

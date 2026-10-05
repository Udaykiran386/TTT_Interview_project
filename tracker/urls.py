from django.contrib.auth.views import LogoutView
from django.urls import path

from . import views as v

urlpatterns = [
    path("", v.home, name="home"),
    path("register/", v.register, name="register"),
    path("login/", v.RoleLoginView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),

    path("admin/dashboard/", v.admin_dashboard, name="admin_dashboard"),
    path("admin/students/", v.admin_students, name="admin_students"),
    path("admin/students/<int:pk>/", v.admin_student_detail, name="admin_student_detail"),
    path("admin/students/<int:pk>/delete/", v.student_delete, name="student_delete"),
    path("admin/groups/", v.admin_groups, name="admin_groups"),
    path("admin/groups/<int:pk>/", v.admin_group_detail, name="admin_group_detail"),
    path("admin/groups/<int:pk>/delete/", v.group_delete, name="group_delete"),
    path("admin/groups/<int:pk>/members/<int:student_id>/remove/", v.member_remove, name="member_remove"),

    path("student/dashboard/", v.student_dashboard, name="student_dashboard"),
    path("student/interviews/", v.student_interviews, name="student_interviews"),
    path("student/interviews/<int:pk>/", v.student_interview_detail, name="student_interview_detail"),
    path("student/interviews/<int:pk>/status/", v.interview_status, name="interview_status"),
    path("student/interviews/<int:pk>/delete/", v.interview_delete, name="interview_delete"),
    path("student/interviews/<int:pk>/rounds/add/", v.round_add, name="round_add"),
    path("student/rounds/<int:pk>/update/", v.round_update, name="round_update"),
]

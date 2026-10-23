from django.urls import path

from . import admin_manage, views

urlpatterns = [
    path("", views.home, name="home"),
    path("register/", views.register, name="register"),
    path("login/", views.student_login, name="student_login"),
    path("admin-login/", views.admin_login, name="admin_login"),
    path("verify-otp/", views.verify_otp, name="verify_otp"),
    path("resend-otp/", views.resend_otp, name="resend_otp"),
    path("logout/", views.logout_view, name="logout"),

    # student
    path("student/", views.student_dashboard, name="student_dashboard"),
    path("exam/start/", views.start_exam, name="start_exam"),
    path("exam/<int:pk>/", views.exam, name="exam"),
    path("exam/<int:pk>/save/", views.save_answer, name="save_answer"),
    path("exam/<int:pk>/submit/", views.submit_exam, name="submit_exam"),
    path("exam/<int:pk>/violation/", views.tab_violation, name="tab_violation"),
    path("result/<int:pk>/", views.result, name="result"),

    # admin panel
    path("panel/", views.admin_dashboard, name="admin_dashboard"),
    path("panel/candidates/", views.admin_candidates, name="admin_candidates"),
    path("panel/candidates/<int:pk>/", views.admin_candidate_edit, name="admin_candidate_edit"),
    path("panel/results/", views.admin_results, name="admin_results"),
    path("panel/results/export/", views.export_results, name="export_results"),
    path("panel/results/<int:pk>/", views.admin_attempt, name="admin_attempt"),
    path("panel/questions/", views.admin_questions, name="admin_questions"),
    path("panel/questions/new/", views.admin_question_edit, name="admin_question_new"),
    path("panel/questions/<int:pk>/", views.admin_question_edit, name="admin_question_edit"),
    path("panel/questions/<int:pk>/toggle/", views.admin_question_toggle, name="admin_question_toggle"),
    path("panel/questions/import/", views.admin_import, name="admin_import"),
    path("panel/questions/template.csv", views.import_template, name="import_template"),
    path("panel/settings/", views.admin_settings, name="admin_settings"),
    path("panel/admins/", admin_manage.admin_users, name="admin_users"),
    path("panel/admins/<int:pk>/", admin_manage.admin_user_edit, name="admin_user_edit"),
    path("panel/admins/<int:pk>/delete/", admin_manage.admin_user_delete, name="admin_user_delete"),
    path("panel/reports/", views.admin_reports, name="admin_reports"),
    path("panel/reports/<int:pk>/retry/", views.admin_report_retry, name="admin_report_retry"),
    path("panel/audit/", views.admin_audit, name="admin_audit"),
]

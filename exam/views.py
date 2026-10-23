import csv
import logging
from datetime import date, timedelta
from functools import wraps

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from . import services
from .forms import (ImportForm, LoginForm, OTPForm, QuestionForm, RegisterForm, SettingForm,
                    StudentEditForm, StudentLoginForm)
from .importer import FIELDS, import_csv
from .models import (LEVELS, SKILLS, AssessmentSetting, Attempt, AttemptAnswer, AuditLog, Question,
                     ReportLog, Student)


logger = logging.getLogger(__name__)


# ------------------------------------------------------------ access control
def student_required(view):
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        u = request.user
        if not u.is_authenticated:
            return redirect(f"{reverse('student_login')}?next={request.path}")
        if u.is_staff:
            return redirect("admin_dashboard")
        try:
            request.student = u.student
        except Student.DoesNotExist:
            logout(request)
            return redirect("student_login")
        return view(request, *args, **kwargs)
    return wrapper


def admin_required(view):
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        u = request.user
        if not u.is_authenticated:
            return redirect("admin_login")
        if not u.is_staff:
            raise PermissionDenied
        return view(request, *args, **kwargs)
    return wrapper


# ------------------------------------------------------------ public pages
def home(request):
    cfg = AssessmentSetting.get()
    return render(request, "exam/home.html", {"cfg": cfg})


def _register_otp_page(request, user, error=""):
    return render(request, "exam/register.html", {"otp_stage": True, "email": user.email, "code_error": error})


def register(request):
    if request.user.is_authenticated:
        return redirect("student_dashboard" if not request.user.is_staff else "admin_dashboard")

    # Step 1: registration form
    form = RegisterForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        d = form.cleaned_data
        with transaction.atomic():
            user = User.objects.create_user(username=d["email"], email=d["email"], password=None,
                                            first_name=d["full_name"].strip())
            student = Student.objects.create(user=user, phone=d["phone"], reference_id=d["reference_id"])
            services.audit(user, "student_registered", student.roll_number or "")
        messages.success(request, f"Registration successful. Your roll number is {student.roll_number}. Please log in with your email.")
        return redirect("student_login")
    return render(request, "exam/register.html", {"form": form})


def _begin_login(request, user, role):
    if settings.OTP_ENABLED and role != "admin":
        try:
            services.issue_otp(user)
        except Exception:
            messages.error(request, "Could not send the verification email. Please try again.")
            return redirect("admin_login" if role == "admin" else "student_login")
        request.session["pending_uid"] = user.pk
        request.session["pending_role"] = role
        request.session["pending_next"] = request.GET.get("next", "")
        return redirect("verify_otp")
    return _finish_login(request, user, role, request.GET.get("next", ""))


ALREADY_USED_MSG = ("This email has already been used to log in. Each registered email can be used only once - "
                    "please register again with a new email.")


def _finish_login(request, user, role, nxt=""):
    if role == "student":
        # one login per email: atomically mark it used (email_verified=True means "already logged in once")
        claimed = Student.objects.filter(user=user, email_verified=False).update(email_verified=True)
        if not claimed:
            messages.error(request, ALREADY_USED_MSG)
            return redirect("register")
    login(request, user)
    services.audit(user, f"{role}_login")
    if nxt and nxt.startswith("/") and not nxt.startswith("//"):
        return redirect(nxt)
    return redirect("admin_dashboard" if role == "admin" else "student_dashboard")


def _student_login(request):
    """Student login with registered email only (no password / OTP)."""
    form = StudentLoginForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        email = form.cleaned_data["email"].strip().lower()
        user = User.objects.filter(username=email, is_staff=False).first()
        if user is None or not Student.objects.filter(user=user).exists():
            form.add_error("email", "No account found with this email. Please register first.")
        elif not user.is_active:
            form.add_error("email", "This account is disabled. Please contact the administrator.")
        elif user.student.email_verified:
            form.add_error("email", ALREADY_USED_MSG)
        else:
            user.backend = "django.contrib.auth.backends.ModelBackend"
            return _finish_login(request, user, "student", request.GET.get("next", ""))
    return render(request, "exam/login.html", {"form": form, "role": "student"})


def _login_view(request, role):
    if request.user.is_authenticated:
        return redirect("admin_dashboard" if request.user.is_staff else "student_dashboard")
    if role == "student":
        return _student_login(request)
    form = LoginForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        email = form.cleaned_data["email"].lower()
        user = authenticate(request, username=email, password=form.cleaned_data["password"])
        if user is None:
            form.add_error(None, "Invalid email or password.")
        elif role == "admin" and not user.is_staff:
            form.add_error(None, "This account is not an administrator.")
        elif role == "student" and user.is_staff:
            form.add_error(None, "Administrators must use the Admin Login page.")
        else:
            return _begin_login(request, user, role)
    return render(request, "exam/login.html", {"form": form, "role": role})


def student_login(request):
    return _login_view(request, "student")


def admin_login(request):
    return _login_view(request, "admin")


def verify_otp(request):
    uid = request.session.get("pending_uid")
    if not uid:
        return redirect("student_login")
    user = get_object_or_404(User, pk=uid)
    role = request.session.get("pending_role", "student")
    form = OTPForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        if services.check_otp(user, form.cleaned_data["code"]):
            nxt = request.session.get("pending_next", "")
            for k in ("pending_uid", "pending_role", "pending_next"):
                request.session.pop(k, None)
            return _finish_login(request, user, role, nxt)
        form.add_error("code", "Incorrect or expired code.")
    return render(request, "exam/verify_otp.html", {"form": form, "email": user.email, "role": role,
                                                    "dev_mode": not settings.EMAIL_HOST_USER})


@require_POST
def resend_otp(request):
    uid = request.session.get("pending_uid")
    if not uid:
        return redirect("student_login")
    user = get_object_or_404(User, pk=uid)
    last = user.otps.order_by("-created_at").first()
    if last and timezone.now() - last.created_at < timedelta(seconds=60):
        messages.warning(request, "Please wait a minute before requesting another code.")
    else:
        services.issue_otp(user)
        messages.success(request, "A new code has been sent.")
    return redirect("verify_otp")


@require_POST
def logout_view(request):
    logout(request)
    return redirect("home")


# ------------------------------------------------------------ student area
@student_required
def student_dashboard(request):
    cfg = AssessmentSetting.get()
    attempts = request.student.attempts.all()
    running = attempts.filter(status="in_progress").first()
    can_start = bool(running) or attempts.count() < cfg.max_attempts
    return render(request, "exam/student_dashboard.html", {
        "student": request.student, "attempts": attempts, "running": running,
        "can_start": can_start, "cfg": cfg})


@student_required
@require_POST
def start_exam(request):
    try:
        attempt = services.start_attempt(request.student)
    except services.NotEnoughQuestions as exc:
        messages.error(request, f"The question bank is not ready: {exc} Please contact the administrator.")
        return redirect("student_dashboard")
    if attempt is None:
        messages.error(request, "You have used all your attempts.")
        return redirect("student_dashboard")
    return redirect("exam", pk=attempt.pk)


def _own_attempt(request, pk):
    return get_object_or_404(Attempt, pk=pk, student=request.student)


@student_required
def exam(request, pk):
    attempt = _own_attempt(request, pk)
    if attempt.status == "submitted":
        return redirect("result", pk=attempt.pk)
    remaining = None
    if attempt.deadline:
        remaining = max(0, int((attempt.deadline - timezone.now()).total_seconds()))
    sections = services.exam_sections(attempt)
    answered = attempt.answers.exclude(selected="").count()
    return render(request, "exam/exam.html", {
        "attempt": attempt, "sections": sections, "remaining": remaining,
        "answered": answered, "total": attempt.answers.count()})


@student_required
@require_POST
def save_answer(request, pk):
    attempt = _own_attempt(request, pk)
    if attempt.status != "in_progress":
        return JsonResponse({"ok": False, "error": "submitted"}, status=409)
    if attempt.deadline and timezone.now() > attempt.deadline + timedelta(seconds=60):
        return JsonResponse({"ok": False, "error": "time over"}, status=409)
    choice = request.POST.get("choice", "")
    if choice not in ("A", "B", "C", "D"):
        return JsonResponse({"ok": False}, status=400)
    updated = AttemptAnswer.objects.filter(attempt=attempt, pk=request.POST.get("aid")).update(selected=choice)
    if not updated:
        return JsonResponse({"ok": False}, status=404)
    return JsonResponse({"ok": True, "answered": attempt.answers.exclude(selected="").count()})


@student_required
@require_POST
def submit_exam(request, pk):
    attempt = _own_attempt(request, pk)
    attempt = services.grade_attempt(attempt)
    if not attempt.reports.exists():
        services.send_report(attempt)
    messages.success(request, f"Exam submitted successfully. Your roll number is {attempt.student.roll_number}.")
    return redirect("result", pk=attempt.pk)


@student_required
@require_POST
def tab_violation(request, pk):
    """Called when the candidate leaves the exam tab. 1st time = warning, 2nd time = auto submit."""
    with transaction.atomic():
        attempt = Attempt.objects.select_for_update().get(pk=_own_attempt(request, pk).pk)
        if attempt.status == "submitted":
            return JsonResponse({"action": "submitted", "redirect": reverse("result", args=[attempt.pk])})
        attempt.tab_switches += 1
        final = attempt.tab_switches >= 2
        if final:
            attempt.auto_submitted = True
        attempt.save(update_fields=["tab_switches", "auto_submitted"])
        services.audit(request.user, "tab_switch", f"attempt {attempt.pk}: count {attempt.tab_switches}")
    if final:
        attempt = services.grade_attempt(attempt)
        if not attempt.reports.exists():
            services.send_report(attempt)
        messages.success(request, f"Exam submitted successfully. Your roll number is {attempt.student.roll_number}.")
        return JsonResponse({"action": "submit", "redirect": reverse("result", args=[attempt.pk])})
    return JsonResponse({"action": "warn", "count": attempt.tab_switches})


@student_required
def result(request, pk):
    attempt = _own_attempt(request, pk)
    if attempt.status != "submitted":
        return redirect("exam", pk=attempt.pk)
    return render(request, "exam/result.html", {
        "attempt": attempt, "summary": services.result_summary(attempt), "cfg": AssessmentSetting.get()})


# ------------------------------------------------------------ admin panel
REGISTRATION_CYCLE_DAYS = 30


def _registration_cycle():
    """Rolling 30-day cycle for the 'Registered candidates' counter.

    The cycle starts at the first candidate's registration time. After every
    30 days the counter goes back to zero and starts counting again from the
    beginning of the new cycle. No data is deleted and no new column is needed
    (Student.created_at is used).
    Returns (count, cycle_start, cycle_end).
    """
    first = Student.objects.order_by("created_at").values_list("created_at", flat=True).first()
    if first is None:
        return 0, None, None
    length = timedelta(days=REGISTRATION_CYCLE_DAYS)
    elapsed_cycles = (timezone.now() - first) // length      # full 30-day blocks passed
    start = first + elapsed_cycles * length
    end = start + length
    count = Student.objects.filter(created_at__gte=start, created_at__lt=end).count()
    return count, start, end


@admin_required
def admin_dashboard(request):
    done = Attempt.objects.filter(status="submitted")
    passed = done.filter(result="PASS").count()
    failed = done.filter(result="FAIL").count()
    total_done = passed + failed
    reg_count, reg_start, reg_end = _registration_cycle()
    ctx = {
        "registered": reg_count, "reg_start": reg_start, "reg_end": reg_end,
        "completed": total_done, "passed": passed, "failed": failed,
        "pass_pct": round(passed * 100 / total_done, 1) if total_done else 0,
        "in_progress": Attempt.objects.filter(status="in_progress").count(),
        "recent": done.select_related("student__user")[:8],
        "bank": Question.objects.filter(active=True).count(),
        "failed_reports": ReportLog.objects.exclude(delivery_status="sent").count(),
    }
    return render(request, "exam/admin_dashboard.html", ctx)


CANDIDATE_PERIODS = [("", "All time"), ("1y", "Last 1 year"), ("6m", "Last 6 months"), ("3m", "Last 3 months"),
                     ("1m", "Last 1 month"), ("2w", "Last 2 weeks"), ("1w", "Last 1 week")]
_PERIOD_DAYS = {"1y": 365, "6m": 182, "3m": 91, "1m": 30, "2w": 14, "1w": 7}


@admin_required
def admin_candidates(request):
    q = request.GET.get("q", "").strip()
    period = request.GET.get("period", "")
    qs = Student.objects.select_related("user").annotate(n_attempts=Count("attempts"))
    if q:
        qs = qs.filter(Q(user__first_name__icontains=q) | Q(user__email__icontains=q) |
                       Q(roll_number__icontains=q) | Q(phone__icontains=q))
    if period in _PERIOD_DAYS:  # filter by registration date
        qs = qs.filter(created_at__gte=timezone.now() - timedelta(days=_PERIOD_DAYS[period]))
    else:
        period = ""
    page = Paginator(qs.order_by("roll_number"), 25).get_page(request.GET.get("page"))
    params = "&".join(p for p in (f"q={q}" if q else "", f"period={period}" if period else "") if p)
    return render(request, "exam/admin_candidates.html", {
        "page": page, "q": q, "period": period, "periods": CANDIDATE_PERIODS, "params": params})


@admin_required
def admin_candidate_edit(request, pk):
    student = get_object_or_404(Student.objects.select_related("user"), pk=pk)
    form = StudentEditForm(request.POST or None, initial={
        "full_name": student.user.first_name, "phone": student.phone,
        "reference_id": student.reference_id, "is_active": student.user.is_active})
    if request.method == "POST" and form.is_valid():
        d = form.cleaned_data
        student.user.first_name, student.user.is_active = d["full_name"], d["is_active"]
        student.user.save()
        student.phone, student.reference_id = d["phone"], d["reference_id"]
        student.save()
        services.audit(request.user, "student_edited", f"{student.roll_number}")
        messages.success(request, "Candidate updated.")
        return redirect("admin_candidates")
    return render(request, "exam/admin_candidate_edit.html", {
        "form": form, "student": student, "attempts": student.attempts.all()})


def _filtered_results(request):
    qs = Attempt.objects.filter(status="submitted").select_related("student__user")
    g = request.GET
    if g.get("q"):
        q = g["q"].strip()
        qs = qs.filter(Q(student__user__first_name__icontains=q) | Q(student__user__email__icontains=q) |
                       Q(student__roll_number__icontains=q))
    if g.get("result") in ("PASS", "FAIL"):
        qs = qs.filter(result=g["result"])
    for key, lookup in (("date_from", "submitted_at__date__gte"), ("date_to", "submitted_at__date__lte")):
        try:
            if g.get(key):
                qs = qs.filter(**{lookup: date.fromisoformat(g[key])})
        except ValueError:
            pass
    for key, field in (("min_total", "total_score__gte"), ("min_sql", "sql_score__gte"),
                       ("min_python", "python_score__gte")):
        if g.get(key, "").isdigit():
            qs = qs.filter(**{field: int(g[key])})
    return qs


@admin_required
def admin_results(request):
    qs = _filtered_results(request)
    page = Paginator(qs, 25).get_page(request.GET.get("page"))
    params = request.GET.copy()
    params.pop("page", None)
    return render(request, "exam/admin_results.html", {"page": page, "params": params.urlencode(), "g": request.GET})


@admin_required
def export_results(request):
    resp = HttpResponse(content_type="text/csv; charset=utf-8")
    resp["Content-Disposition"] = 'attachment; filename="assessment_results.csv"'
    resp.write("\ufeff")  # BOM so Excel opens UTF-8 correctly
    w = csv.writer(resp)
    w.writerow(["Attempt ID", "Roll No", "Name", "Email", "Phone", "Submitted", "SQL", "SQL max", "Python",
                "Python max", "Overall", "Overall max", "Percentage", "Result"])
    for a in _filtered_results(request):
        s = a.student
        w.writerow([a.pk, s.roll_number, s.name, s.email, s.phone,
                    timezone.localtime(a.submitted_at).strftime("%Y-%m-%d %H:%M"), a.sql_score, a.sql_max,
                    a.python_score, a.python_max, a.total_score, a.total_max, a.percentage, a.result])
    services.audit(request.user, "results_exported")
    return resp


@admin_required
def export_results_xlsx(request):
    """Excel export in DB-table style: one row per (student attempt x question number)."""
    data = services.build_results_workbook(_filtered_results(request))
    resp = HttpResponse(data, content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    resp["Content-Disposition"] = 'attachment; filename="assessment_results.xlsx"'
    services.audit(request.user, "results_exported_xlsx")
    return resp


@admin_required
def admin_attempt(request, pk):
    attempt = get_object_or_404(Attempt.objects.select_related("student__user"), pk=pk)
    review = []
    if attempt.status == "submitted":
        for a in attempt.answers.select_related("question"):
            q = a.question
            review.append({"a": a, "q": q,
                           "chosen": q.option_text(a.selected) if a.selected else "(not answered)",
                           "correct": q.option_text(q.answer_key)})
    return render(request, "exam/admin_attempt.html", {
        "attempt": attempt, "summary": services.result_summary(attempt), "review": review})


@admin_required
def admin_questions(request):
    qs = Question.objects.all()
    g = request.GET
    if g.get("skill") in ("sql", "python"):
        qs = qs.filter(skill=g["skill"])
    if g.get("difficulty") in ("easy", "intermediate", "advanced"):
        qs = qs.filter(difficulty=g["difficulty"])
    if g.get("status") in ("active", "archived"):
        qs = qs.filter(active=g["status"] == "active")
    if g.get("q"):
        qs = qs.filter(prompt__icontains=g["q"].strip())
    page = Paginator(qs, 25).get_page(g.get("page"))
    params = g.copy()
    params.pop("page", None)
    counts = {(r["skill"], r["difficulty"]): r["n"] for r in
              Question.objects.filter(active=True).values("skill", "difficulty").annotate(n=Count("id"))}
    matrix = [{"skill": lbl, "cells": [counts.get((s, l), 0) for l, _ in LEVELS]} for s, lbl in SKILLS]
    return render(request, "exam/admin_questions.html", {
        "page": page, "g": g, "params": params.urlencode(), "matrix": matrix, "levels": LEVELS})


@admin_required
def admin_question_edit(request, pk=None):
    obj = get_object_or_404(Question, pk=pk) if pk else None
    form = QuestionForm(request.POST or None, instance=obj)
    if request.method == "POST" and form.is_valid():
        q = form.save()
        services.audit(request.user, "question_saved", f"question {q.pk}")
        messages.success(request, "Question saved.")
        return redirect("admin_questions")
    return render(request, "exam/admin_question_form.html", {"form": form, "obj": obj})


@admin_required
@require_POST
def admin_question_toggle(request, pk):
    q = get_object_or_404(Question, pk=pk)
    q.active = not q.active
    q.save(update_fields=["active"])
    services.audit(request.user, "question_archived" if not q.active else "question_restored", f"question {pk}")
    return redirect("admin_questions")


@admin_required
def admin_import(request):
    form = ImportForm(request.POST or None, request.FILES or None)
    result_info = None
    if request.method == "POST" and form.is_valid():
        created, skipped, errors = import_csv(form.cleaned_data["file"])
        services.audit(request.user, "questions_imported", f"created {created}, skipped {skipped}, errors {len(errors)}")
        result_info = {"created": created, "skipped": skipped, "errors": errors[:50], "n_errors": len(errors)}
    return render(request, "exam/admin_import.html", {"form": form, "info": result_info})


@admin_required
def import_template(request):
    resp = HttpResponse(content_type="text/csv; charset=utf-8")
    resp["Content-Disposition"] = 'attachment; filename="question_template.csv"'
    w = csv.writer(resp)
    w.writerow(FIELDS)
    w.writerow(["sql", "easy", "Basics", "What does SQL stand for?", "Structured Query Language",
                "Simple Query Logic", "Sequential Question Language", "Standard Quick Language", "A", "", 1, 1])
    return resp


@admin_required
def admin_settings(request):
    form = SettingForm(request.POST or None, instance=AssessmentSetting.get())
    if request.method == "POST" and form.is_valid():
        form.save()
        services.audit(request.user, "settings_changed", str(form.cleaned_data))
        messages.success(request, "Settings saved.")
        return redirect("admin_settings")
    return render(request, "exam/admin_settings.html", {"form": form})


@admin_required
def admin_reports(request):
    page = Paginator(ReportLog.objects.select_related("attempt__student__user"), 25).get_page(request.GET.get("page"))
    return render(request, "exam/admin_reports.html", {"page": page})


@admin_required
@require_POST
def admin_report_retry(request, pk):
    log = get_object_or_404(ReportLog, pk=pk)
    services.send_report(log.attempt, log)
    messages.info(request, f"Report status: {log.delivery_status}")
    return redirect("admin_reports")


@admin_required
def admin_audit(request):
    page = Paginator(AuditLog.objects.select_related("actor"), 50).get_page(request.GET.get("page"))
    return render(request, "exam/admin_audit.html", {"page": page})
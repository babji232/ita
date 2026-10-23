from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone

SKILLS = [("sql", "SQL"), ("python", "Python")]
LEVELS = [("easy", "Easy"), ("intermediate", "Intermediate"), ("advanced", "Advanced")]


class Student(models.Model):
    """Candidate profile (linked to Django auth user; username = email)."""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="student")
    roll_number = models.CharField(max_length=20, unique=True, null=True, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    reference_id = models.CharField("Application / reference ID", max_length=50, blank=True)
    email_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if not self.roll_number:
            self.roll_number = f"ITA{self.pk:05d}"
            super().save(update_fields=["roll_number"])

    @property
    def name(self):
        return self.user.first_name or self.user.email

    @property
    def email(self):
        return self.user.email

    def __str__(self):
        return f"{self.roll_number} - {self.name}"


class AssessmentSetting(models.Model):
    """Single-row admin configuration."""
    PASS_MODES = [
        ("overall", "Pass % applied to overall score"),
        ("each_skill", "Pass % required in each skill (SQL and Python)"),
    ]
    pass_mode = models.CharField(max_length=20, choices=PASS_MODES, default="overall")
    pass_percentage = models.PositiveSmallIntegerField(default=50)
    time_limit_minutes = models.PositiveSmallIntegerField(default=90, help_text="0 = no time limit")
    max_attempts = models.PositiveSmallIntegerField(default=1, help_text="Attempts allowed per candidate")
    questions_per_section = models.PositiveSmallIntegerField(default=10)
    report_recipient = models.EmailField(default="admin@itaassociates.co.uk")

    @classmethod
    def get(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def __str__(self):
        return "Assessment settings"


class Question(models.Model):
    skill = models.CharField(max_length=10, choices=SKILLS)
    difficulty = models.CharField(max_length=15, choices=LEVELS)
    topic = models.CharField(max_length=100, blank=True)
    prompt = models.TextField()
    option_a = models.CharField(max_length=500)
    option_b = models.CharField(max_length=500)
    option_c = models.CharField(max_length=500)
    option_d = models.CharField(max_length=500)
    answer_key = models.CharField(max_length=1, choices=[("A", "A"), ("B", "B"), ("C", "C"), ("D", "D")])
    explanation = models.TextField(blank=True)
    marks = models.PositiveSmallIntegerField(default=1)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["skill", "difficulty", "id"]
        indexes = [models.Index(fields=["skill", "difficulty", "active"])]

    def option_text(self, letter):
        return getattr(self, f"option_{letter.lower()}")

    def __str__(self):
        return f"[{self.skill}/{self.difficulty}] {self.prompt[:60]}"


class Attempt(models.Model):
    STATUS = [("in_progress", "In progress"), ("submitted", "Submitted")]
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="attempts")
    started_at = models.DateTimeField(default=timezone.now)
    deadline = models.DateTimeField(null=True, blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=15, choices=STATUS, default="in_progress")
    sql_score = models.PositiveSmallIntegerField(default=0)
    sql_max = models.PositiveSmallIntegerField(default=0)
    python_score = models.PositiveSmallIntegerField(default=0)
    python_max = models.PositiveSmallIntegerField(default=0)
    total_score = models.PositiveSmallIntegerField(default=0)
    total_max = models.PositiveSmallIntegerField(default=0)
    percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    result = models.CharField(max_length=4, blank=True)  # PASS / FAIL
    breakdown = models.JSONField(default=dict, blank=True)
    tab_switches = models.PositiveSmallIntegerField(default=0)
    auto_submitted = models.BooleanField(default=False)

    class Meta:
        ordering = ["-started_at"]

    @property
    def sql_pct(self):
        return round(self.sql_score * 100 / self.sql_max, 1) if self.sql_max else 0

    @property
    def python_pct(self):
        return round(self.python_score * 100 / self.python_max, 1) if self.python_max else 0

    def __str__(self):
        return f"Attempt #{self.pk} - {self.student}"


class AttemptAnswer(models.Model):
    attempt = models.ForeignKey(Attempt, on_delete=models.CASCADE, related_name="answers")
    question = models.ForeignKey(Question, on_delete=models.PROTECT, related_name="+")
    position = models.PositiveSmallIntegerField()
    option_order = models.CharField(max_length=4)  # e.g. "CABD" = shuffled display order
    selected = models.CharField(max_length=1, blank=True)  # original letter A-D
    is_correct = models.BooleanField(default=False)
    marks_awarded = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["position"]
        constraints = [models.UniqueConstraint(fields=["attempt", "question"], name="uniq_attempt_question")]


class ReportLog(models.Model):
    STATUS = [("pending", "Pending"), ("sent", "Sent"), ("failed", "Failed")]
    attempt = models.ForeignKey(Attempt, on_delete=models.CASCADE, related_name="reports")
    recipient = models.EmailField()
    delivery_status = models.CharField(max_length=10, choices=STATUS, default="pending")
    error = models.TextField(blank=True)
    retries = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]


class EmailOTP(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="otps")
    code_hash = models.CharField(max_length=64)
    created_at = models.DateTimeField(default=timezone.now)
    tries = models.PositiveSmallIntegerField(default=0)
    used = models.BooleanField(default=False)


class AuditLog(models.Model):
    actor = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)
    action = models.CharField(max_length=100)
    details = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

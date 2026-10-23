from django.contrib import admin

from .models import (AssessmentSetting, Attempt, AttemptAnswer, AuditLog, Question, ReportLog, Student)

admin.site.register([Student, AssessmentSetting, Attempt, AttemptAnswer, ReportLog, AuditLog])


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ("id", "skill", "difficulty", "prompt", "answer_key", "active")
    list_filter = ("skill", "difficulty", "active")
    search_fields = ("prompt",)

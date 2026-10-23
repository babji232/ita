from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password

from .models import AssessmentSetting, Question


class RegisterForm(forms.Form):
    full_name = forms.CharField(max_length=150)
    email = forms.EmailField()
    phone = forms.CharField(max_length=20, required=False)
    reference_id = forms.CharField(max_length=50, required=False, label="Application / reference ID (optional)")
    accept_privacy = forms.BooleanField(label="I have read and accept the privacy notice")

    def clean_email(self):
        email = self.cleaned_data["email"].lower()
        if User.objects.filter(username=email).exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email


class LoginForm(forms.Form):
    email = forms.EmailField()
    password = forms.CharField(widget=forms.PasswordInput)


class StudentLoginForm(forms.Form):
    email = forms.EmailField()


class OTPForm(forms.Form):
    code = forms.CharField(max_length=6, min_length=6, label="6-digit code")


class StudentEditForm(forms.Form):
    full_name = forms.CharField(max_length=150)
    phone = forms.CharField(max_length=20, required=False)
    reference_id = forms.CharField(max_length=50, required=False)
    is_active = forms.BooleanField(required=False, label="Account active")


class QuestionForm(forms.ModelForm):
    class Meta:
        model = Question
        fields = ["skill", "difficulty", "topic", "prompt", "option_a", "option_b", "option_c", "option_d",
                  "answer_key", "explanation", "marks", "active"]
        widgets = {"prompt": forms.Textarea(attrs={"rows": 3}), "explanation": forms.Textarea(attrs={"rows": 2})}


class ImportForm(forms.Form):
    file = forms.FileField(label="CSV file")

    def clean_file(self):
        f = self.cleaned_data["file"]
        if not f.name.lower().endswith(".csv"):
            raise forms.ValidationError("Upload a .csv file.")
        if f.size > 5 * 1024 * 1024:
            raise forms.ValidationError("File too large (max 5 MB).")
        return f


class SettingForm(forms.ModelForm):
    class Meta:
        model = AssessmentSetting
        fields = ["pass_mode", "pass_percentage", "time_limit_minutes", "max_attempts",
                  "questions_per_section", "report_recipient"]

    def clean_pass_percentage(self):
        v = self.cleaned_data["pass_percentage"]
        if not 1 <= v <= 100:
            raise forms.ValidationError("Enter a value between 1 and 100.")
        return v

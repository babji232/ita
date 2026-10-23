"""Admin management: add / edit / delete administrators.

Admins are stored in the database table `auth_user` (is_staff=True), the same table the
admin login already authenticates against, so every admin added here can log in immediately.
"""
from django import forms
from django.contrib import messages
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from . import services
from .views import admin_required


def _admins():
    return User.objects.filter(is_staff=True).order_by("id")


class AdminCreateForm(forms.Form):
    full_name = forms.CharField(max_length=150)
    email = forms.EmailField()
    password1 = forms.CharField(widget=forms.PasswordInput, label="Password")
    password2 = forms.CharField(widget=forms.PasswordInput, label="Confirm password")

    def clean_email(self):
        email = self.cleaned_data["email"].lower()
        if User.objects.filter(username=email).exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email

    def clean(self):
        data = super().clean()
        p1, p2 = data.get("password1"), data.get("password2")
        if p1 and p2:
            if p1 != p2:
                self.add_error("password2", "Passwords do not match.")
            else:
                try:
                    validate_password(p1)
                except forms.ValidationError as e:
                    self.add_error("password1", e)
        return data


class AdminEditForm(forms.Form):
    full_name = forms.CharField(max_length=150)
    email = forms.EmailField()
    is_active = forms.BooleanField(required=False, label="Account active")
    password1 = forms.CharField(widget=forms.PasswordInput, required=False, label="New password (leave blank to keep)")
    password2 = forms.CharField(widget=forms.PasswordInput, required=False, label="Confirm new password")

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user_obj = user

    def clean_email(self):
        email = self.cleaned_data["email"].lower()
        if User.objects.filter(username=email).exclude(pk=self.user_obj.pk).exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email

    def clean(self):
        data = super().clean()
        p1, p2 = data.get("password1"), data.get("password2")
        if p1 or p2:
            if p1 != p2:
                self.add_error("password2", "Passwords do not match.")
            else:
                try:
                    validate_password(p1, self.user_obj)
                except forms.ValidationError as e:
                    self.add_error("password1", e)
        return data


def _render(request, form, editing=None):
    return render(request, "exam/admin_users.html", {"admins": _admins(), "form": form, "editing": editing})


@admin_required
def admin_users(request):
    """List all admins (database table) + add-admin form beside it."""
    form = AdminCreateForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        d = form.cleaned_data
        user = User.objects.create_user(username=d["email"], email=d["email"], password=d["password1"],
                                        first_name=d["full_name"].strip())
        user.is_staff = True
        user.save()
        services.audit(request.user, "admin_added", user.email)
        messages.success(request, f"Admin {user.email} added.")
        return redirect("admin_users")
    return _render(request, form)


@admin_required
def admin_user_edit(request, pk):
    target = get_object_or_404(_admins(), pk=pk)
    form = AdminEditForm(request.POST or None, user=target, initial={
        "full_name": target.first_name, "email": target.email, "is_active": target.is_active})
    if request.method == "POST" and form.is_valid():
        d = form.cleaned_data
        if not d["is_active"]:
            if target.pk == request.user.pk:
                form.add_error("is_active", "You cannot deactivate your own account.")
            elif not _admins().filter(is_active=True).exclude(pk=target.pk).exists():
                form.add_error("is_active", "At least one active admin is required.")
        if not form.errors:
            target.first_name, target.email, target.username = d["full_name"].strip(), d["email"], d["email"]
            target.is_active = d["is_active"]
            if d["password1"]:
                target.set_password(d["password1"])
            target.save()
            services.audit(request.user, "admin_edited", target.email)
            messages.success(request, "Admin updated.")
            return redirect("admin_users")
    return _render(request, form, editing=target)


@admin_required
@require_POST
def admin_user_delete(request, pk):
    target = get_object_or_404(_admins(), pk=pk)
    if target.pk == request.user.pk:
        messages.error(request, "You cannot delete your own account.")
    elif not _admins().filter(is_active=True).exclude(pk=target.pk).exists():
        messages.error(request, "At least one active admin is required.")
    else:
        email = target.email
        target.delete()
        services.audit(request.user, "admin_deleted", email)
        messages.success(request, f"Admin {email} deleted.")
    return redirect("admin_users")

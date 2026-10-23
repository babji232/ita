from django.contrib.auth.models import User
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Create (or update) an admin user. Login uses the email address."

    def add_arguments(self, parser):
        parser.add_argument("email")
        parser.add_argument("password")
        parser.add_argument("--name", default="Administrator")

    def handle(self, *args, **o):
        email = o["email"].lower()
        user, _ = User.objects.get_or_create(username=email, defaults={"email": email})
        user.email, user.first_name = email, o["name"]
        user.is_staff = user.is_superuser = True
        user.set_password(o["password"])
        user.save()
        self.stdout.write(self.style.SUCCESS(f"Admin ready: {email}"))

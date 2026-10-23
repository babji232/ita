from django.core.management.base import BaseCommand

from exam.models import ReportLog
from exam.services import send_report


class Command(BaseCommand):
    help = "Retry failed/pending score-report emails (run via cron every few minutes)"

    def handle(self, *args, **opts):
        n = 0
        for log in ReportLog.objects.exclude(delivery_status="sent").filter(retries__lt=10).select_related("attempt"):
            send_report(log.attempt, log)
            n += 1
        self.stdout.write(f"Retried {n} report(s)")

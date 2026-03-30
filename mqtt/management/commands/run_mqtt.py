"""
Django Management Command: Run MQTT Scheduler
Usage: python manage.py run_mqtt
"""
from django.core.management.base import BaseCommand
from mqtt import scheduler


class Command(BaseCommand):
    help = 'Start MQTT client and job scheduler for Smart Home'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('🚀 Starting MQTT Scheduler...'))
        scheduler.start_scheduler()
        self.stdout.write(self.style.SUCCESS('⛔ MQTT Scheduler stopped'))

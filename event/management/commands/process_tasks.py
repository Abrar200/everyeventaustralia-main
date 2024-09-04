# event/management/commands/process_tasks.py

from django.core.management.base import BaseCommand
from background_task.models import Task
from background_task.tasks import tasks, autodiscover
import time
from datetime import datetime

class Command(BaseCommand):
    help = 'Process background tasks'

    def handle(self, *args, **options):
        print(f"Starting background task processing at {datetime.now()}")
        autodiscover()
        while True:
            print(f"\nChecking for tasks at {datetime.now()}...")
            task_count = Task.objects.filter(locked_by__isnull=True).count()
            print(f"Number of unlocked tasks: {task_count}")
            if task_count > 0:
                print("Processing tasks")
                tasks.run_next_task()
                print("Finished processing task")
            else:
                print("No tasks to process")
            time.sleep(10)  # Wait for 10 seconds before checking again
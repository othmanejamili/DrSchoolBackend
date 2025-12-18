# your_project/celery.py


import os
from celery import Celery
from celery.schedules import crontab

# Set Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Drive.settings')

# Create Celery app
app = Celery('DriveApp')

# Load configuration from Django settings
app.config_from_object('django.conf:settings', namespace='CELERY')

# Auto-discover tasks from all installed apps
app.autodiscover_tasks()

# Periodic task schedule
app.conf.beat_schedule = {
    'test-every-minute': {
        'task': 'test_email_task',
        'schedule': crontab(minute='*/1'),  # Every minute for testing
    },
}

app.conf.timezone = 'UTC'


@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')




# Install dependencies
#pip install celery redis

# Start Redis (message broker)
#redis-server

# Start Celery worker
#celery -A DriveApp worker -l info

# Start Celery beat (scheduler)
#celery -A DriveApp beat -l info

# Run both together (development only)
#celery -A your_project worker -B -l info
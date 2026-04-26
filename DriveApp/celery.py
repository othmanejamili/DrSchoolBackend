# your_project/celery.py


# your_project/celery.py
import ssl
import certifi
import os
# Fix macOS SSL issue
ssl._create_default_https_context = ssl.create_default_context
os.environ.setdefault('SSL_CERT_FILE', certifi.where())

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



app.conf.timezone = 'UTC'


@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')

app.conf.broker_connection_retry_on_startup = True



# Install dependencies
#pip install celery redis

# Start Redis (message broker)
#redis-server

# Start Celery worker
#celery -A DriveApp worker -l info

# Start Celery beat (scheduler)
#celery -A DriveApp beat -l info

# Run both together (development only)
#celery -A DriveApp worker -B -l info
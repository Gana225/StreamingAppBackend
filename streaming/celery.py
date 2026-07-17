import os
from celery import Celery

# Set default Django settings module for celery
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'streaming.settings')

app = Celery('streaming')

# Read configuration from Django settings using the CELERY_ namespace prefix
app.config_from_object('django.conf:settings', namespace='CELERY')

# Automatically discover asynchronous @shared_task functions inside apps
app.autodiscover_tasks()
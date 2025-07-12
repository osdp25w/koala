import os

from celery import Celery

from koala import settings

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'koala.settings')

app = Celery('koala')

app.conf.broker_url = settings.CELERY_BROKER_URL
app.conf.result_backend = settings.CELERY_RESULT_BACKEND


app.autodiscover_tasks()

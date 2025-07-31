import os
import ssl

from celery import Celery

from koala import settings

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'koala.settings')

app = Celery('koala')
app.conf.broker_url = settings.CELERY_BROKER_URL
app.conf.result_backend = settings.CELERY_RESULT_BACKEND


if settings.ENV != 'local':
    app.conf.redis_ssl = True
    app.conf.redis_ssl_cert_reqs = ssl.CERT_NONE


app.autodiscover_tasks()

# mqtt is not a django app
app.autodiscover_tasks(['koala.mqtt'])

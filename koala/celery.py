import os
import ssl

from celery import Celery

from koala import settings

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'koala.settings')

app = Celery('koala')

if settings.ENV != 'local':
    app.conf.broker_use_ssl = {
        'ssl_cert_reqs': ssl.CERT_REQUIRED,
        'ssl_ca_certs': settings.RABBITMQ_CA_CERT_PATH,
    }


app.conf.broker_url = settings.CELERY_BROKER_URL
app.conf.result_backend = settings.CELERY_RESULT_BACKEND


app.autodiscover_tasks()

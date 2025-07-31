#!/bin/bash
# entrypoint-celery.sh

QUEUE=${1:-iot_default_q}
celery -A koala worker -Q $QUEUE --concurrency=4 --loglevel=info --pool threads -n iot_worker@%h

#!/bin/bash
# entrypoint-celery.sh

CONCURRENCY=${1:-4}
QUEUE=${2:-iot_default_q}
celery -A koala worker -Q $QUEUE --concurrency=$CONCURRENCY --loglevel=info --pool threads -n ${QUEUE}_worker@%h

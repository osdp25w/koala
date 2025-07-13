#!/bin/bash
# entrypoint-celery.sh


QUEUE=${1:-playlog_q}
celery -A koala worker -Q $QUEUE --concurrency=1 --loglevel=info --pool threads -n ${QUEUE}_worker@%h

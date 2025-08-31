#!/usr/bin/env sh

python manage.py migrate
python manage.py collectstatic --noinput

python manage.py register_periodic_tasks

gunicorn koala.wsgi:application --bind 0.0.0.0:8000 --reload --workers 3 --access-logfile - --error-logfile -

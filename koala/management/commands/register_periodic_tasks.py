import importlib

from celery.schedules import crontab
from django.apps import apps
from django.core.management.base import BaseCommand
from django.utils.timezone import get_current_timezone, now
from django_celery_beat.models import CrontabSchedule, PeriodicTask


class Command(BaseCommand):
    help = 'Register all available Celery beat tasks from app schedules.py'

    def handle(self, *args, **kwargs):
        self.stdout.write('🔍 Discovering CELERY_BEAT_SCHEDULE from installed apps...')

        all_schedules = {}

        for app_config in apps.get_app_configs():
            try:
                module = importlib.import_module(f"{app_config.name}.schedules")
                if hasattr(module, 'CELERY_BEAT_SCHEDULE'):
                    self.stdout.write(f"✅ Found schedule in {app_config.name}")
                    all_schedules.update(module.CELERY_BEAT_SCHEDULE)
            except ModuleNotFoundError:
                continue  # app 沒有 schedules.py 就跳過

        self.stdout.write(f"📦 Total tasks found: {len(all_schedules)}")

        for name, config in all_schedules.items():
            task = config['task']
            schedule = config['schedule']

            self.stdout.write(
                f"🔧 Processing task: {name} → {task} (schedule: {schedule})"
            )

            if isinstance(schedule, crontab):
                cron, _ = CrontabSchedule.objects.get_or_create(
                    minute=schedule._orig_minute,
                    hour=schedule._orig_hour,
                    day_of_week=schedule._orig_day_of_week,
                    day_of_month=schedule._orig_day_of_month,
                    month_of_year=schedule._orig_month_of_year,
                    timezone=schedule.tz or get_current_timezone(),
                )
                PeriodicTask.objects.update_or_create(
                    name=name,
                    defaults={
                        'task': task,
                        'crontab': cron,
                        'enabled': True,
                        'start_time': now(),
                    },
                )
                self.stdout.write(f"📝 Registered crontab task: {name} → {task}")
            elif isinstance(schedule, (int, float)):
                # 支援數字間隔（秒）
                from django_celery_beat.models import IntervalSchedule

                # 先嘗試取得現有的，如果有多個就取第一個
                try:
                    interval = IntervalSchedule.objects.filter(
                        every=int(schedule),
                        period=IntervalSchedule.SECONDS,
                    ).first()
                    if not interval:
                        interval = IntervalSchedule.objects.create(
                            every=int(schedule),
                            period=IntervalSchedule.SECONDS,
                        )
                except Exception as e:
                    self.stdout.write(f"⚠️ Error creating IntervalSchedule: {e}")
                    continue
                PeriodicTask.objects.update_or_create(
                    name=name,
                    defaults={
                        'task': task,
                        'interval': interval,
                        'enabled': True,
                        'start_time': now(),
                    },
                )
                self.stdout.write(
                    f"📝 Registered interval task: {name} → {task} (every {schedule}s)"
                )
            else:
                self.stdout.write(
                    f"⚠️ Unsupported schedule type for {name}: {type(schedule)}"
                )

        self.stdout.write(
            self.style.SUCCESS('🎉 All beat tasks registered successfully.')
        )

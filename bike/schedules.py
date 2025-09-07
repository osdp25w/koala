"""
Bike 應用的 Celery Beat 排程任務
"""

from celery.schedules import crontab

CELERY_BEAT_SCHEDULE = {
    'sync-bike-realtime-status': {
        'task': 'bike.tasks.sync_bike_realtime_status',
        'schedule': 10.0,  # 每10秒執行一次
    },
}

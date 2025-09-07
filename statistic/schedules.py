"""
Statistic 應用的 Celery Beat 排程任務
"""

from celery.schedules import crontab

CELERY_BEAT_SCHEDULE = {
    'trigger-hourly-statistics': {
        'task': 'statistic.tasks.trigger_hourly_statistics',
        'schedule': crontab(minute=1),  # 每小時第1分鐘執行統計上一小時
    },
    # 每日統計觸發器 - 每天中午12:10執行，會自動計算前一天並觸發統計
    'trigger-daily-statistics': {
        'task': 'statistic.tasks.trigger_daily_statistics',
        'schedule': crontab(hour=0, minute=5),  # 每天 00:05 執行統計上一天
    },
}

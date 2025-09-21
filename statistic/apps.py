from django.apps import AppConfig


class StatisticConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'statistic'

    def ready(self):
        """當 app 準備就緒時導入 signals"""
        import statistic.signals

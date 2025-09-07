import logging
from functools import wraps

logger = logging.getLogger(__name__)


def celery_retry(max_retries: int = 3, countdown: int = 300):
    """
    Celery 任務重試裝飾器

    Args:
        max_retries: 最大重試次數
        countdown: 重試間隔時間（秒）

    Usage:
        @celery_retry(max_retries=3, countdown=300)
        @shared_task(bind=True)
        def my_task(self):
            # 在需要重試的地方拋出異常即可
            if some_condition_not_met:
                raise Exception("Condition not met, will retry")
    """

    def decorator(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            try:
                return func(self, *args, **kwargs)
            except Exception as exc:
                if self.request.retries < max_retries:
                    logger.warning(
                        f"Task {func.__name__} failed: {exc}. "
                        f"Retrying in {countdown} seconds... "
                        f"(attempt {self.request.retries + 1}/{max_retries})"
                    )
                    raise self.retry(countdown=countdown, exc=exc)
                else:
                    logger.error(
                        f"Task {func.__name__} failed after {max_retries} retries: {exc}"
                    )
                    raise

        return wrapper

    return decorator

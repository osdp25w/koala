from dateutil.relativedelta import relativedelta
from psqlextra.partitioning import (
    PostgresCurrentTimePartitioningStrategy,
    PostgresPartitioningManager,
    PostgresTimePartitionSize,
)
from psqlextra.partitioning.config import PostgresPartitioningConfig

from telemetry.models import TelemetryRecord

manager = PostgresPartitioningManager(
    [
        # TelemetryRecord - 保留24個月的遙測數據
        PostgresPartitioningConfig(
            model=TelemetryRecord,  # 使用模型類別，不是字串
            strategy=PostgresCurrentTimePartitioningStrategy(
                size=PostgresTimePartitionSize(months=1),  # 按月分區
                count=3,  # 預先創建未來3個月的分區
                max_age=relativedelta(months=24),  # 保留24個月的數據
            ),
        ),
        # 未來可以添加其他分區表配置：
        #
        # # 其他模型 - 保留12個月
        # PostgresPartitioningConfig(
        #     model='otherapp.OtherModel',
        #     strategy=PostgresCurrentTimePartitioningStrategy(
        #         size=PostgresTimePartitionSize(months=1),
        #         count=3,  # 預先創建未來3個月
        #         max_age=relativedelta(months=12),  # 只保留12個月
        #     ),
        # ),
        #
        # # 日誌類型 - 按日分區，保留較短時間
        # PostgresPartitioningConfig(
        #     model='logs.DailyLog',
        #     strategy=PostgresCurrentTimePartitioningStrategy(
        #         size=PostgresTimePartitionSize(days=1),  # 按日分區
        #         count=30,  # 預先創建未來30天
        #         max_age=relativedelta(days=90),  # 保留90天
        #     ),
        # ),
    ]
)

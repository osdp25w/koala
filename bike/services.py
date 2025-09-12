import logging
import math
import re
from copy import copy
from datetime import timedelta
from typing import List, Optional

from celery import current_app
from django.core.cache import cache
from django.db.models import Max, Q
from django.utils import timezone

from bike.constants import BikeErrorLogConstants
from bike.models import BikeRealtimeStatus
from telemetry.constants import IoTConstants
from telemetry.models import TelemetryRecord
from telemetry.services import IoTRawProcessService, IoTRawValidationService

logger = logging.getLogger(__name__)


class BikeErrorLogService:
    """
    車輛錯誤處理服務
    負責檢查錯誤條件和格式化錯誤訊息
    """

    @staticmethod
    def evaluate_condition_expression(
        expression: str, iot_data: dict
    ) -> tuple[bool, dict]:
        """
        評估條件表達式

        Args:
            expression: 條件表達式，如 'battery_temp1 >= 55 OR battery_temp2 >= 55'
            iot_data: IoT MSG 數據

        Returns:
            (是否觸發, 觸發信息)
        """
        expression_with_values = copy(expression)
        triggered_values = {}

        # 找出所有字段名 (支持小寫、下劃線、數字)
        field_pattern = r'\b([a-zA-Z][a-zA-Z0-9_]*)\b'
        fields = re.findall(field_pattern, expression)

        # 替換字段名為實際值
        for field in set(fields):
            value = iot_data.get(field)
            if value is not None:
                triggered_values[field] = value
                # 替換字段名為數值
                expression_with_values = re.sub(
                    rf'\b{field}\b', str(value), expression_with_values
                )
            else:
                # 如果欄位沒有值，替換為 None
                expression_with_values = re.sub(
                    rf'\b{field}\b', 'None', expression_with_values
                )

        # 處理 None 值的比較
        expression_with_values = re.sub(
            r'None\s*([><=!]+)\s*(\d+)', r'False', expression_with_values
        )
        expression_with_values = re.sub(
            r'(\d+)\s*([><=!]+)\s*None', r'False', expression_with_values
        )
        expression_with_values = re.sub(
            r'None\s*==\s*None', r'True', expression_with_values
        )

        try:
            # 將 & 和 | 替換為 Python 邏輯運算符
            safe_expression = expression_with_values
            safe_expression = safe_expression.replace(' | ', ' or ')
            safe_expression = safe_expression.replace(' & ', ' and ')

            result = eval(safe_expression)
            return bool(result), triggered_values

        except Exception as e:
            logger.error(f"Error evaluating condition expression '{expression}': {e}")
            return False, {}

    @staticmethod
    def check_location_anomaly(
        iot_data: dict, bike_id: str, current_status=None
    ) -> tuple[bool, dict]:
        """
        檢查車輛位置異常 - 短時間內大幅位移

        Args:
            iot_data: IoT MSG 數據
            bike_id: 車輛ID
            current_status: BikeRealtimeStatus 物件 (可選，提供則不查詢資料庫)

        Returns:
            (是否觸發, 額外資訊)
        """
        try:
            # 如果沒有提供current_status，則查詢資料庫
            if current_status is None:
                try:
                    current_status = BikeRealtimeStatus.objects.get(bike_id=bike_id)
                except BikeRealtimeStatus.DoesNotExist:
                    # 如果沒有現有狀態，不觸發位置異常
                    logger.error(f"BikeRealtimeStatus not found for bike_id: {bike_id}")
                    return False, {}

            # 獲取新的位置數據
            new_lat = iot_data.get('LA')  # 緯度 * 10^6
            new_lng = iot_data.get('LG')  # 經度 * 10^6

            if new_lat is None or new_lng is None:
                return False, {}

            # 計算距離 (使用 Haversine 公式)
            old_lat = current_status.latitude / 1000000.0  # 轉為十進位
            old_lng = current_status.longitude / 1000000.0
            new_lat_decimal = new_lat / 1000000.0
            new_lng_decimal = new_lng / 1000000.0

            # Haversine 公式計算距離
            def haversine_distance(lat1, lon1, lat2, lon2):
                R = 6371000  # 地球半徑（公尺）
                lat1_rad = math.radians(lat1)
                lat2_rad = math.radians(lat2)
                delta_lat = math.radians(lat2 - lat1)
                delta_lon = math.radians(lon2 - lon1)

                a = (
                    math.sin(delta_lat / 2) ** 2
                    + math.cos(lat1_rad)
                    * math.cos(lat2_rad)
                    * math.sin(delta_lon / 2) ** 2
                )
                c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

                return R * c

            distance = haversine_distance(
                old_lat, old_lng, new_lat_decimal, new_lng_decimal
            )

            # 計算時間差
            time_diff = (timezone.now() - current_status.last_seen).total_seconds()

            # 異常判斷條件：
            # 1. 距離 > 1000 公尺 且 時間差 < 60 秒（不合理的高速移動）
            # 2. 距離 > 5000 公尺 且 時間差 < 300 秒（極度異常的瞬移）
            is_anomaly = (distance > 1000 and time_diff < 60) or (
                distance > 5000 and time_diff < 300
            )

            extra_info = {
                'distance': distance,
                'time_diff': int(time_diff),
                'old_position': {'lat': old_lat, 'lng': old_lng},
                'new_position': {'lat': new_lat_decimal, 'lng': new_lng_decimal},
            }

            return is_anomaly, extra_info

        except Exception as e:
            logger.error(f"Error checking location anomaly for {bike_id}: {e}")
            return False, {}

    @staticmethod
    def check_all_conditions_from_telemetry_record(
        telemetry_record: TelemetryRecord,
        current_status: Optional[BikeRealtimeStatus] = None,
    ) -> list[dict]:
        """
        從 TelemetryRecord 檢查所有錯誤條件

        Args:
            telemetry_record: TelemetryRecord 實例
            current_status: BikeRealtimeStatus 實例 (可選，用於位置異常檢查)

        Returns:
            觸發的錯誤列表，每個錯誤包含錯誤類型和 telemetry_record_snapshot
        """
        triggered_errors = []

        for error_type in BikeErrorLogConstants.ALL_ERROR_TYPES:
            condition_expression = error_type.get('condition_expression', '')

            if not condition_expression:
                continue

            # 檢查是否需要自定義處理器
            if condition_expression in BikeErrorLogConstants.CUSTOM_HANDLED_EXPRESSIONS:
                error_data = BikeErrorLogService._handle_custom_expressions(
                    error_type, telemetry_record, current_status
                )
                if error_data:
                    triggered_errors.append(error_data)
            else:
                # 一般條件檢查 - 直接使用 TelemetryRecord 欄位
                (
                    is_triggered,
                    triggered_values,
                ) = BikeErrorLogService._evaluate_telemetry_record_condition(
                    condition_expression, telemetry_record
                )

                if is_triggered:
                    # 找出觸發的欄位和值
                    triggered_field = None
                    triggered_value = None
                    if triggered_values:
                        triggered_field = list(triggered_values.keys())[0]
                        triggered_value = triggered_values[triggered_field]

                    error_data = {
                        'error_type': error_type,
                        'bike_id': telemetry_record.bike_id,
                        'triggered_field': triggered_field,
                        'triggered_value': triggered_value,
                        'triggered_values': triggered_values,
                        'extra_info': {},
                    }
                    triggered_errors.append(error_data)

        # 為每個錯誤添加 telemetry_record_snapshot
        for error_data in triggered_errors:
            error_data[
                'telemetry_record_snapshot'
            ] = BikeErrorLogService._create_telemetry_record_snapshot(telemetry_record)

        return triggered_errors

    @staticmethod
    def _handle_custom_expressions(
        error_type: dict,
        telemetry_record: TelemetryRecord,
        current_status: Optional[BikeRealtimeStatus] = None,
    ) -> dict:
        """
        處理自定義表達式

        Args:
            error_type: 錯誤類型定義
            telemetry_record: TelemetryRecord 實例
            current_status: BikeRealtimeStatus 實例

        Returns:
            錯誤數據字典，如果未觸發則返回 None
        """
        condition_expression = error_type.get('condition_expression', '')

        match condition_expression:
            case BikeErrorLogConstants.LOCATION_CHECK:
                if current_status:
                    iot_data = {
                        'LA': telemetry_record.latitude,
                        'LG': telemetry_record.longitude,
                    }
                    is_anomaly, extra_info = BikeErrorLogService.check_location_anomaly(
                        iot_data, telemetry_record.bike_id, current_status
                    )

                    if is_anomaly:
                        return {
                            'error_type': error_type,
                            'bike_id': telemetry_record.bike_id,
                            'triggered_field': 'location',
                            'triggered_value': None,
                            'triggered_values': {},
                            'extra_info': extra_info,
                        }

            case _:
                logger.warning(f"Unknown custom expression: {condition_expression}")

        return None

    @staticmethod
    def _evaluate_telemetry_record_condition(
        expression: str, record: 'TelemetryRecord'
    ) -> tuple[bool, dict]:
        """
        評估基於 TelemetryRecord 欄位的條件表達式

        Args:
            expression: 條件表達式 (如 "satellites_count < 4")
            record: TelemetryRecord 實例

        Returns:
            (是否觸發, 觸發的欄位值字典)
        """
        try:
            # 創建評估的變數字典
            variables = {}
            for field in record._meta.get_fields():
                if hasattr(record, field.name):
                    value = getattr(record, field.name)
                    # 處理 None 值
                    if value is None:
                        if field.name in [
                            'controller_temp',
                            'battery_temp1',
                            'battery_temp2',
                        ]:
                            value = -999  # 設定一個不會觸發條件的值
                        else:
                            value = 0
                    variables[field.name] = value

            # 評估表達式
            result = eval(expression, {'__builtins__': {}}, variables)

            if result:
                # 找出觸發條件的欄位
                triggered_values = {}
                for field_name in variables:
                    if field_name in expression:
                        triggered_values[field_name] = variables[field_name]

                return True, triggered_values
            else:
                return False, {}

        except Exception as e:
            logger.error(
                f"Error evaluating telemetry record condition '{expression}': {e}"
            )
            return False, {}

    @staticmethod
    def _create_telemetry_record_snapshot(record: TelemetryRecord) -> dict:
        """
        創建 TelemetryRecord 的快照數據

        Args:
            record: TelemetryRecord 實例

        Returns:
            TelemetryRecord 快照字典
        """
        snapshot = record.__dict__.copy()
        # 移除 Django 內部欄位
        snapshot.pop('_state', None)

        # 處理 datetime 序列化
        for key, value in snapshot.items():
            if hasattr(value, 'isoformat'):
                snapshot[key] = value.isoformat()

        return snapshot

    @staticmethod
    def is_duplicate_error(
        bike_id: str, error_code: str, window_minutes: int = 10
    ) -> bool:
        """
        檢查是否為重複錯誤（使用 Redis cache）

        Args:
            bike_id: 車輛ID
            error_code: 錯誤代碼（每個 code 都是唯一的）
            window_minutes: 時間窗口（分鐘）

        Returns:
            是否為重複錯誤
        """
        try:
            # 使用 Redis cache 檢查重複，只需要 bike_id 和 error_code
            cache_key = f"bike_error_log:{bike_id}:{error_code}"

            if cache.get(cache_key):
                # Cache 中存在，表示重複
                return True
            else:
                # Cache 中不存在，設置 cache 並返回非重複
                cache.set(cache_key, True, timeout=window_minutes * 60)  # 轉換為秒
                return False

        except Exception as e:
            logger.error(
                f"Error checking duplicate error for {bike_id}, {error_code}: {e}"
            )
            # 如果 cache 出錯，回退到資料庫檢查
            from bike.models import BikeErrorLog, BikeInfo

            try:
                bike = BikeInfo.objects.get(bike_id=bike_id)
                return BikeErrorLog.objects.filter(
                    bike=bike,
                    code=error_code,
                    created_at__gte=timezone.now() - timedelta(minutes=window_minutes),
                ).exists()
            except:
                return False

    @staticmethod
    def format_error_message(
        error_type: dict,
        bike_id: str,
        triggered_value=None,
        error_message: str = None,
        extra_info: dict = None,
        **kwargs,
    ) -> str:
        """
        格式化錯誤訊息

        Args:
            error_type: 錯誤類型定義
            bike_id: 車輛ID
            triggered_value: 觸發的數值
            error_message: 錯誤訊息（用於設備錯誤代碼）
            extra_info: 額外資訊（用於特殊錯誤類型）
            **kwargs: 其他格式化參數

        Returns:
            格式化後的錯誤訊息
        """
        format_params = {'bike_id': bike_id, **kwargs}

        # 根據 message_format_required_fields 動態添加參數
        required_fields = error_type.get('message_format_required_fields', [])

        for field in required_fields:
            match field:
                case 'satellite_count':
                    format_params[field] = triggered_value
                case 'temp':
                    format_params[field] = triggered_value
                case 'soc':
                    format_params[field] = triggered_value
                case 'distance':
                    if extra_info:
                        format_params[field] = extra_info.get('distance', 0)
                case 'time_diff':
                    if extra_info:
                        format_params[field] = extra_info.get('time_diff', 0)
                case 'rssi':
                    format_params[field] = triggered_value
                case 'error_code':
                    format_params[field] = triggered_value

        return error_type['message_format'].format(**format_params)


class BikeRealtimeStatusTelemetrySyncer:
    """
    車輛即時狀態遙測數據同步器
    負責從遙測記錄同步和更新車輛即時狀態
    """

    @staticmethod
    def get_latest_telemetry_records(cutoff_time) -> List[TelemetryRecord]:
        """
        取得最近時間窗口內每個bike的最新遙測記錄

        Args:
            cutoff_time: 時間截止點

        Returns:
            最新遙測記錄列表
        """
        # 找出每個bike在時間窗口內的最新記錄時間
        latest_times = (
            TelemetryRecord.objects.filter(created_at__gte=cutoff_time)
            .values('bike_id')
            .annotate(latest_created_at=Max('created_at'))
        )

        if not latest_times:
            return []

        # 構建查詢條件：(bike_id, created_at) 的組合
        query = Q()
        for item in latest_times:
            query |= Q(bike_id=item['bike_id'], created_at=item['latest_created_at'])

        # 批量查詢所有最新記錄
        return list(TelemetryRecord.objects.filter(query))

    @staticmethod
    def prepare_basic_status_data(record: TelemetryRecord) -> dict:
        """
        從遙測記錄準備基本狀態數據（位置、電量等）

        Args:
            record: 遙測記錄對象

        Returns:
            基本狀態數據字典
        """
        # 只更新基本數據，不涉及業務狀態判斷
        status_data = {
            'latitude': record.latitude,
            'longitude': record.longitude,
            'soc': record.soc,
            'vehicle_speed': record.vehicle_speed,
            'last_seen': timezone.now(),
        }

        return status_data

    @classmethod
    def batch_update_bike_status(cls, records: List[TelemetryRecord]) -> int:
        """
        批量更新車輛即時狀態（只更新基本資料，不判斷業務狀態）

        Args:
            records: 遙測記錄列表

        Returns:
            更新的記錄數量
        """
        if not records:
            return 0

        # 收集所有需要更新的 bike_id
        bike_ids = [record.bike_id for record in records]

        # 批量查詢現有的車輛狀態
        existing_bike_statuses = {
            bike_status.bike_id: bike_status
            for bike_status in BikeRealtimeStatus.objects.filter(bike_id__in=bike_ids)
        }

        statuses_to_update = []

        for record in records:
            try:
                bike_realtime_status = existing_bike_statuses.get(record.bike_id)

                if not bike_realtime_status:
                    logger.warning(
                        f"Unknown bike_id in telemetry data: {record.bike_id}"
                    )
                    continue

                # 準備基本狀態數據
                status_data = cls.prepare_basic_status_data(record)

                # 更新基本數據
                for field, value in status_data.items():
                    setattr(bike_realtime_status, field, value)

                # 根據遙測數據判斷是否有錯誤
                has_error = IoTRawValidationService.has_telemetry_error(record)

                if has_error:
                    bike_realtime_status.status = BikeRealtimeStatus.StatusOptions.ERROR
                else:
                    if (
                        bike_realtime_status.status
                        == BikeRealtimeStatus.StatusOptions.ERROR
                    ):
                        if bike_realtime_status.orig_status:
                            bike_realtime_status.status = (
                                bike_realtime_status.orig_status
                            )
                        else:
                            bike_realtime_status.status = (
                                BikeRealtimeStatus.StatusOptions.IDLE
                            )

                statuses_to_update.append(bike_realtime_status)
                logger.debug(f"Prepared update for bike {record.bike_id}")

            except Exception as e:
                logger.error(f"Error preparing update for bike {record.bike_id}: {e}")
                continue

        if statuses_to_update:
            for bike_status in statuses_to_update:
                bike_status.save()  # TODO: fix n+1 problem
            logger.info(f"Updated {len(statuses_to_update)} bike statuses")

        return len(statuses_to_update)

    @classmethod
    def sync_from_recent_telemetry(cls, time_window_minutes: int = 5) -> dict:
        """
        從最近的遙測記錄同步車輛即時狀態和處理錯誤檢查

        Args:
            time_window_minutes: 時間窗口（分鐘）

        Returns:
            同步結果
        """
        try:
            # 設定時間窗口
            cutoff_time = timezone.now() - timedelta(minutes=time_window_minutes)

            logger.info(
                f"Starting bike realtime status sync for records after {cutoff_time}"
            )

            # 1. 更新車輛狀態 - 使用最新記錄
            latest_records = cls.get_latest_telemetry_records(cutoff_time)
            updated_count = 0
            if latest_records:
                updated_count = cls.batch_update_bike_status(latest_records)

            # 2. 錯誤檢查 - 使用所有未同步的記錄
            unsynced_records = cls.get_unsynced_telemetry_records()
            error_count = 0
            if unsynced_records:
                error_count = cls.process_unsynced_records_for_errors(unsynced_records)

                # 更新為已同步
                cls.update_records_as_synced(unsynced_records)

            logger.info(
                f"Sync completed: {updated_count} statuses updated, {error_count} errors processed"
            )
            return {
                'success': True,
                'message': f"Updated {updated_count} statuses, processed {error_count} error checks",
                'updated_count': updated_count,
                'error_checks_count': error_count,
            }

        except Exception as e:
            logger.error(f"Error syncing bike realtime status: {e}")
            return {
                'success': False,
                'error': str(e),
                'updated_count': 0,
                'error_checks_count': 0,
            }

    @classmethod
    def get_unsynced_telemetry_records(cls) -> List[TelemetryRecord]:
        """
        取得所有未同步的遙測記錄

        Returns:
            未同步的遙測記錄列表
        """
        return list(
            TelemetryRecord.objects.filter(is_synced=False).order_by('created_at')
        )

    @classmethod
    def process_unsynced_records_for_errors(cls, records: List[TelemetryRecord]) -> int:
        """
        處理未同步記錄的錯誤檢查

        Args:
            records: 未同步的遙測記錄列表

        Returns:
            處理的錯誤數量
        """
        if not records:
            return 0

        # 取得相關的車輛狀態
        bike_ids = [record.bike_id for record in records]
        existing_bike_statuses = {
            bike_status.bike_id: bike_status
            for bike_status in BikeRealtimeStatus.objects.filter(bike_id__in=bike_ids)
        }

        total_errors = 0
        # 追蹤本次批處理中已處理的錯誤，防止批次內重複
        batch_processed_errors = set()

        for record in records:
            try:
                current_status = existing_bike_statuses.get(record.bike_id)

                # 檢查所有錯誤條件
                triggered_errors = (
                    BikeErrorLogService.check_all_conditions_from_telemetry_record(
                        record, current_status
                    )
                )

                # 處理觸發的錯誤
                for error_data in triggered_errors:
                    error_code = error_data['error_type']['code']
                    bike_error_key = f"{record.bike_id}:{error_code}"

                    # 檢查是否在本次批處理中已經處理過相同錯誤
                    if bike_error_key in batch_processed_errors:
                        logger.debug(
                            f"Skipped batch duplicate error {error_code} for bike {record.bike_id}"
                        )
                        continue

                    # 檢查資料庫中的重複
                    if not BikeErrorLogService.is_duplicate_error(
                        record.bike_id, error_code
                    ):
                        cls._queue_error_log_task(
                            error_data, record.telemetry_device_imei
                        )
                        batch_processed_errors.add(bike_error_key)  # 標記已處理
                        total_errors += 1
                        logger.info(
                            f"Queued error {error_code} for bike {record.bike_id}"
                        )
                    else:
                        logger.debug(
                            f"Skipped duplicate error {error_code} for bike {record.bike_id}"
                        )

            except Exception as e:
                logger.error(
                    f"Error processing record {record.id} for bike {record.bike_id}: {e}"
                )
                continue

        return total_errors

    @classmethod
    def _queue_error_log_task(cls, error_data: dict, device_imei: str):
        """
        將錯誤資料轉為異步任務

        Args:
            error_data: 錯誤數據
            device_imei: 設備IMEI
        """
        error_type = error_data['error_type']

        # 格式化錯誤訊息
        detail = BikeErrorLogService.format_error_message(
            error_type=error_type,
            bike_id=error_data['bike_id'],
            triggered_value=error_data['triggered_value'],
            extra_info=error_data.get('extra_info'),
        )

        # 準備錯誤日誌數據
        task_data = {
            'bike_id': error_data['bike_id'],
            'code': error_type['code'],
            'level': error_type['level'],
            'title': error_type['title'],
            'detail': detail,
            'telemetry_device_imei': device_imei,
            'telemetry_record_snapshot': error_data['telemetry_record_snapshot'],
            'extra_context': {
                'triggered_field': error_data['triggered_field'],
                'triggered_value': error_data['triggered_value'],
                'triggered_values': error_data.get('triggered_values', {}),
                'extra_info': error_data.get('extra_info', {}),
            },
        }

        # 發送異步任務
        current_app.send_task(
            'bike.tasks.handle_bike_error_log',
            args=[task_data],
            queue='bike_error_log_q',
        )

    @classmethod
    def update_records_as_synced(cls, records: List[TelemetryRecord]):
        """
        更新記錄為已同步狀態

        Args:
            records: 要更新的記錄列表
        """
        if records:
            record_ids = [record.id for record in records]
            TelemetryRecord.objects.filter(id__in=record_ids).update(is_synced=True)
            logger.info(f"Updated {len(records)} records as synced")

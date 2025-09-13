import logging
from datetime import datetime
from typing import Dict, Optional

from celery import current_app
from django.utils import timezone

from telemetry.constants import IoTConstants
from telemetry.models import TelemetryDevice, TelemetryRecord
from telemetry.utils import SafeDataTypeConverter

logger = logging.getLogger(__name__)


class IoTRawProcessService:
    """
    IoT 原始數據處理服務
    負責解析、轉換和保存 IoT 原始數據
    """

    @staticmethod
    def parse_iot_datetime(datetime_str: str) -> datetime:
        """
        將 IoT 設備的時間格式 (YYYYMMDDhhmmss) 轉換為 Django datetime
        例如: 20250730032641 -> 2025-07-30 03:26:41

        Args:
            datetime_str: IoT 時間格式字串

        Returns:
            轉換後的 datetime 對象
        """
        try:
            if not datetime_str or len(str(datetime_str)) != 14:
                return timezone.now()

            datetime_str = str(datetime_str)
            year = int(datetime_str[0:4])
            month = int(datetime_str[4:6])
            day = int(datetime_str[6:8])
            hour = int(datetime_str[8:10])
            minute = int(datetime_str[10:12])
            second = int(datetime_str[12:14])

            dt = datetime(year, month, day, hour, minute, second)
            return timezone.make_aware(dt)
        except (ValueError, TypeError):
            logger.warning(
                f"Invalid datetime format: {datetime_str}, using current time"
            )
            return timezone.now()

    @staticmethod
    def save_telemetry_record(device_id: str, sequence_id: int, msg_data: dict) -> dict:
        """
        將 IoT 數據轉換並保存到 TelemetryRecord

        Args:
            device_id: 設備 ID (IMEI)
            sequence_id: 序列號
            msg_data: IoT MSG 數據

        Returns:
            保存結果 {'success': bool, 'record_id'?: int, 'error'?: str}
        """
        try:
            # 直接從 IoT 數據中取得 bike_id
            bike_id = msg_data.get('BI')
            if not bike_id:
                return {
                    'success': False,
                    'error': f'No bike_id found in message data: {device_id}',
                }

            # 轉換時間格式
            gps_time = IoTRawProcessService.parse_iot_datetime(msg_data.get('GT'))
            rtc_time = IoTRawProcessService.parse_iot_datetime(msg_data.get('RT'))
            send_time = IoTRawProcessService.parse_iot_datetime(msg_data.get('ST'))

            # 使用統一的數據轉換
            record_data = IoTRawProcessService.convert_iot_message_to_model_data(
                msg_data
            )

            # 添加關聯和時間資訊
            record_data.update(
                {
                    'telemetry_device_imei': device_id,
                    'sequence_id': sequence_id,
                    'gps_time': gps_time,
                    'rtc_time': rtc_time,
                    'send_time': send_time,
                }
            )

            # 創建遙測記錄
            telemetry_record = TelemetryRecord(**record_data)
            telemetry_record.save()

            return {'success': True, 'record_id': telemetry_record.id}

        except Exception as e:
            logger.error(f"Error saving telemetry record: {e}")
            return {'success': False, 'error': str(e)}

    @classmethod
    def process_telemetry_message(
        cls, device_id: str, sequence_id: int, msg_data: dict
    ) -> dict:
        """
        處理遙測消息的主要入口點

        Args:
            device_id: 設備 ID
            sequence_id: 序列號
            msg_data: IoT MSG 數據

        Returns:
            處理結果
        """
        # 驗證數據
        validation_result = IoTRawValidationService.validate_iot_message(msg_data)
        if not validation_result['valid']:
            logger.error(
                f"IoT message validation failed: {validation_result['errors']}"
            )
            return {
                'success': False,
                'error': f"Validation failed: {validation_result['errors']}",
            }

        # 保存遙測記錄
        save_result = cls.save_telemetry_record(device_id, sequence_id, msg_data)

        return save_result

    @staticmethod
    def get_model_field_name(iot_field: str) -> str:
        """
        根據 IoT 欄位名稱獲取對應的模型欄位名稱

        Args:
            iot_field: IoT 設備的欄位名稱 (如 'GT', 'LA', 'SO')

        Returns:
            對應的模型欄位名稱 (如 'gps_time', 'latitude', 'soc')
            如果找不到映射則返回原欄位名稱
        """
        return IoTConstants.FIELD_MAPPING.get(iot_field, iot_field.lower())

    @staticmethod
    def get_field_type(iot_field: str) -> str:
        """
        獲取 IoT 欄位的數據類型

        Args:
            iot_field: IoT 設備的欄位名稱

        Returns:
            數據類型 ('int', 'string', 'bool', 'datetime', 'temp')
        """
        return IoTConstants.FIELD_TYPES.get(iot_field, 'string')

    @staticmethod
    def is_special_value(iot_field: str, value) -> bool:
        """
        檢查是否為特殊數值（如溫度的 2000 表示未讀）

        Args:
            iot_field: IoT 設備的欄位名稱
            value: 欄位值

        Returns:
            是否為特殊值
        """
        if iot_field not in IoTConstants.SPECIAL_VALUES:
            return False

        try:
            return int(value) == IoTConstants.SPECIAL_VALUES[iot_field]
        except (ValueError, TypeError):
            return False

    @staticmethod
    def convert_iot_value(iot_field: str, value):
        """
        根據 IoT 欄位類型轉換數值

        Args:
            iot_field: IoT 設備的欄位名稱
            value: 原始數值

        Returns:
            轉換後的數值，特殊值返回 None
        """
        # 檢查特殊值
        if IoTRawProcessService.is_special_value(iot_field, value):
            return None

        # 根據欄位類型轉換
        field_type = IoTRawProcessService.get_field_type(iot_field)

        match field_type:
            case 'int' | 'temp':
                return SafeDataTypeConverter.safe_int(value, 0)
            case 'bool':
                return SafeDataTypeConverter.safe_bool(value, False)
            case 'string':
                return SafeDataTypeConverter.safe_string(value, '')
            case _:
                # datetime 等特殊類型在外部處理
                return value

    @staticmethod
    def convert_iot_message_to_model_data(msg_data: dict) -> dict:
        """
        將 IoT 消息數據轉換為模型數據格式

        Args:
            msg_data: IoT MSG 數據

        Returns:
            轉換後的模型數據字典
        """
        model_data = {}

        for iot_field, value in msg_data.items():
            # 獲取對應的模型欄位名稱
            model_field = IoTRawProcessService.get_model_field_name(iot_field)

            # 跳過時間欄位（需要特殊處理）
            if IoTRawProcessService.get_field_type(iot_field) == 'datetime':
                continue

            # 使用統一的IoT數據轉換
            converted_value = IoTRawProcessService.convert_iot_value(iot_field, value)
            model_data[model_field] = converted_value

        return model_data


class IoTRawValidationService:
    """
    IoT 數據驗證服務
    負責各種 IoT 數據的格式和內容驗證
    """

    @staticmethod
    def validate_iot_message(msg_data: dict) -> dict:
        """
        驗證 IoT 消息格式和必要欄位

        Args:
            msg_data: IoT MSG 數據

        Returns:
            驗證結果 {'valid': bool, 'errors': list}
        """
        errors = []

        # 檢查必要欄位
        required_fields = ['BI']  # Bike ID 是必須的
        for field in required_fields:
            if field not in msg_data or not msg_data[field]:
                errors.append(f"Missing required field: {field}")

        # 檢查數據類型
        for field, value in msg_data.items():
            if field in IoTConstants.FIELD_TYPES:
                expected_type = IoTRawProcessService.get_field_type(field)
                if not IoTRawValidationService._validate_field_type(
                    field, value, expected_type
                ):
                    errors.append(
                        f"Invalid type for field {field}: expected {expected_type}"
                    )

        return {'valid': len(errors) == 0, 'errors': errors}

    @staticmethod
    def _validate_field_type(field: str, value, expected_type: str) -> bool:
        """
        驗證欄位數據類型

        Args:
            field: 欄位名稱
            value: 欄位值
            expected_type: 預期類型

        Returns:
            是否符合類型要求
        """
        if value is None:
            return True  # None 值允許

        try:
            match expected_type:
                case 'int' | 'temp':
                    int(value)
                    return True
                case 'bool':
                    # IoT 的 bool 通常是 0/1
                    return str(value) in ['0', '1', 'True', 'False']
                case 'string':
                    str(value)
                    return True
                case 'datetime':
                    # 檢查是否為 14 位數字格式
                    return len(str(value)) == 14 and str(value).isdigit()
                case _:
                    return True  # 未知類型允許通過
        except (ValueError, TypeError):
            return False

    @staticmethod
    def has_telemetry_error(record: TelemetryRecord) -> bool:
        """
        檢查遙測記錄是否包含錯誤狀態
        根據 Report ID (RD) 判斷：
        - 2: Normal Update
        - 101: Error Condition
        - 22: Error Code (錯誤訊息在 MS 欄位)

        Args:
            record: 遙測記錄對象

        Returns:
            是否有錯誤
        """
        # 檢查 Report ID 是否為錯誤狀態
        if hasattr(record, 'report_id') and record.report_id is not None:
            if record.report_id in [101, 22]:  # 101: Error Condition, 22: Error Code
                return True

        # 其他錯誤條件檢查
        # 電量極低
        if hasattr(record, 'soc') and record.soc is not None and record.soc < 5:
            return True

        # GPS 信號異常 (GQ=99 表示無信號)
        if hasattr(record, 'gps_signal_quality') and record.gps_signal_quality == 99:
            return True

        return False

    @classmethod
    def validate_telemetry_record(cls, record: TelemetryRecord) -> dict:
        """
        驗證遙測記錄的完整性和有效性

        Args:
            record: 遙測記錄對象

        Returns:
            驗證結果
        """
        errors = []
        warnings = []

        # 檢查是否有錯誤狀態
        if cls.has_telemetry_error(record):
            errors.append('Telemetry contains error condition')

        # 檢查 GPS 數據有效性
        if record.latitude == 0 and record.longitude == 0:
            warnings.append('Invalid GPS coordinates (0,0)')

        # 檢查電量數據
        if record.soc is not None and (record.soc < 0 or record.soc > 100):
            warnings.append(f"Battery level out of range: {record.soc}%")

        return {
            'valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings,
            'has_errors': cls.has_telemetry_error(record),
        }

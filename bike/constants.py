"""
Bike 錯誤相關的常數定義
定義各種車輛錯誤的標題、訊息和級別
"""

from bike.models import BikeErrorLog


class BikeErrorLogConstants:
    """車輛錯誤常數定義"""

    LOCATION_CHECK = 'LOCATION_CHECK'

    CUSTOM_HANDLED_EXPRESSIONS = [
        LOCATION_CHECK,
    ]

    # GPS訊號異常 (info)
    # 條件: satellites_count < 4
    GPS_SIGNAL_POOR = {
        'code': 'gps_signal_poor',
        'title': 'GPS訊號異常',
        'level': BikeErrorLog.LevelOptions.INFO,
        'message_format': '車輛 {bike_id} GPS衛星數量過少 ({satellite_count} 顆)，可能影響定位準確度',
        'message_format_required_fields': ['satellite_count'],
        'condition_expression': 'satellites_count < 4',
        'expression_required_fields': ['satellites_count'],
    }

    # 電池溫度警告 (warning/critical)
    # 條件: warning >= 55, critical >= 60
    BATTERY_TEMP_WARNING = {
        'code': 'battery_temp_warning',
        'title': '電池溫度過高',
        'level': BikeErrorLog.LevelOptions.WARNING,
        'message_format': '車輛 {bike_id} 電池溫度過高 ({temp}°C)，建議停止使用並降溫',
        'message_format_required_fields': ['temp'],
        'condition_expression': 'battery_temp1 >= 55 | battery_temp2 >= 55',
        'expression_required_fields': ['battery_temp1', 'battery_temp2'],
    }

    BATTERY_TEMP_CRITICAL = {
        'code': 'battery_temp_critical',
        'title': '電池溫度危險',
        'level': BikeErrorLog.LevelOptions.CRITICAL,
        'message_format': '車輛 {bike_id} 電池溫度達危險等級 ({temp}°C)，請立即停止使用',
        'message_format_required_fields': ['temp'],
        'condition_expression': 'battery_temp1 >= 60 | battery_temp2 >= 60',
        'expression_required_fields': ['battery_temp1', 'battery_temp2'],
    }

    # 電量警告 (warning/critical)
    # 條件: warning < 20, critical < 10
    BATTERY_LEVEL_WARNING = {
        'code': 'battery_level_warning',
        'title': '電池電量不足',
        'level': BikeErrorLog.LevelOptions.WARNING,
        'message_format': '車輛 {bike_id} 電池電量偏低 ({soc}%)，建議儘快充電',
        'message_format_required_fields': ['soc'],
        'condition_expression': 'soc < 20',
        'expression_required_fields': ['soc'],
    }

    BATTERY_LEVEL_CRITICAL = {
        'code': 'battery_level_critical',
        'title': '電池電量極低',
        'level': BikeErrorLog.LevelOptions.CRITICAL,
        'message_format': '車輛 {bike_id} 電池電量極低 ({soc}%)，即將無法使用',
        'message_format_required_fields': ['soc'],
        'condition_expression': 'soc < 10',
        'expression_required_fields': ['soc'],
    }

    # 車輛位置異常 (info) - 短時間內大幅位移
    # 條件: 需要與 BikeRealtimeStatus 比較位置和時間差
    LOCATION_ANOMALY = {
        'code': 'location_anomaly',
        'title': '車輛位置異常',
        'level': BikeErrorLog.LevelOptions.INFO,
        'message_format': '車輛 {bike_id} 位置異常，短時間內大幅位移 ({distance:.1f}m，{time_diff}秒)，可能存在定位問題',
        'message_format_required_fields': ['distance', 'time_diff'],
        'condition_expression': LOCATION_CHECK,  # 特殊條件，需要額外邏輯處理
        'expression_required_fields': ['latitude', 'longitude'],
    }

    # RSSI訊號異常 (info)
    # 條件: rssi < 4
    RSSI_POOR = {
        'code': 'rssi_poor',
        'title': 'RSSI訊號異常',
        'level': BikeErrorLog.LevelOptions.INFO,
        'message_format': '車輛 {bike_id} 網路訊號品質不佳 (RSSI: {rssi})，可能影響通訊穩定性',
        'message_format_required_fields': ['rssi'],
        'condition_expression': 'rssi < 4',
        'expression_required_fields': ['rssi'],
    }

    # 感測器異常 (info) - 基於確定的 error code
    SENSOR_MALFUNCTION = {
        'code': 'sensor_malfunction',
        'title': '感測器異常',
        'level': BikeErrorLog.LevelOptions.INFO,
        'message_format': '車輛 {bike_id} 感測器讀取異常，部分數據可能不準確',
        'message_format_required_fields': [],
        'condition_expression': 'controller_temp == 2000 | battery_temp1 == 2000 | battery_temp2 == 2000',
        'expression_required_fields': [
            'controller_temp',
            'battery_temp1',
            'battery_temp2',
        ],
    }

    # 遙測設備異常 (critical)
    # 條件: report_id = 101 (Error Condition) OR report_id = 22 (Error Code with message)
    TELEMETRY_DEVICE_MALFUNCTION = {
        'code': 'telemetry_device_malfunction',
        'title': '遙測設備異常',
        'level': BikeErrorLog.LevelOptions.CRITICAL,
        'message_format': '車輛 {bike_id} 遙測設備異常 (錯誤代碼: {error_code})，需要檢查設備狀態',
        'message_format_required_fields': ['error_code'],
        'condition_expression': 'report_id == 101 | report_id == 22',
        'expression_required_fields': ['report_id'],
    }

    # 所有錯誤類型的列表
    ALL_ERROR_TYPES = [
        GPS_SIGNAL_POOR,
        BATTERY_TEMP_WARNING,
        BATTERY_TEMP_CRITICAL,
        BATTERY_LEVEL_WARNING,
        BATTERY_LEVEL_CRITICAL,
        LOCATION_ANOMALY,
        RSSI_POOR,
        SENSOR_MALFUNCTION,
        TELEMETRY_DEVICE_MALFUNCTION,
    ]

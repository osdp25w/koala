class IoTConstants:
    """IoT 設備相關常數配置類"""

    # 消息類型常數
    MESSAGE_TYPE_TELEMETRY = 'telemetry'

    # IoT 設備欄位到 TelemetryRecord 模型欄位的映射
    FIELD_MAPPING = {
        # 時間資訊
        'GT': 'gps_time',  # GPS Date Time in YYYYMMDDhhmmss
        'RT': 'rtc_time',  # RTC Date Time in YYYYMMDDhhmmss
        'ST': 'send_time',  # Sending Date Time in YYYYMMDDhhmmss
        # GPS 位置資訊
        'LG': 'longitude',  # Longitude in 0.000001
        'LA': 'latitude',  # Latitude in 0.000001
        'HD': 'heading_direction',  # GPS heading direction. 0~365 degrees
        'VS': 'vehicle_speed',  # Vehicle Speed in 1km/hr
        'AT': 'altitude',  # GPS Altitude in 1 meter
        'HP': 'gps_hdop',  # GPS HDOP in 0.1 Unit
        'VP': 'gps_vdop',  # GPS VDOP in 0.1 unit
        'SA': 'satellites_count',  # Satellite in view count
        # 電池與動力資訊
        'MV': 'battery_voltage',  # Bike battery voltage in 0.1V
        'SO': 'soc',  # SOC in 1%
        'EO': 'bike_odometer',  # Bike odometer in 1 meter
        'AL': 'assist_level',  # Assist Level range 0~4
        'PT': 'pedal_torque',  # Pedal Torque in 0.01 Nm
        'CT': 'controller_temp',  # Controller Temperature in 1 degree Celsius. 2000=Not read
        'CA': 'pedal_cadence',  # Pedal Cadence in 0.025 RPM
        'TP1': 'battery_temp1',  # Battery Temperature 1 value in 1 degree Celsius
        'TP2': 'battery_temp2',  # Battery Temperature 2 value in 1 degree Celsius
        # 系統狀態資訊
        'IN': 'acc_status',  # Input Status 1: ACC On, 0: ACC Off
        'OP': 'output_status',  # Output Status
        'AI1': 'analog_input',  # Analog Input in 0.001V
        'BV': 'backup_battery',  # Device backup battery voltage in 0.1V
        'GQ': 'rssi',  # RSSI range 0~31, 99=no signal
        'OD': 'total_odometer',  # Odometer in 0.1 km
        'DD': 'member_id',  # Driver ID
        # 報告資訊
        'RD': 'report_id',  # Report ID (2: Normal Update; 101: Error Condition; 22: Error Code)
        'MS': 'message',  # Text message (ERROR Code will show up here with Report ID = 22)
        # 車輛識別
        'BI': 'bike_id',  # Bike ID as string
    }

    # IoT 數據類型定義（用於數據驗證和轉換）
    FIELD_TYPES = {
        # 時間欄位 (特殊處理)
        'GT': 'datetime',
        'RT': 'datetime',
        'ST': 'datetime',
        # 整數欄位
        'LG': 'int',
        'LA': 'int',
        'HD': 'int',
        'VS': 'int',
        'AT': 'int',
        'HP': 'int',
        'VP': 'int',
        'SA': 'int',
        'MV': 'int',
        'SO': 'int',
        'EO': 'int',
        'AL': 'int',
        'PT': 'int',
        'CT': 'temp',  # 特殊處理：2000=None
        'CA': 'int',
        'TP1': 'temp',  # 特殊處理：2000=None
        'TP2': 'temp',  # 特殊處理：2000=None
        'IN': 'bool',
        'OP': 'int',
        'AI1': 'int',
        'BV': 'int',
        'GQ': 'int',
        'OD': 'int',
        'RD': 'int',
        # 字串欄位
        'DD': 'string',
        'MS': 'string',
        'BI': 'string',
    }

    # 特殊數值處理規則
    SPECIAL_VALUES = {
        'CT': 2000,  # Controller Temperature: 2000 = Not read
        'TP1': 2000,  # Battery Temperature 1: 2000 = Not read
        'TP2': 2000,  # Battery Temperature 2: 2000 = Not read
        'GQ': 99,  # RSSI: 99 = No signal
    }

    # 數值縮放係數說明（註釋用，實際轉換在 tasks.py 中處理）
    SCALE_FACTORS = {
        'LG': 'IoT: * 0.000001, DB: * 10^6 (相同)',
        'LA': 'IoT: * 0.000001, DB: * 10^6 (相同)',
        'HP': 'IoT: * 0.1, DB: * 10 (需轉換)',
        'VP': 'IoT: * 0.1, DB: * 10 (需轉換)',
        'MV': 'IoT: * 0.1V, DB: * 10 (相同)',
        'PT': 'IoT: * 0.01 Nm, DB: * 100 (需轉換)',
        'CA': 'IoT: * 0.025 RPM, DB: * 40 (需轉換)',
        'AI1': 'IoT: * 0.001V, DB: * 1000 (相同)',
        'BV': 'IoT: * 0.1V, DB: * 10 (相同)',
        'OD': 'IoT: * 0.1 km, DB: * 10 (相同)',
    }

    # Report ID 定義
    REPORT_IDS = {
        2: 'Normal Update',
        22: 'Error Code',
        101: 'Error Condition',
    }

    # 用於 BikeRealtimeStatus 更新的欄位映射
    REALTIME_STATUS_MAPPING = {
        'LA': 'latitude',
        'LG': 'longitude',
        'SO': 'battery_level',
        'IN': 'acc_status',
        'VS': 'vehicle_speed',
    }

"""
Tests for telemetry models - 業務邏輯測試
專注於 model 的業務邏輯，不涉及 API
"""
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import TestCase

from telemetry.models import TelemetryDevice
from telemetry.tests.base import BaseTelemetryTestWithFixtures


class TelemetryDeviceModelTest(BaseTelemetryTestWithFixtures):
    """TelemetryDevice 模型業務邏輯測試"""

    def test_telemetry_device_string_representation(self):
        """測試設備字串表示"""
        device = self.device_alpha
        expected_str = f"{device.IMEI} - {device.name}"
        self.assertEqual(str(device), expected_str)

    def test_telemetry_device_creation_with_defaults(self):
        """測試創建設備時使用預設值"""
        device = TelemetryDevice.objects.create(
            IMEI='555555555555555', name='Default Status Device', model='TD-2024-IoT'
        )

        self.assertEqual(device.status, TelemetryDevice.StatusOptions.AVAILABLE)
        self.assertIsNotNone(device.created_at)
        self.assertIsNotNone(device.updated_at)

    def test_telemetry_device_imei_uniqueness(self):
        """測試 IMEI 唯一性約束"""
        with self.assertRaises(IntegrityError):
            TelemetryDevice.objects.create(
                IMEI=self.device_alpha.IMEI,  # 重複的 IMEI
                name='Duplicate IMEI Device',
                model='TD-2024-IoT',
            )

    def test_telemetry_device_status_choices(self):
        """測試設備狀態選項"""
        device = self.device_alpha

        # 測試所有有效狀態
        valid_statuses = [
            TelemetryDevice.StatusOptions.AVAILABLE,
            TelemetryDevice.StatusOptions.DEPLOYED,
            TelemetryDevice.StatusOptions.MAINTENANCE,
        ]

        for status in valid_statuses:
            device.status = status
            device.save()
            device.refresh_from_db()
            self.assertEqual(device.status, status)

    def test_telemetry_device_filtering_by_status(self):
        """測試按狀態過濾設備"""
        available_devices = TelemetryDevice.objects.filter(
            status=TelemetryDevice.StatusOptions.AVAILABLE
        )
        deployed_devices = TelemetryDevice.objects.filter(
            status=TelemetryDevice.StatusOptions.DEPLOYED
        )
        maintenance_devices = TelemetryDevice.objects.filter(
            status=TelemetryDevice.StatusOptions.MAINTENANCE
        )

        # 基於 fixtures 驗證
        self.assertEqual(available_devices.count(), 2)  # Alpha, Delta
        self.assertEqual(deployed_devices.count(), 1)  # Beta
        self.assertEqual(maintenance_devices.count(), 1)  # Gamma

    def test_telemetry_device_filtering_by_model(self):
        """測試按型號過濾設備"""
        td_2024_iot_devices = TelemetryDevice.objects.filter(model='TD-2024-IoT')

        # 基於 fixtures 驗證
        self.assertEqual(td_2024_iot_devices.count(), 2)  # Alpha, Gamma

    def test_telemetry_device_ordering(self):
        """測試設備排序"""
        devices = list(TelemetryDevice.objects.all())

        # 應該按 created_at 排序
        for i in range(1, len(devices)):
            self.assertLessEqual(devices[i - 1].created_at, devices[i].created_at)

    def test_telemetry_device_update_timestamps(self):
        """測試更新時間戳"""
        device = self.device_alpha
        original_updated_at = device.updated_at

        # 更新設備
        device.name = 'Updated Device Name'
        device.save()

        device.refresh_from_db()
        self.assertGreater(device.updated_at, original_updated_at)

    def test_telemetry_device_meta_indexes(self):
        """測試模型索引配置"""
        # 這個測試確保模型配置了正確的索引
        meta = TelemetryDevice._meta
        index_fields = []

        for index in meta.indexes:
            index_fields.extend(index.fields)

        # 驗證重要欄位有索引
        self.assertIn('status', index_fields)
        self.assertIn('model', index_fields)

    def test_telemetry_device_cascade_relationships(self):
        """測試與其他模型的關聯關係"""
        # 確保設備被正確載入
        self.assertEqual(TelemetryDevice.objects.count(), 4)

        # 測試設備可以安全刪除（如果沒有關聯的腳踏車）
        device_to_delete = self.device_delta
        device_imei = device_to_delete.IMEI
        device_to_delete.delete()

        # 驗證設備已被刪除
        self.assertFalse(TelemetryDevice.objects.filter(IMEI=device_imei).exists())
        self.assertEqual(TelemetryDevice.objects.count(), 3)

    def test_telemetry_device_imei_length_validation(self):
        """測試 IMEI 長度限制"""
        # IMEI 太長
        with self.assertRaises((ValidationError, IntegrityError)):
            device = TelemetryDevice(
                IMEI='1' * 25, name='Long IMEI Device', model='TD-2024-IoT'  # 超過 20 字元
            )
            device.full_clean()

    def test_telemetry_device_name_length_validation(self):
        """測試設備名稱長度限制"""
        # 名稱太長
        with self.assertRaises(ValidationError):
            device = TelemetryDevice(
                IMEI='666666666666666', name='A' * 105, model='TD-2024-IoT'  # 超過 100 字元
            )
            device.full_clean()

    def test_telemetry_device_bulk_operations(self):
        """測試批量操作"""
        # 批量更新狀態
        TelemetryDevice.objects.filter(
            status=TelemetryDevice.StatusOptions.AVAILABLE
        ).update(status=TelemetryDevice.StatusOptions.MAINTENANCE)

        # 驗證更新結果
        available_count = TelemetryDevice.objects.filter(
            status=TelemetryDevice.StatusOptions.AVAILABLE
        ).count()
        maintenance_count = TelemetryDevice.objects.filter(
            status=TelemetryDevice.StatusOptions.MAINTENANCE
        ).count()

        self.assertEqual(available_count, 0)
        self.assertEqual(maintenance_count, 3)  # Gamma + Alpha + Delta

    def test_telemetry_device_query_performance(self):
        """測試查詢性能相關配置"""
        # 測試索引欄位查詢
        with self.assertNumQueries(1):
            list(TelemetryDevice.objects.filter(status='available'))

        with self.assertNumQueries(1):
            list(TelemetryDevice.objects.filter(model='TD-2024-IoT'))

    def test_telemetry_device_status_transitions(self):
        """測試設備狀態轉換"""
        device = self.device_alpha

        # Available -> Deployed
        device.status = TelemetryDevice.StatusOptions.DEPLOYED
        device.save()
        self.assertEqual(device.status, TelemetryDevice.StatusOptions.DEPLOYED)

        # Deployed -> Maintenance
        device.status = TelemetryDevice.StatusOptions.MAINTENANCE
        device.save()
        self.assertEqual(device.status, TelemetryDevice.StatusOptions.MAINTENANCE)

        # Maintenance -> Available
        device.status = TelemetryDevice.StatusOptions.AVAILABLE
        device.save()
        self.assertEqual(device.status, TelemetryDevice.StatusOptions.AVAILABLE)

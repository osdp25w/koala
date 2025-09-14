"""
Tests for bike services
"""
from django.test import TestCase
from rest_framework.exceptions import ValidationError

from bike.models import BikeInfo, BikeRealtimeStatus
from bike.services import BikeManagementService
from bike.tests.base import BaseBikeTestWithFixtures
from telemetry.models import TelemetryDevice


class BikeManagementServiceTest(BaseBikeTestWithFixtures):
    """BikeManagementService 業務邏輯測試"""

    def test_can_modify_bike_when_idle(self):
        """測試腳踏車在idle狀態時可以修改"""
        self.bike_status_001.status = BikeRealtimeStatus.StatusOptions.IDLE
        self.bike_status_001.save()

        result = BikeManagementService.can_modify_bike(self.bike_test001)
        self.assertTrue(result)

    def test_cannot_modify_bike_when_rented(self):
        """測試腳踏車在租借狀態時不可修改"""
        self.bike_status_001.status = BikeRealtimeStatus.StatusOptions.RENTED
        self.bike_status_001.save()

        result = BikeManagementService.can_modify_bike(self.bike_test001)
        self.assertFalse(result)

    def test_validate_bike_modification_raises_error_when_rented(self):
        """測試租借中的腳踏車修改驗證拋出錯誤"""
        self.bike_status_001.status = BikeRealtimeStatus.StatusOptions.RENTED
        self.bike_status_001.save()

        with self.assertRaises(ValidationError):
            BikeManagementService.validate_bike_modification(self.bike_test001)

    def test_assign_device_to_bike_updates_device_status(self):
        """測試分配設備給腳踏車會更新設備狀態"""
        # 使用未分配的設備
        available_device = TelemetryDevice.objects.get(
            pk='234567890123456'
        )  # device_beta

        BikeManagementService.assign_device_to_bike(
            self.bike_test001, available_device.IMEI
        )

        # 檢查資料庫狀態變化
        self.bike_test001.refresh_from_db()
        available_device.refresh_from_db()

        self.assertEqual(self.bike_test001.telemetry_device_id, available_device.IMEI)
        self.assertEqual(
            available_device.status, TelemetryDevice.StatusOptions.DEPLOYED
        )

    def test_release_device_from_bike_updates_device_status(self):
        """測試從腳踏車釋放設備會更新設備狀態"""
        # bike_test001 已經有分配的設備 (從 fixtures 載入的設備)
        device_gamma = self.bike_test001.telemetry_device

        BikeManagementService.release_device_from_bike(self.bike_test001)

        # 檢查資料庫狀態變化
        self.bike_test001.refresh_from_db()
        device_gamma.refresh_from_db()

        self.assertIsNone(self.bike_test001.telemetry_device)
        self.assertEqual(device_gamma.status, TelemetryDevice.StatusOptions.AVAILABLE)

    def test_update_bike_telemetry_device_switches_devices(self):
        """測試更新腳踏車遙測設備會正確切換設備"""
        # bike_test001 目前使用的設備 (從 fixtures 載入)
        old_device = self.bike_test001.telemetry_device
        new_device = TelemetryDevice.objects.get(pk='234567890123456')  # device_beta

        BikeManagementService.update_bike_telemetry_device(
            self.bike_test001, new_device.IMEI
        )

        # 檢查資料庫狀態變化
        self.bike_test001.refresh_from_db()
        old_device.refresh_from_db()
        new_device.refresh_from_db()

        self.assertEqual(self.bike_test001.telemetry_device_id, new_device.IMEI)
        self.assertEqual(old_device.status, TelemetryDevice.StatusOptions.AVAILABLE)
        self.assertEqual(new_device.status, TelemetryDevice.StatusOptions.DEPLOYED)

    def test_delete_bike_removes_from_database(self):
        """測試刪除腳踏車會從資料庫移除"""
        # 確保腳踏車狀態允許刪除
        self.bike_status_001.status = BikeRealtimeStatus.StatusOptions.IDLE
        self.bike_status_001.save()

        bike_id = self.bike_test001.bike_id
        BikeManagementService.delete_bike(self.bike_test001)

        # 檢查腳踏車已從資料庫刪除
        self.assertFalse(BikeInfo.objects.filter(bike_id=bike_id).exists())

    def test_delete_bike_with_device_releases_device(self):
        """測試刪除有設備的腳踏車會釋放設備"""
        # 確保腳踏車狀態允許刪除
        self.bike_status_001.status = BikeRealtimeStatus.StatusOptions.IDLE
        self.bike_status_001.save()

        device = self.bike_test001.telemetry_device
        bike_id = self.bike_test001.bike_id

        BikeManagementService.delete_bike(self.bike_test001)

        # 檢查設備狀態已恢復
        device.refresh_from_db()
        self.assertEqual(device.status, TelemetryDevice.StatusOptions.AVAILABLE)
        self.assertFalse(BikeInfo.objects.filter(bike_id=bike_id).exists())

    def test_validate_telemetry_device_with_unavailable_device(self):
        """測試驗證不可用的遙測設備會拋出錯誤"""
        # 使用維修狀態的設備
        maintenance_device = TelemetryDevice.objects.get(
            pk='456789012345678'
        )  # device_delta

        with self.assertRaises(ValidationError) as context:
            BikeManagementService.validate_telemetry_device(maintenance_device.IMEI)

        self.assertIn('not available', str(context.exception))

    def test_validate_telemetry_device_already_assigned(self):
        """測試驗證已分配的遙測設備會拋出錯誤"""
        # 取得已分配給 bike_test001 的設備
        assigned_device = self.bike_test001.telemetry_device

        # 嘗試分配給另一個腳踏車
        other_bike = BikeInfo.objects.get(pk='TEST002')

        with self.assertRaises(ValidationError) as context:
            BikeManagementService.validate_telemetry_device(
                assigned_device.IMEI, other_bike
            )

        self.assertIn('not available', str(context.exception))

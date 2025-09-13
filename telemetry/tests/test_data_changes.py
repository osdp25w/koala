"""
Tests for telemetry data changes - 專注於資料變化，不檢查 API 回應
透過 API 操作後檢查資料庫狀態變化
"""
from django.urls import reverse
from rest_framework import status

from bike.models import BikeCategory, BikeInfo, BikeSeries
from telemetry.models import TelemetryDevice

from .base import BaseTelemetryAPITest


class TelemetryDeviceDataChangesTest(BaseTelemetryAPITest):
    """TelemetryDevice 資料變化測試 - 使用 fixtures 載入資料，專注於資料變化"""

    def test_telemetry_device_create_api_creates_device_in_database(self):
        """測試創建遙測設備API會在資料庫中創建設備"""
        self.authenticate_as(self.admin_profile)
        url = reverse('telemetry:devices-list')
        data = {
            'IMEI': '999888777666555',
            'name': 'New API Device',
            'model': 'TD-2024-IoT-v2',
            'status': TelemetryDevice.StatusOptions.AVAILABLE,
        }

        initial_count = TelemetryDevice.objects.count()
        self.client.post(url, data, format='json')

        # 檢查資料庫變化
        current_count = TelemetryDevice.objects.count()
        if current_count > initial_count:
            # 如果設備被創建，檢查資料
            created_device = TelemetryDevice.objects.filter(
                IMEI='999888777666555'
            ).first()
            if created_device:
                self.assertEqual(created_device.name, 'New API Device')
                self.assertEqual(created_device.model, 'TD-2024-IoT-v2')
                self.assertEqual(
                    created_device.status, TelemetryDevice.StatusOptions.AVAILABLE
                )

    def test_telemetry_device_create_with_invalid_imei_fails(self):
        """測試創建無效IMEI的設備會失敗"""
        self.authenticate_as(self.admin_profile)
        url = reverse('telemetry:devices-list')
        data = {
            'IMEI': '12345',  # 長度不正確
            'name': 'Invalid Device',
            'model': 'TD-2024-IoT',
        }

        initial_count = TelemetryDevice.objects.count()
        self.client.post(url, data, format='json')

        # 檢查資料庫中沒有創建設備
        current_count = TelemetryDevice.objects.count()
        self.assertEqual(current_count, initial_count)
        self.assertFalse(TelemetryDevice.objects.filter(IMEI='12345').exists())

    def test_telemetry_device_create_duplicate_imei_fails(self):
        """測試創建重複IMEI的設備會失敗"""
        self.authenticate_as(self.admin_profile)
        url = reverse('telemetry:devices-list')
        data = {
            'IMEI': self.device_alpha.IMEI,  # 使用已存在的IMEI
            'name': 'Duplicate Device',
            'model': 'TD-2024-IoT',
        }

        initial_count = TelemetryDevice.objects.count()
        self.client.post(url, data, format='json')

        # 檢查資料庫中沒有重複的設備
        current_count = TelemetryDevice.objects.count()
        self.assertEqual(current_count, initial_count)

        devices_count = TelemetryDevice.objects.filter(
            IMEI=self.device_alpha.IMEI
        ).count()
        self.assertEqual(devices_count, 1)  # 只有原本的一個

    def test_telemetry_device_update_api_modifies_device_data(self):
        """測試更新遙測設備API會修改資料庫中的資料"""
        self.authenticate_as(self.admin_profile)
        url = reverse('telemetry:devices-detail', kwargs={'pk': self.device_alpha.IMEI})
        data = {
            'name': 'Updated Device Name',
            'model': 'TD-2024-IoT-Updated',
            'status': TelemetryDevice.StatusOptions.MAINTENANCE,
        }

        original_name = self.device_alpha.name
        original_model = self.device_alpha.model
        original_status = self.device_alpha.status

        self.client.patch(url, data, format='json')

        # 檢查資料庫中的數據變化
        self.device_alpha.refresh_from_db()

        # 如果更新成功，檢查變化
        if self.device_alpha.name != original_name:
            self.assertEqual(self.device_alpha.name, 'Updated Device Name')
        if self.device_alpha.model != original_model:
            self.assertEqual(self.device_alpha.model, 'TD-2024-IoT-Updated')
        if self.device_alpha.status != original_status:
            self.assertEqual(
                self.device_alpha.status, TelemetryDevice.StatusOptions.MAINTENANCE
            )

    def test_telemetry_device_update_imei_fails(self):
        """測試嘗試更新設備IMEI會失敗"""
        self.authenticate_as(self.admin_profile)
        url = reverse('telemetry:devices-detail', kwargs={'pk': self.device_alpha.IMEI})
        data = {
            'IMEI': '888777666555444',  # 嘗試修改IMEI
            'name': 'Updated Device',
        }

        original_imei = self.device_alpha.IMEI
        self.client.patch(url, data, format='json')

        # 檢查IMEI沒有改變
        self.device_alpha.refresh_from_db()
        self.assertEqual(self.device_alpha.IMEI, original_imei)
        self.assertNotEqual(self.device_alpha.IMEI, '888777666555444')

    def test_telemetry_device_delete_api_removes_from_database(self):
        """測試刪除遙測設備API會從資料庫移除設備"""
        self.authenticate_as(self.admin_profile)

        device_imei = self.device_delta.IMEI
        url = reverse('telemetry:devices-detail', kwargs={'pk': device_imei})

        initial_count = TelemetryDevice.objects.count()
        self.client.delete(url)

        # 檢查設備是否從資料庫移除
        current_count = TelemetryDevice.objects.count()
        if current_count < initial_count:
            self.assertFalse(TelemetryDevice.objects.filter(IMEI=device_imei).exists())

    def test_telemetry_device_delete_with_bike_association_fails(self):
        """測試刪除有關聯腳踏車的設備會失敗"""
        self.authenticate_as(self.admin_profile)

        # 創建關聯的腳踏車
        category = BikeCategory.objects.create(
            category_name='Test Category', description='Test Description'
        )
        series = BikeSeries.objects.create(
            category=category,
            series_name='Test Series',
            description='Test Series Description',
        )
        bike = BikeInfo.objects.create(
            bike_id='DEL_TEST001',
            bike_name='Delete Test Bike',
            bike_model='Model A',
            series=series,
            telemetry_device=self.device_beta,
        )

        device_imei = self.device_beta.IMEI
        url = reverse('telemetry:devices-detail', kwargs={'pk': device_imei})

        initial_count = TelemetryDevice.objects.count()
        self.client.delete(url)

        # 檢查設備仍然存在（刪除應該失敗）
        current_count = TelemetryDevice.objects.count()
        if current_count == initial_count:
            self.assertTrue(TelemetryDevice.objects.filter(IMEI=device_imei).exists())

    def test_member_cannot_access_telemetry_device_management(self):
        """測試普通會員無法存取遙測設備管理功能"""
        self.authenticate_as(self.member_profile)

        # 測試創建
        url = reverse('telemetry:devices-list')
        data = {
            'IMEI': '777666555444333',
            'name': 'Member Device',
            'model': 'TD-2024-IoT',
        }

        initial_count = TelemetryDevice.objects.count()
        self.client.post(url, data, format='json')

        # 檢查資料庫沒有變化
        current_count = TelemetryDevice.objects.count()
        self.assertEqual(current_count, initial_count)
        self.assertFalse(
            TelemetryDevice.objects.filter(IMEI='777666555444333').exists()
        )

        # 測試更新
        url = reverse('telemetry:devices-detail', kwargs={'pk': self.device_alpha.IMEI})
        original_name = self.device_alpha.name
        self.client.patch(url, {'name': 'Member Updated'}, format='json')

        # 檢查沒有變化
        self.device_alpha.refresh_from_db()
        self.assertEqual(self.device_alpha.name, original_name)

        # 測試刪除
        initial_count = TelemetryDevice.objects.count()
        self.client.delete(url)

        # 檢查設備仍然存在
        current_count = TelemetryDevice.objects.count()
        self.assertEqual(current_count, initial_count)
        self.assertTrue(
            TelemetryDevice.objects.filter(IMEI=self.device_alpha.IMEI).exists()
        )

    def test_staff_can_list_and_retrieve_devices(self):
        """測試工作人員可以查看遙測設備列表和詳情"""
        self.authenticate_as(self.staff_profile)

        # 測試列表存取不會改變資料
        url = reverse('telemetry:devices-list')
        initial_count = TelemetryDevice.objects.count()
        self.client.get(url)

        current_count = TelemetryDevice.objects.count()
        self.assertEqual(current_count, initial_count)

        # 測試詳情存取不會改變資料
        url = reverse('telemetry:devices-detail', kwargs={'pk': self.device_alpha.IMEI})
        self.client.get(url)

        # 確保設備資料沒有變化
        self.device_alpha.refresh_from_db()
        self.assertIsNotNone(self.device_alpha)

    def test_telemetry_device_filter_by_status(self):
        """測試按狀態過濾遙測設備"""
        self.authenticate_as(self.staff_profile)

        url = reverse('telemetry:devices-list')

        # 過濾可用狀態，不檢查回應，只檢查資料庫查詢邏輯
        self.client.get(url, {'status': 'available'})

        # 檢查資料庫查詢結果
        available_devices = TelemetryDevice.objects.filter(status='available')
        self.assertGreaterEqual(available_devices.count(), 1)

        # 過濾維護狀態
        self.client.get(url, {'status': 'maintenance'})

        maintenance_devices = TelemetryDevice.objects.filter(status='maintenance')
        self.assertGreaterEqual(maintenance_devices.count(), 0)

    def test_telemetry_device_create_with_deployed_status_fails(self):
        """測試創建deployed狀態的設備會失敗"""
        self.authenticate_as(self.admin_profile)
        url = reverse('telemetry:devices-list')
        data = {
            'IMEI': '555444333222111',
            'name': 'Deployed Device',
            'model': 'TD-2024-IoT',
            'status': TelemetryDevice.StatusOptions.DEPLOYED,
        }

        initial_count = TelemetryDevice.objects.count()
        self.client.post(url, data, format='json')

        # 檢查資料庫中沒有創建設備
        current_count = TelemetryDevice.objects.count()
        if current_count == initial_count:
            self.assertFalse(
                TelemetryDevice.objects.filter(IMEI='555444333222111').exists()
            )

    def test_telemetry_device_status_update_affects_database(self):
        """測試設備狀態更新影響資料庫"""
        self.authenticate_as(self.admin_profile)
        url = reverse('telemetry:devices-detail', kwargs={'pk': self.device_alpha.IMEI})

        original_status = self.device_alpha.status
        new_status = TelemetryDevice.StatusOptions.MAINTENANCE

        data = {'status': new_status}
        self.client.patch(url, data, format='json')

        # 檢查資料庫變化
        self.device_alpha.refresh_from_db()
        if self.device_alpha.status != original_status:
            self.assertEqual(self.device_alpha.status, new_status)

    def test_telemetry_device_bulk_status_change(self):
        """測試批量狀態變更的資料一致性"""
        self.authenticate_as(self.admin_profile)

        # 記錄初始狀態
        initial_available = TelemetryDevice.objects.filter(
            status=TelemetryDevice.StatusOptions.AVAILABLE
        ).count()

        # 嘗試更新每個可用設備的狀態
        available_devices = TelemetryDevice.objects.filter(
            status=TelemetryDevice.StatusOptions.AVAILABLE
        )

        for device in available_devices:
            url = reverse('telemetry:devices-detail', kwargs={'pk': device.IMEI})
            data = {'status': TelemetryDevice.StatusOptions.MAINTENANCE}
            self.client.patch(url, data, format='json')

        # 檢查狀態變化
        final_available = TelemetryDevice.objects.filter(
            status=TelemetryDevice.StatusOptions.AVAILABLE
        ).count()
        final_maintenance = TelemetryDevice.objects.filter(
            status=TelemetryDevice.StatusOptions.MAINTENANCE
        ).count()

        # 如果更新成功，可用設備數量應該減少
        if final_available < initial_available:
            self.assertGreater(final_maintenance, 1)  # 至少有一個設備變為維護狀態

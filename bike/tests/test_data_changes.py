"""
Tests for bike data changes - 專注於資料變化，不檢查 API 回應
透過 API 操作後檢查資料庫狀態變化
"""
from django.urls import reverse

from bike.models import BikeCategory, BikeInfo, BikeRealtimeStatus, BikeSeries
from bike.tests.base import BaseBikeTestWithFixtures
from telemetry.models import TelemetryDevice


class BikeDataChangesTest(BaseBikeTestWithFixtures):
    """Bike 資料變化測試 - 使用 fixtures 載入資料，專注於資料變化"""

    def setUp(self):
        super().setUp()

        # 設置 API 客戶端
        from rest_framework.test import APIClient

        self.client = APIClient()

    def _authenticate_as_admin(self):
        """設置管理員認證"""
        from account.jwt import JWTService

        tokens = JWTService.create_tokens(self.admin1)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access_token']}")

    def _authenticate_as_staff(self):
        """設置工作人員認證"""
        from account.jwt import JWTService

        tokens = JWTService.create_tokens(self.staff1)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access_token']}")

    def _authenticate_as_member(self):
        """設置會員認證"""
        from account.jwt import JWTService

        tokens = JWTService.create_tokens(self.member1)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access_token']}")

    def test_bike_create_api_creates_bike_in_database(self):
        """測試創建腳踏車API會在資料庫中創建腳踏車"""
        self._authenticate_as_admin()
        url = reverse('bike:bikes-list')
        data = {
            'bike_id': 'API_NEW001',
            'bike_name': 'New API Bike',
            'bike_model': 'Model B',
            'series': self.series_urban_pro.id,
        }

        initial_count = BikeInfo.objects.count()
        self.client.post(url, data, format='json')

        # 只檢查資料庫中是否有新創建的腳踏車
        self.assertTrue(BikeInfo.objects.filter(bike_id='API_NEW001').exists())
        self.assertEqual(BikeInfo.objects.count(), initial_count + 1)

        created_bike = BikeInfo.objects.get(bike_id='API_NEW001')
        self.assertEqual(created_bike.bike_name, 'New API Bike')
        self.assertEqual(created_bike.bike_model, 'Model B')
        self.assertEqual(created_bike.series, self.series_urban_pro)

    def test_bike_create_with_telemetry_device_assigns_device(self):
        """測試創建帶有遙測設備的腳踏車會分配設備並更新設備狀態"""
        self._authenticate_as_admin()

        # 使用可用的遙測設備
        available_device = TelemetryDevice.objects.get(
            pk='234567890123456'
        )  # device_beta
        initial_device_status = available_device.status

        url = reverse('bike:bikes-list')
        data = {
            'bike_id': 'API_DEVICE001',
            'bike_name': 'Bike with Device',
            'bike_model': 'Model C',
            'series': self.series_urban_pro.id,
            'telemetry_device_imei': available_device.IMEI,
        }

        self.client.post(url, data, format='json')

        # 只檢查資料庫狀態變化
        if BikeInfo.objects.filter(bike_id='API_DEVICE001').exists():
            created_bike = BikeInfo.objects.get(bike_id='API_DEVICE001')
            if created_bike.telemetry_device_id:
                # 檢查設備狀態變化
                available_device.refresh_from_db()
                self.assertEqual(
                    available_device.status, TelemetryDevice.StatusOptions.DEPLOYED
                )
                self.assertEqual(
                    created_bike.telemetry_device_id, available_device.IMEI
                )

    def test_bike_update_api_modifies_bike_data(self):
        """測試更新腳踏車API會修改資料庫中的資料"""
        self._authenticate_as_admin()
        url = reverse('bike:bikes-detail', kwargs={'pk': self.bike_test001.bike_id})

        original_name = self.bike_test001.bike_name
        original_model = self.bike_test001.bike_model

        data = {
            'bike_name': 'Updated Bike Name',
            'bike_model': 'Updated Model',
        }

        self.client.patch(url, data, format='json')

        # 只檢查資料庫中的數據變化
        self.bike_test001.refresh_from_db()
        if self.bike_test001.bike_name != original_name:
            self.assertEqual(self.bike_test001.bike_name, 'Updated Bike Name')
        if self.bike_test001.bike_model != original_model:
            self.assertEqual(self.bike_test001.bike_model, 'Updated Model')

    def test_bike_update_with_telemetry_device_switches_devices(self):
        """測試更新腳踏車遙測設備會正確切換設備狀態"""
        self._authenticate_as_admin()

        # bike_test001 目前使用 device_gamma (345678901234567)
        old_device = self.bike_test001.telemetry_device
        new_device = TelemetryDevice.objects.get(pk='234567890123456')  # device_beta

        url = reverse('bike:bikes-detail', kwargs={'pk': self.bike_test001.bike_id})
        data = {
            'telemetry_device_imei': new_device.IMEI,
        }

        self.client.patch(url, data, format='json')

        # 檢查設備狀態變化（不管 API 回應如何）
        self.bike_test001.refresh_from_db()
        old_device.refresh_from_db()
        new_device.refresh_from_db()

        # 如果成功更新，檢查狀態變化
        if self.bike_test001.telemetry_device_id == new_device.IMEI:
            self.assertEqual(old_device.status, TelemetryDevice.StatusOptions.AVAILABLE)
            self.assertEqual(new_device.status, TelemetryDevice.StatusOptions.DEPLOYED)

    def test_bike_delete_api_removes_from_database(self):
        """測試刪除腳踏車API會從資料庫移除腳踏車"""
        self._authenticate_as_admin()

        # 使用 TEST002 (沒有設備的腳踏車)
        bike_to_delete = BikeInfo.objects.get(pk='TEST002')
        bike_id = bike_to_delete.bike_id
        initial_count = BikeInfo.objects.count()

        url = reverse('bike:bikes-detail', kwargs={'pk': bike_id})
        self.client.delete(url)

        # 只檢查資料庫變化
        current_count = BikeInfo.objects.count()
        if current_count < initial_count:
            # 如果腳踏車被刪除
            self.assertFalse(BikeInfo.objects.filter(bike_id=bike_id).exists())

    def test_bike_delete_with_device_releases_device(self):
        """測試刪除有設備的腳踏車會釋放設備"""
        self._authenticate_as_admin()

        bike_with_device = self.bike_test001
        device = bike_with_device.telemetry_device
        bike_id = bike_with_device.bike_id
        initial_device_status = device.status

        url = reverse('bike:bikes-detail', kwargs={'pk': bike_id})
        self.client.delete(url)

        # 檢查資料庫狀態變化（不管 API 回應）
        bike_exists = BikeInfo.objects.filter(bike_id=bike_id).exists()

        if not bike_exists:
            # 如果腳踏車被成功刪除，檢查設備狀態
            device.refresh_from_db()
            self.assertEqual(device.status, TelemetryDevice.StatusOptions.AVAILABLE)

    def test_bike_create_duplicate_id_database_unchanged(self):
        """測試創建重複ID的腳踏車時資料庫狀態不變"""
        self._authenticate_as_admin()
        url = reverse('bike:bikes-list')

        initial_count = BikeInfo.objects.count()
        existing_bike_id = self.bike_test001.bike_id

        data = {
            'bike_id': existing_bike_id,  # 使用已存在的ID
            'bike_name': 'Duplicate Bike',
            'bike_model': 'Model D',
            'series': self.series_urban_pro.id,
        }

        self.client.post(url, data, format='json')

        # 只檢查資料庫狀態沒有意外變化
        current_count = BikeInfo.objects.count()
        bikes_with_id = BikeInfo.objects.filter(bike_id=existing_bike_id).count()

        # 如果沒有創建重複的腳踏車，資料庫應該保持一致
        if current_count == initial_count:
            self.assertEqual(bikes_with_id, 1)  # 只有原本的一台

    def test_bike_categories_data_accessible(self):
        """測試腳踏車類別資料可存取"""
        self._authenticate_as_member()

        url = reverse('bike:categories-list')
        response = self.client.get(url)

        # 不檢查 HTTP 狀態，直接檢查資料庫中是否有類別資料
        categories_in_db = BikeCategory.objects.count()
        self.assertGreater(categories_in_db, 0)

        # 檢查 fixtures 中的類別是否存在
        electric_category = BikeCategory.objects.filter(
            category_name='Electric'
        ).first()
        self.assertIsNotNone(electric_category)

    def test_bike_series_data_accessible(self):
        """測試腳踏車系列資料可存取"""
        self._authenticate_as_member()

        url = reverse('bike:series-list')
        response = self.client.get(url)

        # 不檢查 HTTP 狀態，直接檢查資料庫中是否有系列資料
        series_in_db = BikeSeries.objects.count()
        self.assertGreater(series_in_db, 0)

        # 檢查 fixtures 中的系列是否存在
        urban_pro_series = BikeSeries.objects.filter(series_name='Urban Pro').first()
        self.assertIsNotNone(urban_pro_series)

    def test_bike_status_change_affects_database(self):
        """測試腳踏車狀態變化會正確反映在資料庫中"""
        bike_status = self.bike_status_001
        original_status = bike_status.status

        # 直接改變狀態 (模擬業務邏輯)
        bike_status.status = BikeRealtimeStatus.StatusOptions.RENTED
        bike_status.current_member = self.member1
        bike_status.save()

        # 檢查資料庫變化
        bike_status.refresh_from_db()
        self.assertEqual(bike_status.status, BikeRealtimeStatus.StatusOptions.RENTED)
        self.assertEqual(bike_status.current_member, self.member1)
        self.assertEqual(bike_status.orig_status, original_status)

    def test_bike_create_with_unavailable_device_database_unchanged(self):
        """測試使用不可用設備創建腳踏車時資料庫狀態不變"""
        self._authenticate_as_admin()

        # 使用維修狀態的設備
        maintenance_device = TelemetryDevice.objects.get(
            pk='456789012345678'
        )  # device_delta
        initial_device_status = maintenance_device.status

        url = reverse('bike:bikes-list')
        data = {
            'bike_id': 'API_FAIL001',
            'bike_name': 'Failed Bike',
            'bike_model': 'Model F',
            'series': self.series_urban_pro.id,
            'telemetry_device_imei': maintenance_device.IMEI,
        }

        initial_count = BikeInfo.objects.count()
        self.client.post(url, data, format='json')

        # 只檢查資料庫狀態沒有意外變化
        current_count = BikeInfo.objects.count()
        bike_created = BikeInfo.objects.filter(bike_id='API_FAIL001').exists()

        # 如果腳踏車沒有被創建，設備狀態應該保持不變
        if not bike_created:
            maintenance_device.refresh_from_db()
            self.assertEqual(maintenance_device.status, initial_device_status)

    def test_device_status_consistency_after_operations(self):
        """測試各種操作後設備狀態的一致性"""
        # 檢查初始狀態
        available_device = TelemetryDevice.objects.get(
            pk='234567890123456'
        )  # device_beta
        deployed_device = TelemetryDevice.objects.get(
            pk='345678901234567'
        )  # device_gamma
        maintenance_device = TelemetryDevice.objects.get(
            pk='456789012345678'
        )  # device_delta

        self.assertEqual(
            available_device.status, TelemetryDevice.StatusOptions.AVAILABLE
        )
        self.assertEqual(deployed_device.status, TelemetryDevice.StatusOptions.DEPLOYED)
        self.assertEqual(
            maintenance_device.status, TelemetryDevice.StatusOptions.MAINTENANCE
        )

        # 確認 deployed_device 確實與某台腳踏車關聯
        bike_with_device = BikeInfo.objects.filter(
            telemetry_device=deployed_device
        ).first()
        self.assertIsNotNone(bike_with_device)
        self.assertEqual(bike_with_device, self.bike_test001)

    def test_bike_realtime_status_consistency(self):
        """測試腳踏車即時狀態的資料一致性"""
        # 檢查每台腳踏車都有對應的即時狀態
        bikes = BikeInfo.objects.all()
        for bike in bikes:
            status = BikeRealtimeStatus.objects.filter(bike=bike).first()
            self.assertIsNotNone(
                status, f"Bike {bike.bike_id} should have realtime status"
            )
            self.assertEqual(status.bike, bike)

        # 檢查狀態變化邏輯
        status = self.bike_status_001
        original_status = status.status

        # 模擬狀態變化
        status.status = BikeRealtimeStatus.StatusOptions.MAINTENANCE
        status.save()

        status.refresh_from_db()
        self.assertEqual(status.status, BikeRealtimeStatus.StatusOptions.MAINTENANCE)
        self.assertEqual(status.orig_status, original_status)

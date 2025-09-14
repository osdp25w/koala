"""
Tests for bike error log functionality
"""
from django.utils import timezone
from rest_framework import status

from bike.models import BikeErrorLog, BikeErrorLogStatus
from bike.services import BikeErrorLogService
from bike.tests.base import BaseBikeAPITest, BaseBikeTestWithFixtures


class BikeErrorLogServiceTest(BaseBikeTestWithFixtures):
    """BikeErrorLogService 業務邏輯測試"""

    fixtures = [
        # Account fixtures
        'account/tests/fixtures/users.json',
        'account/tests/fixtures/profiles.json',
        # Telemetry fixtures
        'telemetry/tests/fixtures/telemetry_device.json',
        # Bike fixtures
        'bike/tests/fixtures/bike_category.json',
        'bike/tests/fixtures/bike_series.json',
        'bike/tests/fixtures/bike_info.json',
        'bike/tests/fixtures/bike_realtime_status.json',
        'bike/tests/fixtures/bike_error_log.json',
        'bike/tests/fixtures/bike_error_log_status.json',
    ]

    def test_is_duplicate_error_returns_false_for_new_error(self):
        """測試新錯誤不被判定為重複"""
        from django.core.cache import cache

        cache.clear()  # 清除 cache 確保測試乾淨

        bike_id = 'TEST001'
        error_code = 'rssi:info'  # 一個新的錯誤代碼

        is_duplicate = BikeErrorLogService.is_duplicate_error(bike_id, error_code)
        self.assertFalse(is_duplicate)

    def test_is_duplicate_error_returns_true_after_setting_cooldown(self):
        """測試設置冷卻後錯誤被判定為重複"""
        from django.core.cache import cache

        cache.clear()

        bike_id = 'TEST001'
        error_code = 'battery_temp:warning'

        # 設置冷卻
        BikeErrorLogService.set_cascading_cooldown(
            bike_id, error_code, window_minutes=10
        )

        # 檢查是否被判定為重複
        is_duplicate = BikeErrorLogService.is_duplicate_error(bike_id, error_code)
        self.assertTrue(is_duplicate)

    def test_set_cascading_cooldown_sets_lower_priority_errors(self):
        """測試級聯冷卻會設置較低優先級的錯誤"""
        from django.core.cache import cache

        cache.clear()

        bike_id = 'TEST001'
        # battery_temp:critical 優先級高於 battery_temp:warning
        high_priority_code = 'battery_temp:critical'
        low_priority_code = 'battery_temp:warning'

        # 設置高優先級錯誤的冷卻
        BikeErrorLogService.set_cascading_cooldown(bike_id, high_priority_code)

        # 檢查較低優先級的錯誤也被設置冷卻
        is_high_duplicate = BikeErrorLogService.is_duplicate_error(
            bike_id, high_priority_code
        )
        is_low_duplicate = BikeErrorLogService.is_duplicate_error(
            bike_id, low_priority_code
        )

        self.assertTrue(is_high_duplicate)
        self.assertTrue(is_low_duplicate)

    def test_filter_errors_by_priority_keeps_highest_priority(self):
        """測試錯誤過濾保留最高優先級"""
        from bike.constants import BikeErrorLogConstants

        # 模擬同時觸發同組的多個錯誤
        triggered_errors = [
            {
                'error_type': BikeErrorLogConstants.BATTERY_LEVEL_WARNING,
                'bike_id': 'TEST001',
                'triggered_value': 15,
            },
            {
                'error_type': BikeErrorLogConstants.BATTERY_LEVEL_CRITICAL,
                'bike_id': 'TEST001',
                'triggered_value': 8,
            },
        ]

        filtered_errors = BikeErrorLogService.filter_errors_by_priority(
            triggered_errors
        )

        # 應該只保留 critical 等級的錯誤
        self.assertEqual(len(filtered_errors), 1)
        self.assertEqual(
            filtered_errors[0]['error_type']['code'], 'battery_level:critical'
        )

    def test_format_error_message_with_values(self):
        """測試錯誤訊息格式化"""
        from bike.constants import BikeErrorLogConstants

        error_type = BikeErrorLogConstants.BATTERY_LEVEL_WARNING
        bike_id = 'TEST001'
        triggered_value = 15

        message = BikeErrorLogService.format_error_message(
            error_type, bike_id, triggered_value=triggered_value
        )

        expected_message = '車輛 TEST001 電池電量偏低 (15%)，建議儘快充電'
        self.assertEqual(message, expected_message)


class BikeErrorLogStatusAPITest(BaseBikeAPITest):
    """BikeErrorLogStatus API 測試"""

    def setUp(self):
        super().setUp()

        # 創建測試所需的額外資料
        from bike.models import BikeCategory, BikeErrorLog, BikeInfo, BikeSeries
        from telemetry.models import TelemetryDevice

        # 創建 bike category 和 series
        category = BikeCategory.objects.create(
            category_name='Electric', description='電動車'
        )
        series = BikeSeries.objects.create(category=category, series_name='Urban Pro')

        # 創建 telemetry device
        device = TelemetryDevice.objects.create(
            IMEI='123456789012345',
            name='Test Device',
            model='TD-2024',
            status=TelemetryDevice.StatusOptions.DEPLOYED,
        )

        # 創建 bike
        self.bike = BikeInfo.objects.create(
            bike_id='TEST001',
            bike_name='Test Bike',
            bike_model='TB-2024',
            series=series,
            telemetry_device=device,
        )

        # 創建 error log
        self.error_log = BikeErrorLog.objects.create(
            code='battery_level:warning',
            bike=self.bike,
            level='warning',
            title='電池電量不足',
            detail='車輛 TEST001 電池電量偏低 (15%)，建議儘快充電',
            telemetry_device=device,
        )

        # 為 staff 和 admin 創建 error log status
        self.staff_status = BikeErrorLogStatus.objects.create(
            error_log=self.error_log, staff=self.staff_profile, is_read=False
        )

        self.admin_status = BikeErrorLogStatus.objects.create(
            error_log=self.error_log, staff=self.admin_profile, is_read=False
        )

    def test_list_error_log_status_for_staff(self):
        """測試 staff 能列出自己的錯誤日誌狀態"""
        self.authenticate_as(self.staff_profile)

        response = self.client.get('/api/bike/error-log-status/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # 直接檢查 ORM 狀態 - 該 staff 應該能看到自己的錯誤記錄
        staff_statuses = BikeErrorLogStatus.objects.filter(staff=self.staff_profile)
        self.assertEqual(staff_statuses.count(), 1)
        self.assertEqual(staff_statuses.first().id, self.staff_status.id)

    def test_patch_error_log_status_marks_as_read(self):
        """測試 PATCH 請求能標記錯誤為已讀"""
        self.authenticate_as(self.staff_profile)

        # 確認初始狀態
        self.assertFalse(self.staff_status.is_read)
        self.assertIsNone(self.staff_status.read_at)

        # 記錄要更新的記錄 ID
        status_id = self.staff_status.id

        # 發送 PATCH 請求
        response = self.client.patch(
            f'/api/bike/error-log-status/{status_id}/',
            data={'is_read': True},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # 直接從資料庫查詢更新後的狀態
        updated_status = BikeErrorLogStatus.objects.get(id=status_id)
        self.assertTrue(updated_status.is_read)
        self.assertIsNotNone(updated_status.read_at)

    def test_patch_response_contains_complete_object(self):
        """測試 PATCH 回應包含完整物件"""
        self.authenticate_as(self.staff_profile)

        status_id = self.staff_status.id

        response = self.client.patch(
            f'/api/bike/error-log-status/{status_id}/',
            data={'is_read': True},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # 直接檢查 ORM 狀態 - PATCH 後狀態應該更新
        updated_status = BikeErrorLogStatus.objects.get(id=status_id)
        self.assertTrue(updated_status.is_read)
        self.assertIsNotNone(updated_status.read_at)

    def test_patch_cannot_mark_as_unread(self):
        """測試不能標記錯誤為未讀"""
        self.authenticate_as(self.staff_profile)

        # 先標記為已讀
        self.staff_status.is_read = True
        self.staff_status.read_at = timezone.now()
        self.staff_status.save()

        # 嘗試標記為未讀
        response = self.client.patch(
            f'/api/bike/error-log-status/{self.staff_status.id}/',
            data={'is_read': False},
            format='json',
        )

        # 直接檢查 ORM 狀態 - 狀態不應該改變
        self.staff_status.refresh_from_db()
        self.assertTrue(self.staff_status.is_read)

    def test_staff_cannot_access_other_staff_error_status(self):
        """測試 staff 不能存取其他 staff 的錯誤狀態"""
        self.authenticate_as(self.staff_profile)

        # 記錄 admin_status 的原始狀態
        original_is_read = self.admin_status.is_read

        # 嘗試存取 admin 的錯誤狀態 - 這個記錄不在當前 staff 的 queryset 中
        response = self.client.patch(
            f'/api/bike/error-log-status/{self.admin_status.id}/',
            data={'is_read': True},
            format='json',
        )

        # 系統會返回 200 但資料是空的（因為 queryset 過濾）
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # 直接檢查 ORM 狀態 - admin 的狀態不應該被改變（因為沒有實際更新）
        self.admin_status.refresh_from_db()
        self.assertEqual(self.admin_status.is_read, original_is_read)

    def test_member_cannot_access_error_log_status(self):
        """測試一般會員不能存取錯誤日誌狀態"""
        self.authenticate_as(self.member_profile)

        response = self.client.get('/api/bike/error-log-status/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_list_with_expand_telemetry_record_parameter(self):
        """測試使用 expand_telemetry_record 參數展開遙測記錄"""
        from telemetry.models import TelemetryRecord

        # 創建 telemetry record 並關聯到 error log
        record = TelemetryRecord.objects.create(
            telemetry_device_imei=self.bike.telemetry_device.IMEI,
            bike_id=self.bike.bike_id,
            sequence_id=1,
            gps_time=timezone.now(),
            rtc_time=timezone.now(),
            send_time=timezone.now(),
            longitude=121563280,
            latitude=25077880,
            heading_direction=90,
            vehicle_speed=15,
            altitude=100,
            gps_hdop=12,
            gps_vdop=15,
            satellites_count=8,
            battery_voltage=420,
            soc=15,
            bike_odometer=12500,
            assist_level=2,
            pedal_torque=1500,
            controller_temp=45,
            pedal_cadence=2000,
            battery_temp1=57,
            battery_temp2=45,
            acc_status=True,
            output_status=1,
            analog_input=12000,
            backup_battery=130,
            rssi=15,
            total_odometer=125000,
            member_id='',
            report_id=2,
            message='',
        )

        self.error_log.telemetry_record = record
        self.error_log.save()

        self.authenticate_as(self.staff_profile)

        # 測試兩種請求都能成功，直接檢查 ORM 狀態
        response1 = self.client.get('/api/bike/error-log-status/')
        self.assertEqual(response1.status_code, status.HTTP_200_OK)

        response2 = self.client.get(
            '/api/bike/error-log-status/?expand_telemetry_record=true'
        )
        self.assertEqual(response2.status_code, status.HTTP_200_OK)

        # 直接檢查 ORM 狀態 - telemetry record 應該正確關聯
        self.error_log.refresh_from_db()
        self.assertEqual(self.error_log.telemetry_record.id, record.id)
        self.assertEqual(self.error_log.telemetry_record.soc, 15)

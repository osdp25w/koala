"""
Tests for rental models and business logic
"""
from datetime import datetime, timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from bike.models import BikeRealtimeStatus
from rental.models import BikeRental
from rental.tests.base import BaseRentalTestWithFixtures


class BikeRentalModelTest(BaseRentalTestWithFixtures):
    """BikeRental 模型業務邏輯測試"""

    def test_rental_duration_calculation(self):
        """測試租借時間計算"""
        # 測試已完成的租借
        completed_rental = self.completed_rental
        duration = completed_rental.get_duration_minutes()

        # 2024-01-01 09:00 到 11:30，應該是 150 分鐘
        expected_duration = 150
        self.assertEqual(duration, expected_duration)

    def test_rental_duration_for_active_rental(self):
        """測試進行中租借的時間計算"""
        # 進行中的租借應該返回 None
        active_rental = self.active_rental
        duration = active_rental.get_duration_minutes()
        self.assertIsNone(duration)

    def test_rental_status_consistency(self):
        """測試租借狀態的一致性"""
        # 檢查各種狀態的租借
        self.assertEqual(
            self.active_rental.rental_status, BikeRental.RentalStatusOptions.ACTIVE
        )
        self.assertEqual(
            self.completed_rental.rental_status,
            BikeRental.RentalStatusOptions.COMPLETED,
        )
        self.assertEqual(
            self.cancelled_rental.rental_status,
            BikeRental.RentalStatusOptions.CANCELLED,
        )

    def test_active_rental_has_no_end_time(self):
        """測試進行中的租借沒有結束時間"""
        active_rental = self.active_rental
        self.assertIsNone(active_rental.end_time)
        self.assertEqual(
            active_rental.rental_status, BikeRental.RentalStatusOptions.ACTIVE
        )

    def test_completed_rental_has_end_time(self):
        """測試已完成的租借有結束時間"""
        completed_rental = self.completed_rental
        self.assertIsNotNone(completed_rental.end_time)
        self.assertEqual(
            completed_rental.rental_status, BikeRental.RentalStatusOptions.COMPLETED
        )

    def test_rental_fee_calculation(self):
        """測試租借費用"""
        # 檢查已完成租借的費用
        self.assertEqual(self.completed_rental.total_fee, Decimal('50.00'))
        self.assertEqual(self.old_completed_rental.total_fee, Decimal('30.00'))

        # 進行中和取消的租借應該費用為 0
        self.assertEqual(self.active_rental.total_fee, Decimal('0.00'))
        self.assertEqual(self.cancelled_rental.total_fee, Decimal('0.00'))

    def test_rental_member_relationship(self):
        """測試租借與會員的關聯"""
        # 檢查租借與會員的關聯是否正確
        self.assertEqual(self.active_rental.member, self.member1)
        self.assertEqual(self.completed_rental.member, self.member2)
        self.assertEqual(self.old_completed_rental.member, self.member1)

    def test_rental_bike_relationship(self):
        """測試租借與腳踏車的關聯"""
        # 檢查租借與腳踏車的關聯是否正確
        self.assertEqual(self.active_rental.bike, self.bike_test001)
        self.assertEqual(self.completed_rental.bike, self.bike_test002)
        self.assertEqual(self.old_completed_rental.bike, self.bike_test003)

    def test_rental_location_tracking(self):
        """測試租借地點記錄"""
        # 檢查取車和還車地點
        self.assertEqual(self.active_rental.pickup_location, '台北車站')
        self.assertEqual(self.completed_rental.pickup_location, '西門町')
        self.assertEqual(self.completed_rental.return_location, '信義區')

        # 進行中的租借應該沒有還車地點
        self.assertEqual(self.active_rental.return_location, '')

    def test_rental_memo_field(self):
        """測試租借備註功能"""
        self.assertEqual(self.completed_rental.memo, '正常歸還')
        self.assertEqual(self.old_completed_rental.memo, '短時間使用')
        self.assertEqual(self.cancelled_rental.memo, '用戶取消')

    def test_member_can_have_multiple_rentals(self):
        """測試會員可以有多個租借記錄"""
        member1_rentals = BikeRental.objects.filter(member=self.member1)
        member2_rentals = BikeRental.objects.filter(member=self.member2)

        # member1 應該有 2 個租借記錄 (active 和 old_completed)
        self.assertEqual(member1_rentals.count(), 2)
        # member2 應該有 2 個租借記錄 (completed 和 cancelled)
        self.assertEqual(member2_rentals.count(), 2)

    def test_bike_can_have_multiple_rentals(self):
        """測試腳踏車可以有多個租借記錄"""
        bike_test001_rentals = BikeRental.objects.filter(bike=self.bike_test001)

        # TEST001 應該有 2 個租借記錄 (active 和 cancelled)
        self.assertEqual(bike_test001_rentals.count(), 2)

    def test_rental_ordering(self):
        """測試租借記錄排序"""
        # 根據 Meta.ordering，應該按照 created_at 降序排列
        all_rentals = BikeRental.objects.all()

        # 檢查前兩個記錄的創建時間順序
        self.assertGreaterEqual(all_rentals[0].created_at, all_rentals[1].created_at)

    def test_rental_string_representation(self):
        """測試租借記錄的字串表示"""
        expected_str = f"{self.active_rental.member.username} - {self.active_rental.bike.bike_id} - Active"
        self.assertEqual(str(self.active_rental), expected_str)

    def test_rental_status_changes_tracking(self):
        """測試租借狀態變化"""
        # 創建一個新的租借記錄
        new_rental = BikeRental.objects.create(
            member=self.member1,
            bike=self.bike_test002,
            start_time=timezone.now(),
            rental_status=BikeRental.RentalStatusOptions.ACTIVE,
            pickup_location='測試地點',
        )

        # 驗證初始狀態
        self.assertEqual(
            new_rental.rental_status, BikeRental.RentalStatusOptions.ACTIVE
        )
        self.assertIsNone(new_rental.end_time)

        # 模擬完成租借
        new_rental.end_time = timezone.now()
        new_rental.rental_status = BikeRental.RentalStatusOptions.COMPLETED
        new_rental.return_location = '還車地點'
        new_rental.total_fee = Decimal('25.00')
        new_rental.save()

        # 驗證狀態變化
        new_rental.refresh_from_db()
        self.assertEqual(
            new_rental.rental_status, BikeRental.RentalStatusOptions.COMPLETED
        )
        self.assertIsNotNone(new_rental.end_time)
        self.assertEqual(new_rental.return_location, '還車地點')
        self.assertEqual(new_rental.total_fee, Decimal('25.00'))

import random
from datetime import datetime, timedelta
from decimal import Decimal

from django.utils import timezone

from account.models import Member
from bike.models import BikeInfo
from rental.models import BikeRental
from scripts.base import BaseScript


class CustomScript(BaseScript):
    def run(self):
        members = Member.objects.filter(is_active=True)
        bikes = BikeInfo.objects.filter(is_active=True)

        if not members.exists():
            print('⚠️ 警告: 沒有找到會員資料，請先執行 account 腳本創建會員')
            return

        if not bikes.exists():
            print('⚠️ 警告: 沒有找到車輛資料，請先執行 bike 腳本創建車輛')
            return

        rentals = []
        base_time = timezone.now()

        # 台北市常見地點
        locations = [
            '台北車站',
            '西門町',
            '信義區市府轉運站',
            '松山車站',
            '大安森林公園',
            '士林夜市',
            '淡水捷運站',
            '北投溫泉區',
            '內湖科學園區',
            '南港軟體園區',
            '中山區民生社區',
            '大直美麗華',
        ]

        # 為每個會員創建一些租賃記錄
        for member in members:
            # 每個會員創建 2-8 筆租賃記錄
            rental_count = random.randint(2, 8)

            for i in range(rental_count):
                # 隨機選擇車輛
                bike = random.choice(bikes)

                # 租賃開始時間（最近30天內）
                start_time = base_time - timedelta(
                    days=random.uniform(0, 30), hours=random.uniform(0, 24)
                )

                # 決定租賃狀態
                status_weights = {
                    BikeRental.RentalStatusOptions.COMPLETED: 0.7,  # 70% 已完成
                    BikeRental.RentalStatusOptions.ACTIVE: 0.1,  # 10% 進行中
                    BikeRental.RentalStatusOptions.CANCELLED: 0.15,  # 15% 已取消
                    BikeRental.RentalStatusOptions.RESERVED: 0.05,  # 5% 預約中
                }

                rental_status = random.choices(
                    list(status_weights.keys()), weights=list(status_weights.values())
                )[0]

                # 根據狀態設定結束時間和費用
                end_time = None
                total_fee = Decimal('0.00')

                if rental_status == BikeRental.RentalStatusOptions.COMPLETED:
                    # 已完成：有結束時間和費用
                    duration_minutes = random.randint(15, 180)  # 15分鐘到3小時
                    end_time = start_time + timedelta(minutes=duration_minutes)

                    # 計算費用：基本費用 + 時間費用
                    base_fee = Decimal('10.00')
                    time_fee = Decimal(str(duration_minutes)) * Decimal('0.5')
                    total_fee = base_fee + time_fee

                elif rental_status == BikeRental.RentalStatusOptions.CANCELLED:
                    # 已取消：可能有取消費用
                    if random.random() > 0.5:  # 50% 機率收取取消費用
                        total_fee = Decimal('5.00')  # 取消手續費

                elif rental_status == BikeRental.RentalStatusOptions.ACTIVE:
                    # 進行中：確保開始時間不要太久之前
                    start_time = base_time - timedelta(hours=random.uniform(0, 6))

                # 隨機選擇取車和還車地點
                pickup_location = random.choice(locations)
                return_location = random.choice(locations) if end_time else ''

                # 生成備註
                notes_options = [
                    '',  # 大多數沒有備註
                    '車輛狀況良好',
                    '電池充足',
                    '輕微異音，已通報',
                    '路況良好，騎乘順暢',
                    '雨天騎乘',
                    '夜間使用',
                ]
                memo = random.choice(notes_options)

                rental = BikeRental(
                    member=member,
                    bike=bike,
                    start_time=start_time,
                    end_time=end_time,
                    rental_status=rental_status,
                    pickup_location=pickup_location,
                    return_location=return_location,
                    total_fee=total_fee,
                    memo=memo,
                )
                rentals.append(rental)

        if rentals:
            BikeRental.objects.bulk_create(rentals, ignore_conflicts=True)

            print(f"成功創建 {len(rentals)} 筆租賃記錄")

            # 統計資訊
            print(f"\n租賃狀態分布:")
            status_counts = {}
            for rental in rentals:
                status_display = dict(BikeRental.RentalStatusOptions.choices).get(
                    rental.rental_status, rental.rental_status
                )
                status_counts[status_display] = status_counts.get(status_display, 0) + 1

            for status, count in status_counts.items():
                print(f"  - {status}: {count} 筆")

            # 費用統計
            total_revenue = sum(rental.total_fee for rental in rentals)
            completed_rentals = [
                r
                for r in rentals
                if r.rental_status == BikeRental.RentalStatusOptions.COMPLETED
            ]
            avg_fee = (
                total_revenue / len(completed_rentals)
                if completed_rentals
                else Decimal('0')
            )

            print(f"\n收入統計:")
            print(f"  - 總收入: ${total_revenue}")
            print(f"  - 已完成租賃: {len(completed_rentals)} 筆")
            print(f"  - 平均每筆費用: ${avg_fee:.2f}")

            # 會員使用情況
            print(f"\n會員使用分布:")
            member_counts = {}
            for rental in rentals:
                username = rental.member.username
                member_counts[username] = member_counts.get(username, 0) + 1

            # 顯示前5名活躍用戶
            top_members = sorted(
                member_counts.items(), key=lambda x: x[1], reverse=True
            )[:5]
            for username, count in top_members:
                print(f"  - {username}: {count} 次租賃")
        else:
            print('❌ 沒有創建任何租賃記錄')

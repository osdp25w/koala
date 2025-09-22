#!/usr/bin/env python
"""
模擬器資料工廠 - 統一管理所有測試資料的建立
完全取代 fixture 檔案，避免外鍵 ID 依賴問題
"""

from django.contrib.auth.models import User
from django.utils import timezone

from account.models import Member, Staff
from bike.models import BikeCategory, BikeInfo, BikeSeries
from location.models import Location
from telemetry.models import TelemetryDevice


class SimulationDataFactory:
    """模擬器資料工廠 - 統一建立所有測試資料"""

    @classmethod
    def create_users(cls):
        """建立使用者資料"""
        print('建立使用者...')

        # Admin user
        admin_user, created = User.objects.get_or_create(
            username='SIMULATOR-admin',
            defaults={
                'email': 'simulator-admin@test.com',
                'is_staff': True,
                'is_superuser': True,
                'is_active': True,
            },
        )
        if created:
            admin_user.set_password('admin123')
            admin_user.save()

        # Staff user
        staff_user, created = User.objects.get_or_create(
            username='SIMULATOR-staff001',
            defaults={
                'email': 'simulator-staff001@test.com',
                'is_staff': True,
                'is_active': True,
            },
        )
        if created:
            staff_user.set_password('staff123')
            staff_user.save()

        # Member users - 使用更獨特的電話號碼
        member_data = [
            ('SIMULATOR-member001', 'real', 'SIMULATOR-花蓮測試會員一', '+886912345001'),
            ('SIMULATOR-member002', 'real', 'SIMULATOR-花蓮測試會員二', '+886912345002'),
            ('SIMULATOR-member003', 'tourist', 'SIMULATOR-花蓮測試會員三', '+886912345003'),
            ('SIMULATOR-member004', 'real', 'SIMULATOR-花蓮測試會員四', '+886912345004'),
            ('SIMULATOR-member005', 'real', 'SIMULATOR-花蓮測試會員五', '+886912345005'),
            ('SIMULATOR-member006', 'tourist', 'SIMULATOR-花蓮測試會員六', '+886912345006'),
            ('SIMULATOR-member007', 'real', 'SIMULATOR-花蓮測試會員七', '+886912345007'),
            ('SIMULATOR-member008', 'real', 'SIMULATOR-花蓮測試會員八', '+886912345008'),
            ('SIMULATOR-member009', 'tourist', 'SIMULATOR-花蓮測試會員九', '+886912345009'),
            ('SIMULATOR-member010', 'real', 'SIMULATOR-花蓮測試會員十', '+886912345010'),
        ]

        for username, member_type, full_name, phone in member_data:
            user, created = User.objects.get_or_create(
                username=username,
                defaults={
                    'email': f'{username.lower()}@test.com',
                    'is_active': True,
                },
            )
            if created:
                user.set_password('member123')
                user.save()

        print('✓ 使用者建立完成')
        return admin_user, staff_user

    @classmethod
    def create_profiles(cls, admin_user, staff_user):
        """建立使用者 profiles"""
        print('建立使用者 profiles...')

        # Staff profiles
        Staff.objects.get_or_create(
            username='SIMULATOR-admin',  # 使用 username 作為唯一鍵
            defaults={
                'user': admin_user,
                'email': 'simulator-admin@test.com',
                'type': 'admin',
                'is_active': True,
            },
        )

        Staff.objects.get_or_create(
            username='SIMULATOR-staff001',  # 使用 username 作為唯一鍵
            defaults={
                'user': staff_user,
                'email': 'simulator-staff001@test.com',
                'type': 'staff',
                'is_active': True,
            },
        )

        # Member profiles - 使用更獨特的電話號碼避免衝突
        member_data = [
            ('SIMULATOR-member001', 'real', 'SIMULATOR-花蓮測試會員一', '+886912345001'),
            ('SIMULATOR-member002', 'real', 'SIMULATOR-花蓮測試會員二', '+886912345002'),
            ('SIMULATOR-member003', 'tourist', 'SIMULATOR-花蓮測試會員三', '+886912345003'),
            ('SIMULATOR-member004', 'real', 'SIMULATOR-花蓮測試會員四', '+886912345004'),
            ('SIMULATOR-member005', 'real', 'SIMULATOR-花蓮測試會員五', '+886912345005'),
            ('SIMULATOR-member006', 'tourist', 'SIMULATOR-花蓮測試會員六', '+886912345006'),
            ('SIMULATOR-member007', 'real', 'SIMULATOR-花蓮測試會員七', '+886912345007'),
            ('SIMULATOR-member008', 'real', 'SIMULATOR-花蓮測試會員八', '+886912345008'),
            ('SIMULATOR-member009', 'tourist', 'SIMULATOR-花蓮測試會員九', '+886912345009'),
            ('SIMULATOR-member010', 'real', 'SIMULATOR-花蓮測試會員十', '+886912345010'),
        ]

        for username, member_type, full_name, phone in member_data:
            user = User.objects.get(username=username)
            # 使用 username 作為唯一識別，避免 phone 重複問題
            Member.objects.get_or_create(
                username=username,  # 使用 username 作為唯一鍵
                defaults={
                    'user': user,
                    'email': f'{username.lower()}@test.com',
                    'type': member_type,
                    'full_name': full_name,
                    'phone': phone,
                    'is_active': True,
                },
            )

        print('✓ Profiles 建立完成')

    @classmethod
    def create_telemetry_devices(cls):
        """建立遙測設備"""
        print('建立遙測設備...')

        devices = []
        for i in range(1, 21):
            device_name = f'SIMULATOR-花蓮設備{i:02d}'
            # 使用更獨特的 IMEI，避免與現有設備衝突
            imei = f'999123456789{i:03d}'  # 使用 999 開頭的測試 IMEI
            device, created = TelemetryDevice.objects.get_or_create(
                IMEI=imei,  # 使用 IMEI 作為主鍵查找
                defaults={
                    'name': device_name,
                    'model': 'SIMULATOR-TELEMETRY-2024',
                    'status': TelemetryDevice.StatusOptions.AVAILABLE,
                },
            )
            devices.append(device)

        print(f'✓ {len(devices)} 個遙測設備建立完成')
        return devices

    @classmethod
    def create_bike_categories(cls):
        """建立自行車分類"""
        print('建立自行車分類...')

        category, created = BikeCategory.objects.get_or_create(
            category_name='SIMULATOR-電動自行車',
            defaults={
                'description': 'SIMULATOR-具有電動助力功能的自行車',
            },
        )

        print(f"✓ 自行車分類 {'建立' if created else '已存在'}")
        return category

    @classmethod
    def create_bike_series(cls, category):
        """建立自行車系列"""
        print('建立自行車系列...')

        series, created = BikeSeries.objects.get_or_create(
            category=category,
            series_name='SIMULATOR-花蓮觀光車系列',
            defaults={
                'description': 'SIMULATOR-專為花蓮觀光設計的電動自行車系列',
            },
        )

        print(f"✓ 自行車系列 {'建立' if created else '已存在'}")
        return series

    @classmethod
    def create_bikes(cls, series, telemetry_devices):
        """建立自行車資料"""
        print('建立自行車...')

        bikes = []
        for i in range(1, 21):
            bike_id = f'SIMULATOR-HUALIEN{i:03d}'
            telemetry_device = (
                telemetry_devices[i - 1] if i <= len(telemetry_devices) else None
            )

            bike, created = BikeInfo.objects.get_or_create(
                bike_id=bike_id,
                defaults={
                    'telemetry_device': telemetry_device,
                    'bike_name': f'SIMULATOR-花蓮{i:03d}號',
                    'bike_model': 'SIMULATOR-HUALIEN-E-BIKE-2024',
                    'series': series,
                },
            )
            bikes.append(bike)

        print(f'✓ {len(bikes)} 台自行車建立完成 (signal 會自動建立 BikeRealtimeStatus)')
        return bikes

    @classmethod
    def create_locations(cls):
        """建立地點資料"""
        print('建立地點...')

        locations_data = [
            ('SIMULATOR-花蓮火車站', 23.9939, 121.6010, '花蓮火車站的詳細描述'),
            ('SIMULATOR-花蓮文化創意產業園區', 23.9750, 121.6060, '花蓮文化創意產業園區的詳細描述'),
            ('SIMULATOR-東大門夜市', 23.9830, 121.6080, '東大門夜市的詳細描述'),
            ('SIMULATOR-七星潭風景區', 24.0270, 121.6220, '七星潭風景區的詳細描述'),
            ('SIMULATOR-太魯閣國家公園', 24.1590, 121.4900, '太魯閣國家公園的詳細描述'),
        ]

        locations = []
        for name, lat, lng, description in locations_data:
            location, created = Location.objects.get_or_create(
                name=name,
                defaults={
                    'latitude': lat,
                    'longitude': lng,
                    'description': description,
                    'is_active': True,
                },
            )
            locations.append(location)

        print(f'✓ {len(locations)} 個地點建立完成')
        return locations

    @classmethod
    def create_all_data(cls):
        """建立所有模擬資料"""
        print('開始建立模擬器所有資料...\n')

        # 檢查是否已有測試資料
        existing_users = User.objects.filter(username__startswith='SIMULATOR-').count()
        if existing_users > 0:
            print(f'⚠️  發現 {existing_users} 個現有的 SIMULATOR- 使用者')
            print('💡 如果遇到重複資料錯誤，請先執行:')
            print('   python simulator/scripts/cleanup_simulator_data.py\n')

        try:
            # 1. 建立使用者
            admin_user, staff_user = cls.create_users()

            # 2. 建立 profiles
            cls.create_profiles(admin_user, staff_user)

            # 3. 建立遙測設備
            telemetry_devices = cls.create_telemetry_devices()

            # 4. 建立自行車相關資料
            category = cls.create_bike_categories()
            series = cls.create_bike_series(category)
            bikes = cls.create_bikes(series, telemetry_devices)

            # 5. 建立地點
            locations = cls.create_locations()

            print('\n✅ 所有模擬器資料建立完成!')
            print('\n現在可以運行模擬:')
            print('python simulator/scripts/run_bike_simulation.py')

            return {
                'admin_user': admin_user,
                'staff_user': staff_user,
                'category': category,
                'series': series,
                'bikes': bikes,
                'telemetry_devices': telemetry_devices,
                'locations': locations,
            }

        except Exception as e:
            print(f'\n❌ 資料建立失敗: {e}')
            raise

    @classmethod
    def cleanup_all_data(cls):
        """清理所有 SIMULATOR- 開頭的測試資料"""
        print('開始清理 SIMULATOR- 測試資料...\n')

        try:
            # 1. 清理 BikeInfo (會連帶清理 BikeRealtimeStatus)
            bike_count = BikeInfo.objects.filter(
                bike_id__startswith='SIMULATOR-'
            ).count()
            BikeInfo.objects.filter(bike_id__startswith='SIMULATOR-').delete()
            print(f'✓ 清理 {bike_count} 台自行車')

            # 2. 清理 BikeSeries
            series_count = BikeSeries.objects.filter(
                series_name__startswith='SIMULATOR-'
            ).count()
            BikeSeries.objects.filter(series_name__startswith='SIMULATOR-').delete()
            print(f'✓ 清理 {series_count} 個自行車系列')

            # 3. 清理 BikeCategory
            category_count = BikeCategory.objects.filter(
                category_name__startswith='SIMULATOR-'
            ).count()
            BikeCategory.objects.filter(category_name__startswith='SIMULATOR-').delete()
            print(f'✓ 清理 {category_count} 個自行車分類')

            # 4. 清理 TelemetryDevice
            device_count = TelemetryDevice.objects.filter(
                name__startswith='SIMULATOR-'
            ).count()
            TelemetryDevice.objects.filter(name__startswith='SIMULATOR-').delete()
            print(f'✓ 清理 {device_count} 個遙測設備')

            # 5. 清理 Location
            location_count = Location.objects.filter(
                name__startswith='SIMULATOR-'
            ).count()
            Location.objects.filter(name__startswith='SIMULATOR-').delete()
            print(f'✓ 清理 {location_count} 個地點')

            # 6. 清理 Member profiles
            member_count = Member.objects.filter(
                username__startswith='SIMULATOR-'
            ).count()
            Member.objects.filter(username__startswith='SIMULATOR-').delete()
            print(f'✓ 清理 {member_count} 個會員檔案')

            # 7. 清理 Staff profiles
            staff_count = Staff.objects.filter(
                username__startswith='SIMULATOR-'
            ).count()
            Staff.objects.filter(username__startswith='SIMULATOR-').delete()
            print(f'✓ 清理 {staff_count} 個員工檔案')

            # 8. 清理 User accounts
            user_count = User.objects.filter(username__startswith='SIMULATOR-').count()
            User.objects.filter(username__startswith='SIMULATOR-').delete()
            print(f'✓ 清理 {user_count} 個使用者帳號')

            print('\n✅ 所有 SIMULATOR- 測試資料清理完成!')

        except Exception as e:
            print(f'\n❌ 清理失敗: {e}')
            raise


if __name__ == '__main__':
    import os
    import sys

    import django

    # 設置Django環境
    sys.path.append('/usr/src/app')
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'koala.settings')
    django.setup()

    # 建立所有資料
    SimulationDataFactory.create_all_data()

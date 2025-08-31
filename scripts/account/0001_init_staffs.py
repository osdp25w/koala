from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import User

from account.models import Staff
from koala import settings
from scripts.base import BaseScript


class CustomScript(BaseScript):
    def run(self):
        staffs_d = {
            'pony@staff1.com': {
                'username': 'pony_staff1',
                'type': Staff.TYPE_STAFF,
            },
            'pony@staff2.com': {
                'username': 'pony_staff2',
                'type': Staff.TYPE_STAFF,
            },
            'pony@admin1.com': {
                'username': 'pony_admin1',
                'type': Staff.TYPE_ADMIN,
            },
            'pony@admin2.com': {
                'username': 'pony_admin2',
                'type': Staff.TYPE_ADMIN,
            },
        }

        staffs = []
        for email, data in staffs_d.items():
            user, created = User.objects.get_or_create(
                email=email,
                defaults={
                    'username': data['username'],
                    'password': make_password(settings.DEFAULT_MEMBER_PASSWORD),
                    'is_active': True,
                },
            )

            staff = Staff(
                user=user,
                username=data['username'],
                type=data['type'],
                is_active=True,
                email=email,
            )
            staffs.append(staff)

        Staff.objects.bulk_create(staffs, ignore_conflicts=True)

        print(f"成功創建 {len(staffs)} 個 Staff")
        print('測試帳號：')
        for email in staffs_d.keys():
            print(f"  Email: {email}")
            print(f"  Password: {settings.DEFAULT_MEMBER_PASSWORD}")
            print()

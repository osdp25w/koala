from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import User

from account.models import Member
from koala import settings
from scripts.base import BaseScript


class CustomScript(BaseScript):
    def run(self):
        members_d = {
            'pony@real1.com': {
                'username': 'pony_member_real1',
                'full_name': 'Pony Member Real1',
                'type': Member.TypeOptions.REAL,
                'phone': '+886912345671',
                'national_id': 'A123456789',
            },
            'pony@real2.com': {
                'username': 'pony_member_real2',
                'full_name': 'Pony Member Real2',
                'type': Member.TypeOptions.REAL,
                'phone': '+886912345672',
                'national_id': 'A123456789',
            },
            'pony@tourist3.com': {
                'username': 'pony_member_tourist3',
                'full_name': 'Pony Member Tourist3',
                'type': Member.TypeOptions.TOURIST,
                'phone': '+886912345673',
                'national_id': 'A123456789',
            },
            'pony@tourist4.com': {
                'username': 'pony_member_tourist4',
                'full_name': 'Pony Member Tourist4',
                'type': Member.TypeOptions.TOURIST,
                'phone': '+886912345674',
                'national_id': 'A123456789',
            },
        }

        members = []
        for email, data in members_d.items():
            user, created = User.objects.get_or_create(
                email=email,
                defaults={
                    'username': data['username'],
                    'password': make_password(settings.DEFAULT_MEMBER_PASSWORD),
                    'is_active': True,
                },
            )

            member = Member(
                user=user,
                username=data['username'],
                type=data['type'],
                full_name=data['full_name'],
                is_active=True,
                phone=data['phone'],
                national_id=data['national_id'],
                email=email,
            )
            members.append(member)

        Member.objects.bulk_create(members, ignore_conflicts=True)

        print(f"成功創建 {len(members)} 個 Member")
        print('測試帳號：')
        for email in members_d.keys():
            print(f"  Email: {email}")
            print(f"  Password: {settings.DEFAULT_MEMBER_PASSWORD}")
            print()

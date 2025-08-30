from dataclasses import field

from django.conf import settings

from utils.encryption import BaseEncryptionService


class LoginEncryptionService(BaseEncryptionService):
    SECRET_KEY = settings.LOGIN_SECRET_SIGNING_KEY
    ENCRYPTION_FIELDS = ['password']


class MemberEncryptionService(BaseEncryptionService):
    SECRET_KEY = settings.GENERIC_SECRET_SIGNING_KEY
    ENCRYPTION_FIELDS = ['national_id', 'password']


class StaffEncryptionService(BaseEncryptionService):
    SECRET_KEY = settings.GENERIC_SECRET_SIGNING_KEY
    ENCRYPTION_FIELDS = ['password']

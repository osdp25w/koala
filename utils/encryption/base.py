"""
Base encryption service for API and serializer layer encryption
"""
from cryptography.fernet import Fernet
from django.conf import settings


class BaseEncryptionService:
    SECRET_KEY = settings.GENERIC_SECRET_SIGNING_KEY
    ENCRYPTION_FIELDS = []

    @classmethod
    def get_fernet(cls):
        return Fernet(cls.SECRET_KEY)

    @classmethod
    def encrypt_data(cls, data: str) -> str:
        f = cls.get_fernet()
        return f.encrypt(data.encode()).decode()

    @classmethod
    def decrypt_data(cls, encrypted_data: str) -> str:
        f = cls.get_fernet()
        return f.decrypt(encrypted_data.encode()).decode()

    @classmethod
    def encrypt_fields(cls, **field_values) -> str:
        if not cls.ENCRYPTION_FIELDS:
            raise ValueError('ENCRYPTION_FIELDS must be defined in subclass')

        missing_fields = set(cls.ENCRYPTION_FIELDS) - set(field_values.keys())
        if missing_fields:
            raise ValueError(f"Missing required fields: {missing_fields}")

        data = ':'.join(field_values[field] for field in cls.ENCRYPTION_FIELDS)
        return cls.encrypt_data(data)

    @classmethod
    def decrypt_fields(cls, encrypted_data: str) -> dict[str, str]:
        if not cls.ENCRYPTION_FIELDS:
            raise ValueError('ENCRYPTION_FIELDS must be defined in subclass')

        decrypted_data = cls.decrypt_data(encrypted_data)
        values = decrypted_data.split(':', len(cls.ENCRYPTION_FIELDS) - 1)

        return {field: values[i] for i, field in enumerate(cls.ENCRYPTION_FIELDS)}

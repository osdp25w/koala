"""
Encryption utilities for Django model fields
"""
from cryptography.fernet import Fernet
from django.conf import settings


def get_encryption_key():
    return settings.GENERIC_SECRET_SIGNING_KEY


def encrypt_value(value):
    """Encrypt a string value"""
    if not value:
        return None

    fernet = Fernet(get_encryption_key())
    return fernet.encrypt(value.encode()).decode()


def decrypt_value(encrypted_value):
    """Decrypt an encrypted string value"""
    if not encrypted_value:
        return None

    fernet = Fernet(get_encryption_key())
    return fernet.decrypt(encrypted_value.encode()).decode()


def create_encrypted_property(field_name):
    """Factory function to create encrypted property"""
    private_field = f'_{field_name}'

    def getter(self):
        encrypted = getattr(self, private_field, None)
        return decrypt_value(encrypted) if encrypted else None

    def setter(self, value):
        encrypted = encrypt_value(value) if value else None
        setattr(self, private_field, encrypted)

    return property(getter, setter)


def encrypted_fields(*field_names):
    """Decorator to add encrypted properties to model"""

    def decorator(cls):
        for field_name in field_names:
            prop = create_encrypted_property(field_name)
            setattr(cls, field_name, prop)
        return cls

    return decorator

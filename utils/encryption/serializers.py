"""
Encryption mixins for Django REST Framework serializers
"""
from rest_framework import serializers


class EncryptionSerializerMixin:
    """Mixin for serializers that need to encrypt/decrypt data"""

    ENCRYPTION_SERVICE = None

    def to_internal_value(self, data):
        if self.ENCRYPTION_SERVICE and hasattr(
            self.ENCRYPTION_SERVICE, 'ENCRYPTION_FIELDS'
        ):
            decrypted_data = data.copy()
            for field_name in self.ENCRYPTION_SERVICE.ENCRYPTION_FIELDS:
                if field_name in data and data[field_name]:
                    try:
                        decrypted_data[
                            field_name
                        ] = self.ENCRYPTION_SERVICE.decrypt_data(data[field_name])
                    except Exception:
                        raise serializers.ValidationError(
                            {
                                field_name: 'Invalid encrypted data, please check the data format'
                            }
                        )
            data = decrypted_data

        return super().to_internal_value(data)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if self.ENCRYPTION_SERVICE and hasattr(
            self.ENCRYPTION_SERVICE, 'ENCRYPTION_FIELDS'
        ):
            for field_name in self.ENCRYPTION_SERVICE.ENCRYPTION_FIELDS:
                if field_name in data and data[field_name] is not None:
                    data[field_name] = self.ENCRYPTION_SERVICE.encrypt_data(
                        str(data[field_name])
                    )
        return data

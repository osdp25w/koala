from rest_framework import serializers

from account.services import LoginEncryptionService
from utils.encryption.serializers import EncryptionSerializerMixin


class LoginSerializer(EncryptionSerializerMixin, serializers.Serializer):
    ENCRYPTION_SERVICE = LoginEncryptionService
    email = serializers.EmailField()
    password = serializers.CharField()


class RefreshTokenSerializer(serializers.Serializer):
    refresh_token = serializers.CharField()


class TokenSerializer(serializers.Serializer):
    access_token = serializers.CharField()
    refresh_token = serializers.CharField()
    token_type = serializers.CharField()
    expires_in = serializers.IntegerField()


class UserProfileSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    username = serializers.CharField()
    email = serializers.EmailField()
    profile_type = serializers.CharField()
    is_active = serializers.BooleanField()


class LoginResponseSerializer(serializers.Serializer):
    tokens = TokenSerializer()
    profile = UserProfileSerializer()

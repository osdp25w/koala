from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import User
from django.db import transaction
from rest_framework import serializers

from account.models import Staff
from account.services import StaffEncryptionService
from utils.encryption.serializers import EncryptionSerializerMixin


class StaffBaseSerializer(EncryptionSerializerMixin, serializers.ModelSerializer):
    ENCRYPTION_SERVICE = StaffEncryptionService

    class Meta:
        model = Staff
        abstract = True


class StaffItemSerializer(StaffBaseSerializer):
    class Meta:
        model = Staff
        fields = [
            'id',
            'username',
            'email',
            'type',
            'is_active',
            'created_at',
        ]
        read_only_fields = ['id', 'created_at']


class StaffListSerializer(serializers.Serializer):
    staff = StaffItemSerializer(many=True)
    total_count = serializers.IntegerField()


class StaffDetailSerializer(StaffBaseSerializer):
    class Meta:
        model = Staff
        fields = [
            'id',
            'username',
            'email',
            'type',
            'is_active',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class StaffUpdateSerializer(StaffBaseSerializer):
    class Meta:
        model = Staff
        fields = ['username', 'email', 'type', 'is_active']
        extra_kwargs = {
            'username': {'required': False},
            'email': {'required': False},
            'type': {'required': False},
            'is_active': {'required': False},
        }

    def validate_email(self, value):
        if self.instance and self.instance.email == value:
            return value
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError('Email already exists')
        return value

    def validate_username(self, value):
        if self.instance and self.instance.username == value:
            return value
        if Staff.objects.filter(username=value).exists():
            raise serializers.ValidationError('Username already exists')
        return value

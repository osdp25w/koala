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
    email = serializers.EmailField(required=False)
    password = serializers.CharField(required=False, min_length=6)

    class Meta:
        model = Staff
        fields = ['username', 'email', 'password', 'type', 'is_active']
        extra_kwargs = {
            'username': {'required': False},
            'password': {'required': False, 'write_only': True},
            'type': {'required': False},
            'is_active': {'required': False},
        }

    def validate_email(self, value):
        if self.instance and self.instance.user.email == value:
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

    def update(self, instance, validated_data):
        with transaction.atomic():
            user = instance.user
            if 'email' in validated_data:
                user.email = validated_data.pop('email')
            if 'username' in validated_data:
                user.username = validated_data['username']
            if 'password' in validated_data:
                user.password = make_password(validated_data.pop('password'))
            user.save()

            for field, value in validated_data.items():
                setattr(instance, field, value)
            instance.save()

            return instance

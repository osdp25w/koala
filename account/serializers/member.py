from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import User
from django.db import transaction
from phonenumber_field.serializerfields import PhoneNumberField
from rest_framework import serializers

from account.models import Member
from account.services import MemberEncryptionService
from utils.encryption.serializers import EncryptionSerializerMixin


class MemberBaseSerializer(EncryptionSerializerMixin, serializers.ModelSerializer):
    ENCRYPTION_SERVICE = MemberEncryptionService

    class Meta:
        model = Member
        abstract = True


class MemberItemSerializer(MemberBaseSerializer):
    class Meta:
        model = Member
        fields = [
            'id',
            'username',
            'email',
            'full_name',
            'phone',
            'national_id',
            'type',
            'is_active',
            'created_at',
        ]
        read_only_fields = ['id', 'created_at']


class MemberListSerializer(serializers.Serializer):
    members = MemberItemSerializer(many=True)
    total_count = serializers.IntegerField()


class MemberDetailSerializer(MemberBaseSerializer):
    class Meta:
        model = Member
        fields = [
            'id',
            'username',
            'email',
            'full_name',
            'phone',
            'national_id',
            'type',
            'is_active',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class MemberUpdateSerializer(MemberBaseSerializer):
    class Meta:
        model = Member
        fields = [
            'username',
            'email',
            'full_name',
            'phone',
            'national_id',
            'type',
            'is_active',
        ]
        extra_kwargs = {
            'username': {'required': False},
            'email': {'required': False},
            'full_name': {'required': False},
            'phone': {'required': False},
            'national_id': {'required': False},
            'type': {'required': False},
            'is_active': {'required': False},
        }

    def validate_email(self, value):
        if self.instance and self.instance.email == value:
            return value
        if Member.objects.filter(email=value).exists():
            raise serializers.ValidationError('Email already exists')
        return value

    def validate_username(self, value):
        if self.instance and self.instance.username == value:
            return value
        if Member.objects.filter(username=value).exists():
            raise serializers.ValidationError('Username already exists')
        return value

    def validate_phone(self, value):
        if not value:
            return value
        if self.instance and self.instance.phone == value:
            return value
        if Member.objects.filter(phone=value).exists():
            raise serializers.ValidationError('此電話號碼已被使用')
        return value


class MemberRegistrationSerializer(
    EncryptionSerializerMixin, serializers.ModelSerializer
):
    ENCRYPTION_SERVICE = MemberEncryptionService
    email = serializers.EmailField(write_only=True)
    password = serializers.CharField(write_only=True, min_length=6)
    national_id = serializers.CharField(required=False)

    class Meta:
        model = Member
        fields = [
            'username',
            'email',
            'password',
            'full_name',
            'phone',
            'national_id',
            'type',
        ]
        extra_kwargs = {
            'full_name': {'required': True},
            'phone': {'required': False},
            'national_id': {'required': False},
            'type': {'required': False, 'default': Member.TypeOptions.TOURIST},
        }

    def validate_email(self, value):
        if Member.objects.filter(email=value).exists():
            raise serializers.ValidationError('此信箱已被註冊')
        return value

    def validate_username(self, value):
        if Member.objects.filter(username=value).exists():
            raise serializers.ValidationError('此用戶名已被使用')
        return value

    def validate_phone(self, value):
        if not value:
            return value
        if Member.objects.filter(phone=value).exists():
            raise serializers.ValidationError('此電話號碼已被使用')
        return value

    def create(self, validated_data):
        with transaction.atomic():
            user_data = {
                'username': validated_data.pop('username'),
                'email': validated_data.pop('email'),
                'password': make_password(validated_data.pop('password')),
                'is_active': True,
            }

            user = User.objects.create(**user_data)

            # 設定 Member 的關聯資料
            validated_data['user'] = user
            validated_data['username'] = user.username
            validated_data['type'] = validated_data.get(
                'type', Member.TypeOptions.TOURIST
            )

            member = Member.objects.create(**validated_data)

            return member


class MemberSimpleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Member
        fields = ['id', 'full_name', 'phone']

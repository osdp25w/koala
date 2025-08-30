from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import User
from django.db import transaction
from rest_framework import serializers

from account.mixins.serializer_mixins import RBACSerializerMixin
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
    email = serializers.EmailField(required=False)
    password = serializers.CharField(required=False, min_length=6)
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
            'is_active',
        ]
        extra_kwargs = {
            'username': {'required': False},
            'password': {'required': False, 'write_only': True},
            'full_name': {'required': False},
            'phone': {'required': False},
            'national_id': {'required': False},
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
        if Member.objects.filter(username=value).exists():
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
            'type': {'required': False, 'default': Member.TYPE_TOURIST},
        }

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError('此信箱已被註冊')
        return value

    def validate_username(self, value):
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError('此用戶名已被使用')
        if Member.objects.filter(username=value).exists():
            raise serializers.ValidationError('此用戶名已被使用')
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
            validated_data['type'] = validated_data.get('type', Member.TYPE_TOURIST)

            member = Member.objects.create(**validated_data)

            return member

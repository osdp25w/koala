from rest_framework import serializers

from account.models import Member
from bike.models import (
    BikeCategory,
    BikeErrorLog,
    BikeErrorLogStatus,
    BikeInfo,
    BikeRealtimeStatus,
    BikeSeries,
)
from bike.services import BikeManagementService


class BikeCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = BikeCategory
        fields = ['id', 'category_name', 'description', 'created_at', 'updated_at']


class BikeSeriesSerializer(serializers.ModelSerializer):
    category = BikeCategorySerializer(read_only=True)

    class Meta:
        model = BikeSeries
        fields = [
            'id',
            'category',
            'series_name',
            'description',
            'created_at',
            'updated_at',
        ]


class BikeInfoSerializer(serializers.ModelSerializer):
    telemetry_device_imei = serializers.CharField(
        source='telemetry_device.IMEI', read_only=True
    )
    series_id = serializers.IntegerField(source='series.id', read_only=True)
    category_id = serializers.IntegerField(source='series.category.id', read_only=True)

    class Meta:
        model = BikeInfo
        fields = [
            'bike_id',
            'bike_name',
            'bike_model',
            'series_id',
            'category_id',
            'telemetry_device_imei',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']


class BikeInfoCreateSerializer(serializers.ModelSerializer):
    telemetry_device_imei = serializers.CharField(
        write_only=True, required=False, allow_null=True
    )

    class Meta:
        model = BikeInfo
        fields = [
            'bike_id',
            'bike_name',
            'bike_model',
            'series',
            'telemetry_device_imei',
        ]

    def to_representation(self, instance):
        return BikeInfoSerializer(instance).data

    def validate_telemetry_device_imei(self, value):
        if value:
            BikeManagementService.validate_telemetry_device(value)
        return value

    def create(self, validated_data):
        imei = validated_data.pop('telemetry_device_imei', None)
        bike = super().create(validated_data)

        if imei:
            BikeManagementService.assign_device_to_bike(bike, imei)

        return bike


class BikeInfoUpdateSerializer(serializers.ModelSerializer):
    telemetry_device_imei = serializers.CharField(
        write_only=True, required=False, allow_null=True
    )

    class Meta:
        model = BikeInfo
        fields = ['bike_name', 'bike_model', 'series', 'telemetry_device_imei']

    def to_representation(self, instance):
        return BikeInfoSerializer(instance).data

    def validate(self, attrs):
        # 檢查腳踏車狀態，只有非 RENTED 狀態才能修改
        if self.instance:
            BikeManagementService.validate_bike_modification(self.instance)
        return attrs

    def validate_telemetry_device_imei(self, value):
        if value:
            BikeManagementService.validate_telemetry_device(value, self.instance)
        return value

    def update(self, instance, validated_data):
        imei = validated_data.pop('telemetry_device_imei', None)

        # 先更新其他欄位
        instance = super().update(instance, validated_data)

        # 處理 telemetry_device 更新
        if 'telemetry_device_imei' in self.initial_data:  # 確認前端有傳這個欄位
            BikeManagementService.update_bike_telemetry_device(instance, imei)

        return instance


class MemberSimpleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Member
        fields = ['id', 'full_name', 'phone']


class BikeRealtimeStatusSerializer(serializers.ModelSerializer):
    bike = BikeInfoSerializer(read_only=True)
    lat_decimal = serializers.ReadOnlyField()
    lng_decimal = serializers.ReadOnlyField()
    current_member = MemberSimpleSerializer(read_only=True)

    class Meta:
        model = BikeRealtimeStatus
        fields = [
            'bike',
            'latitude',
            'longitude',
            'lat_decimal',
            'lng_decimal',
            'soc',
            'vehicle_speed',
            'status',
            'current_member',
            'last_seen',
            'updated_at',
        ]


class BikeErrorLogSerializer(serializers.ModelSerializer):
    bike = BikeInfoSerializer(read_only=True)
    telemetry_device_imei = serializers.CharField(
        source='telemetry_device.IMEI', read_only=True
    )
    level_display = serializers.CharField(source='get_level_display', read_only=True)
    telemetry_record = serializers.SerializerMethodField()

    class Meta:
        model = BikeErrorLog
        fields = [
            'id',
            'code',
            'bike',
            'level',
            'level_display',
            'title',
            'detail',
            'telemetry_device_imei',
            'telemetry_record',
            'created_at',
        ]

    def get_telemetry_record(self, obj):
        """
        根據 expand_telemetry_record 參數決定是否展開 telemetry_record
        """
        from telemetry.serializers import TelemetryRecordSerializer

        if not obj.telemetry_record:
            return None

        is_expand = self.context.get('expand_telemetry_record', False)
        if is_expand:
            return TelemetryRecordSerializer(obj.telemetry_record).data
        else:
            return obj.telemetry_record.id


class BikeErrorLogStatusSerializer(serializers.ModelSerializer):
    error_log = BikeErrorLogSerializer(read_only=True)

    class Meta:
        model = BikeErrorLogStatus
        fields = [
            'id',
            'error_log',
            'is_read',
            'read_at',
        ]
        read_only_fields = ['error_log']


class BikeErrorLogStatusUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = BikeErrorLogStatus
        fields = ['is_read']

    def to_representation(self, instance):
        return BikeErrorLogStatusSerializer(instance).data

    def validate_is_read(self, value):
        if not value:
            raise serializers.ValidationError('只能標記為已讀，不能標記為未讀')
        return value

    def update(self, instance, validated_data):
        # 只允許標記為已讀，不允許取消已讀狀態
        is_read = validated_data.get('is_read', False)

        if is_read and not instance.is_read:
            from django.utils import timezone

            validated_data['read_at'] = timezone.now()
        elif instance.is_read and not is_read:
            # 已讀狀態不能被取消
            raise serializers.ValidationError('不能取消已讀狀態')

        return super().update(instance, validated_data)

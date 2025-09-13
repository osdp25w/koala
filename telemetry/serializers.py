from rest_framework import serializers

from bike.serializers import BikeInfoSerializer
from telemetry.constants import IoTConstants
from telemetry.models import TelemetryDevice


class TelemetryDeviceBaseSerializer(serializers.ModelSerializer):
    class Meta:
        model = TelemetryDevice
        fields = ['IMEI', 'name', 'model', 'status']


class TelemetryDeviceSerializer(TelemetryDeviceBaseSerializer):
    """用於列表和詳情顯示"""

    bike = BikeInfoSerializer(read_only=True)

    class Meta(TelemetryDeviceBaseSerializer.Meta):
        fields = TelemetryDeviceBaseSerializer.Meta.fields + [
            'bike',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']


class TelemetryDeviceCreateSerializer(TelemetryDeviceBaseSerializer):
    def validate_IMEI(self, value):
        # 檢查長度
        if len(value) != IoTConstants.IMEI_LENGTH:
            raise serializers.ValidationError(
                f"IMEI must be exactly {IoTConstants.IMEI_LENGTH} digits."
            )

        # 檢查是否都是數字
        if not value.isdigit():
            raise serializers.ValidationError('IMEI must contain only digits.')

        # 檢查是否已存在
        if TelemetryDevice.objects.filter(IMEI=value).exists():
            raise serializers.ValidationError('IMEI already exists.')

        return value

    def validate_status(self, value):
        """新增時不允許設定為 deployed"""
        if value == TelemetryDevice.StatusOptions.DEPLOYED:
            raise serializers.ValidationError(
                'Cannot create device with deployed status.'
            )
        return value

    def create(self, validated_data):
        # 如果沒有指定 status，預設為 available
        if 'status' not in validated_data:
            validated_data['status'] = TelemetryDevice.StatusOptions.AVAILABLE
        return super().create(validated_data)


class TelemetryDeviceUpdateSerializer(TelemetryDeviceBaseSerializer):
    class Meta(TelemetryDeviceBaseSerializer.Meta):
        read_only_fields = ['IMEI']

    def validate(self, attrs):
        """驗證更新數據"""
        # 檢查是否嘗試修改 IMEI
        if 'IMEI' in self.initial_data:
            raise serializers.ValidationError({'IMEI': 'IMEI cannot be modified.'})
        return attrs

    def validate_status(self, value):
        """驗證狀態轉換"""
        if self.instance:
            current_status = self.instance.status

            # 如果從 deployed 狀態要修改到其他狀態，檢查是否有綁定的腳踏車
            if (
                current_status == TelemetryDevice.StatusOptions.DEPLOYED
                and value != TelemetryDevice.StatusOptions.DEPLOYED
            ):
                # 檢查是否有關聯的 bike
                if hasattr(self.instance, 'bike') and self.instance.bike:
                    raise serializers.ValidationError(
                        {
                            'bike_association': f'Cannot change status from deployed. Device is associated with bike {self.instance.bike.bike_id}. Please remove bike association first.'
                        }
                    )

        return value

from rest_framework import serializers

from account.models import Member

from .models import BikeInfo, BikeRealtimeStatus


class BikeInfoSerializer(serializers.ModelSerializer):
    class Meta:
        model = BikeInfo
        fields = ['bike_id', 'bike_name', 'bike_model']


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

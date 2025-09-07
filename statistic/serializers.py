from rest_framework import serializers

from .models import DailyOverviewStatistics, HourlyOverviewStatistics


class DailyOverviewStatisticsSerializer(serializers.ModelSerializer):
    total_distance_km = serializers.FloatField(read_only=True)
    carbon_reduction_kg = serializers.FloatField(read_only=True)
    average_soc = serializers.FloatField(read_only=True)

    class Meta:
        model = DailyOverviewStatistics
        fields = [
            'id',
            'online_bikes_count',
            'offline_bikes_count',
            'total_distance_km',
            'carbon_reduction_kg',
            'average_soc',
            'collected_time',
        ]
        read_only_fields = ['id']

    def to_representation(self, instance):
        """格式化小數點到一位"""
        data = super().to_representation(instance)

        # 格式化浮點數到一位小數點
        if data['total_distance_km'] is not None:
            data['total_distance_km'] = round(data['total_distance_km'], 1)
        if data['carbon_reduction_kg'] is not None:
            data['carbon_reduction_kg'] = round(data['carbon_reduction_kg'], 1)
        if data['average_soc'] is not None:
            data['average_soc'] = round(data['average_soc'], 1)

        return data


class HourlyOverviewStatisticsSerializer(serializers.ModelSerializer):
    distance_km = serializers.FloatField(read_only=True)
    carbon_reduction_kg = serializers.FloatField(read_only=True)
    average_soc = serializers.FloatField(read_only=True)

    class Meta:
        model = HourlyOverviewStatistics
        fields = [
            'id',
            'online_bikes_count',
            'offline_bikes_count',
            'distance_km',
            'carbon_reduction_kg',
            'average_soc',
            'collected_time',
        ]
        read_only_fields = ['id']

    def to_representation(self, instance):
        """格式化小數點到一位"""
        data = super().to_representation(instance)

        # 格式化浮點數到一位小數點
        if data['distance_km'] is not None:
            data['distance_km'] = round(data['distance_km'], 1)
        if data['carbon_reduction_kg'] is not None:
            data['carbon_reduction_kg'] = round(data['carbon_reduction_kg'], 1)
        if data['average_soc'] is not None:
            data['average_soc'] = round(data['average_soc'], 1)

        return data

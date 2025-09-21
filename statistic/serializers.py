from django.contrib.gis.geos import LineString, Point
from rest_framework import serializers

from account.serializers.member import MemberSimpleSerializer
from statistic.models import (
    DailyGeometryCoordinateStatistics,
    DailyOverviewStatistics,
    GeometryCoordinate,
    HourlyGeometryCoordinateStatistics,
    HourlyOverviewStatistics,
    RouteMatchResult,
)


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


class GeometryCoordinateSerializer(serializers.ModelSerializer):
    coordinate = serializers.SerializerMethodField()

    class Meta:
        model = GeometryCoordinate
        fields = ['coordinate']

    def get_coordinate(self, obj):
        return [float(obj.longitude), float(obj.latitude)]


class AggregatedGeometryCoordinateListSerializer(serializers.ListSerializer):
    """處理整個queryset的分組邏輯"""

    def to_representation(self, queryset):
        """將queryset按usage_count分組並格式化"""
        from collections import defaultdict

        # 按usage_count分組座標
        usage_groups = defaultdict(list)
        for item in queryset:
            usage_count = item['total_usage_count']
            coordinate = [
                float(item['geometry_coordinate__longitude']),
                float(item['geometry_coordinate__latitude']),
            ]
            usage_groups[usage_count].append(coordinate)

        result = []
        for usage_count in sorted(usage_groups.keys(), reverse=True):
            result.append(
                {
                    'usage_count': usage_count,
                    'geometry_coordinate': {'coordinates': usage_groups[usage_count]},
                }
            )

        return result


class AggregatedGeometryCoordinateStatisticsSerializer(serializers.Serializer):
    """聚合座標統計序列化器 - 處理按usage_count分組的座標"""

    class Meta:
        list_serializer_class = AggregatedGeometryCoordinateListSerializer


class RouteMatchResultSerializer(serializers.ModelSerializer):
    """單個路線匹配結果序列化器"""

    geometry = serializers.SerializerMethodField()
    start_point = serializers.SerializerMethodField()
    end_point = serializers.SerializerMethodField()

    class Meta:
        model = RouteMatchResult
        fields = [
            'id',
            'geometry',
            'start_point',
            'end_point',
            'distance_meters',
            'average_confidence',
            'fallback_strategy',
            'created_at',
        ]

    def get_geometry(self, obj):
        """將 LineString 轉換為 GeoJSON 格式"""
        if obj.geometry:
            return {'type': 'LineString', 'coordinates': list(obj.geometry.coords)}
        return None

    def get_start_point(self, obj):
        """將起點轉換為座標陣列"""
        if obj.start_point:
            return [obj.start_point.x, obj.start_point.y]
        return None

    def get_end_point(self, obj):
        """將終點轉換為座標陣列"""
        if obj.end_point:
            return [obj.end_point.x, obj.end_point.y]
        return None


class MemberRouteListSerializer(serializers.Serializer):
    """會員路線列表序列化器"""

    member = MemberSimpleSerializer()
    routes = RouteMatchResultSerializer(many=True)

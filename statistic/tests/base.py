"""
Base test classes for statistic app
"""
from unittest.mock import patch

from django.test import TestCase


class BaseStatisticTestWithFixtures(TestCase):
    """基礎測試類，載入 statistic 相關 fixtures"""

    fixtures = [
        # All fixtures in statistic app - 不包含 ride_sessions.json，讓 signal 自動創建
        'statistic/tests/fixtures/users.json',
        'statistic/tests/fixtures/profiles.json',
        'statistic/tests/fixtures/telemetry_device.json',
        'statistic/tests/fixtures/bike_category.json',
        'statistic/tests/fixtures/bike_series.json',
        'statistic/tests/fixtures/bike_info.json',
        'statistic/tests/fixtures/telemetry_records.json',
        'statistic/tests/fixtures/bike_rentals.json',
    ]

    def setUp(self):
        """設置共用的測試數據"""
        # Import models here to avoid circular imports
        from account.models import Member
        from bike.models import BikeInfo
        from rental.models import BikeRental
        from statistic.models import RideSession
        from telemetry.models import TelemetryRecord

        # Load test data from fixtures
        self.bike_test001 = BikeInfo.objects.get(pk='TEST001')
        self.bike_test002 = BikeInfo.objects.get(pk='TEST002')

        self.member1 = Member.objects.get(pk=1)

        self.bike_rental_1 = BikeRental.objects.get(pk=1)
        self.bike_rental_2 = BikeRental.objects.get(pk=2)

        # RideSession 由 signal 自動創建，使用 bike_rental 來取得
        self.ride_session_1 = self.bike_rental_1.ride_session
        self.ride_session_2 = self.bike_rental_2.ride_session

        # Load telemetry records for bike TEST001
        self.telemetry_records = list(
            TelemetryRecord.objects.filter(bike_id='TEST001').order_by('gps_time')
        )

    def mock_osrm_success_response(self):
        """模擬 OSRM 成功響應"""
        mock_response = {
            'code': 'Ok',
            'matchings': [
                {
                    'distance': 1250.5,
                    'confidence': 0.85,
                    'geometry': {
                        'coordinates': [
                            [121.565000, 25.042500],
                            [121.565100, 25.042600],
                            [121.565200, 25.042700],
                            [121.565300, 25.042800],
                            [121.565400, 25.042900],
                            [121.565500, 25.043000],
                            [121.565600, 25.043100],
                            [121.565700, 25.043200],
                            [121.565800, 25.043300],
                            [121.565900, 25.043400],
                        ]
                    },
                }
            ],
            'tracepoints': [
                {'waypoint_index': 0},
                {'waypoint_index': 1},
                {'waypoint_index': 2},
                {'waypoint_index': 3},
                {'waypoint_index': 4},
                {'waypoint_index': 5},
                {'waypoint_index': 6},
                {'waypoint_index': 7},
                {'waypoint_index': 8},
                {'waypoint_index': 9},
            ],
        }

        mock_patch = patch('statistic.services.requests.get')
        mock_get = mock_patch.start()
        return mock_patch, mock_get, mock_response

    def mock_osrm_failure_response(self):
        """模擬 OSRM 失敗響應"""
        mock_response = {
            'code': 'NoMatch',
            'message': 'Could not match to nearest streets.',
        }

        mock_patch = patch('statistic.services.requests.get')
        mock_get = mock_patch.start()
        return mock_patch, mock_get, mock_response

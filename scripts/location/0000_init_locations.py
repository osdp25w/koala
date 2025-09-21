from django.contrib.gis.geos import Point

from location.models import Location
from scripts.base import BaseScript


class CustomScript(BaseScript):
    def run(self):
        locations_data = [
            {
                'name': '華麗轉身',
                'description': '建國路一段',
                'latitude': 23.984969,
                'longitude': 121.595615,
                'is_active': True,
            },
            {
                'name': '順其自然',
                'description': '民有街',
                'latitude': 24.036611,
                'longitude': 121.606953,
                'is_active': True,
            },
        ]

        locations = []
        for data in locations_data:
            location = Location(
                **data,
                point=Point(
                    float(data['longitude']), float(data['latitude']), srid=4326
                ),
            )
            locations.append(location)

        Location.objects.bulk_create(locations, ignore_conflicts=True)

        print(f"成功創建 {len(locations)} 個地點")
        for location in locations:
            print(f"  - {location.name}: {location.description}")
            print(f"    座標: ({location.latitude}, {location.longitude})")

from bike.models import BikeCategory, BikeSeries
from scripts.base import BaseScript


class CustomScript(BaseScript):
    def run(self):
        # 先確保分類存在
        electric_category = BikeCategory.objects.get(category_name='電動自行車')
        traditional_category = BikeCategory.objects.get(category_name='傳統自行車')
        scooter_category = BikeCategory.objects.get(category_name='電動機車')
        folding_category = BikeCategory.objects.get(category_name='摺疊車')

        series_data = [
            # 電動自行車系列
            {
                'category': electric_category,
                'series_name': 'Urban Pro',
                'description': '都市專業級電動自行車，長續航力',
            },
            {
                'category': electric_category,
                'series_name': 'Mountain Explorer',
                'description': '山地探險電動自行車，強勁動力',
            },
            {
                'category': electric_category,
                'series_name': 'City Cruiser',
                'description': '城市巡航電動自行車，舒適騎乘',
            },
            # 傳統自行車系列
            {
                'category': traditional_category,
                'series_name': 'Classic Road',
                'description': '經典公路自行車，輕量化設計',
            },
            {
                'category': traditional_category,
                'series_name': 'Sport Racing',
                'description': '競速運動自行車，高性能',
            },
            # 電動機車系列
            {
                'category': scooter_category,
                'series_name': 'Smart Scooter',
                'description': '智能電動機車，科技感十足',
            },
            # 摺疊車系列
            {
                'category': folding_category,
                'series_name': 'Compact Fold',
                'description': '輕巧摺疊車，便於攜帶',
            },
            {
                'category': folding_category,
                'series_name': 'Business Fold',
                'description': '商務摺疊車，專業外觀',
            },
        ]

        series_list = []
        for data in series_data:
            series = BikeSeries(**data)
            series_list.append(series)

        BikeSeries.objects.bulk_create(series_list, ignore_conflicts=True)

        print(f"成功創建 {len(series_list)} 個車輛系列")
        for series in series_list:
            print(
                f"  - {series.category.category_name} > {series.series_name}: {series.description}"
            )

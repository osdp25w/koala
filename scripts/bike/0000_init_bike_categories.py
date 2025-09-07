from bike.models import BikeCategory
from scripts.base import BaseScript


class CustomScript(BaseScript):
    def run(self):
        categories_data = [
            {'category_name': '電動自行車', 'description': '配備電動輔助系統的自行車，適合中長距離騎乘'},
            {'category_name': '傳統自行車', 'description': '無電動輔助的傳統自行車，適合短距離騎乘和運動'},
            {'category_name': '電動機車', 'description': '電動輔助機車，適合城市通勤'},
            {'category_name': '摺疊車', 'description': '可摺疊收納的自行車，便於攜帶和存放'},
        ]

        categories = []
        for data in categories_data:
            category = BikeCategory(**data)
            categories.append(category)

        BikeCategory.objects.bulk_create(categories, ignore_conflicts=True)

        print(f"成功創建 {len(categories)} 個車輛大分類")
        for category in categories:
            print(f"  - {category.category_name}: {category.description}")

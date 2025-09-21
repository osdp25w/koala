#!/usr/bin/env python
"""
建立模擬器所需的所有測試資料
使用 DataFactory 統一管理，無需 fixture 檔案
直接執行: python simulator/scripts/setup_simulation_data.py
"""

import os
import sys

import django

# 設置Django環境
sys.path.append('/usr/src/app')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'koala.settings')
django.setup()

from simulator.data_factory import SimulationDataFactory


def setup_simulation_data():
    """建立所有模擬器資料"""
    print('使用 DataFactory 建立模擬器資料...\n')

    try:
        # 使用 DataFactory 建立所有資料
        data = SimulationDataFactory.create_all_data()

        print('\n📊 資料建立統計:')
        print(f"  🚲 自行車: {len(data['bikes'])} 台")
        print(f"  📡 遙測設備: {len(data['telemetry_devices'])} 個")
        print(f"  📍 地點: {len(data['locations'])} 個")
        print(f"  👤 管理員: {data['admin_user'].username}")
        print(f"  👨‍💼 員工: {data['staff_user'].username}")
        print(f"  🏷️  車輛分類: {data['category'].category_name}")
        print(f"  🚲 車輛系列: {data['series'].series_name}")

        return True

    except Exception as e:
        print(f"\n❌ DataFactory 建立失敗: {e}")
        return False


if __name__ == '__main__':
    success = setup_simulation_data()
    if success:
        print('\n✅ 所有資料建立成功!')
    else:
        print('\n❌ 資料建立失敗!')
        sys.exit(1)

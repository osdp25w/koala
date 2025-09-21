#!/usr/bin/env python
"""
運行花蓮自行車租賃模擬
直接執行: python simulator/scripts/run_bike_simulation.py [租賃次數]
範例: python simulator/scripts/run_bike_simulation.py 5
"""

import os
import sys

import django

# 設置Django環境
sys.path.append('/usr/src/app')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'koala.settings')
django.setup()

from simulator.services import SimulationRunner


def run_simulation(num_rentals=5):
    print(f'開始運行花蓮自行車租賃模擬 (租賃次數: {num_rentals})')

    try:
        rentals = SimulationRunner.run_full_simulation(num_rentals=num_rentals)
        print(f'模擬完成! 總共完成 {len(rentals)} 次租賃')
        return rentals

    except Exception as e:
        print(f'模擬過程中發生錯誤: {e}')
        raise


if __name__ == '__main__':
    # 從命令行參數獲取租賃次數
    num_rentals = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    run_simulation(num_rentals)

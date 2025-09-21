#!/usr/bin/env python
"""
清理所有 SIMULATOR- 開頭的測試資料
直接執行: python simulator/scripts/cleanup_simulator_data.py
"""

import os
import sys

import django

# 設置Django環境
sys.path.append('/usr/src/app')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'koala.settings')
django.setup()

from simulator.data_factory import SimulationDataFactory


def cleanup_simulator_data():
    """清理所有模擬器資料"""
    print('🧹 開始清理 SIMULATOR- 測試資料...\n')

    try:
        # 詢問使用者確認
        confirm = input('⚠️  這將刪除所有 SIMULATOR- 開頭的測試資料，確定要繼續嗎？ (y/N): ')
        if confirm.lower() not in ['y', 'yes']:
            print('❌ 取消清理操作')
            return False

        # 執行清理
        SimulationDataFactory.cleanup_all_data()
        return True

    except Exception as e:
        print(f'\n❌ 清理失敗: {e}')
        return False


if __name__ == '__main__':
    success = cleanup_simulator_data()
    if success:
        print('\n✅ 清理完成!')
    else:
        print('\n❌ 清理失敗!')
        sys.exit(1)

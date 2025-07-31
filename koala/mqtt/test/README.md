# MQTT + Celery 測試套件

這個目錄包含了完整的 MQTT + Celery 整合測試套件，用於驗證 IoT 設備消息處理架構。

## 📁 目錄結構

```
koala/mqtt/test/
├── README.md                           # 本文檔
├── __init__.py                         # Python模組初始化
├── run_tests.sh                        # 🚀 測試執行腳本 (推薦使用)
├── run_all_tests.py                    # Python測試套件
├── test_single_queue_architecture.py   # 單一隊列架構測試
└── iot_device_simulator.py            # IoT設備模擬器
```

## 🚀 快速開始

### 使用測試腳本 (推薦)

```bash
# 顯示幫助信息
./koala/mqtt/test/run_tests.sh --help

# 檢查服務狀態
./koala/mqtt/test/run_tests.sh --check

# 運行基本測試 (不包含IoT模擬器)
./koala/mqtt/test/run_tests.sh --test

# 運行完整測試 (包含IoT模擬器)
./koala/mqtt/test/run_tests.sh --full

# 重啟服務並運行完整測試
./koala/mqtt/test/run_tests.sh --restart

# 顯示服務日誌
./koala/mqtt/test/run_tests.sh --logs
```

### 直接運行 Python 測試

```bash
# 運行基本架構測試
docker-compose -f backend-local.yml exec koala-iot-default-worker python koala/mqtt/test/run_all_tests.py

# 運行包含IoT模擬器的完整測試
docker-compose -f backend-local.yml exec koala-iot-default-worker python koala/mqtt/test/run_all_tests.py --include-iot-simulator

# 單獨運行IoT設備模擬器
docker-compose -f backend-local.yml exec koala-iot-default-worker python koala/mqtt/test/iot_device_simulator.py --bikes 3 --duration 5
```

## 📋 測試套件說明

### 1. 單一隊列架構測試 (`test_single_queue_architecture.py`)

測試新的單一隊列架構，驗證基於 `message_type` 的路由機制：

- ✅ MQTT 連接測試
- ✅ 遙測消息發布測試
- ✅ 車隊管理消息發布測試
- ✅ 運動消息發布測試
- ✅ 未知消息類型處理測試

**測試流程**：
1. 建立 MQTT 連接
2. 發布各種類型的測試消息
3. 驗證 Celery 任務被正確觸發
4. 檢查消息處理結果

### 2. IoT 設備模擬器 (`iot_device_simulator.py`)

模擬真實的 IoT 設備行為，發送各種類型的數據：

**功能特性**：
- 🚲 模擬多輛腳踏車設備
- 📡 發送遙測數據 (位置、電池、速度等)
- 🏢 發送車隊管理數據 (狀態、維護信息等)
- 🏃 發送運動數據 (距離、卡路里、速度等)
- ⏰ 模擬真實的時間間隔和數據變化

**參數選項**：
```bash
--bikes <數量>      # 模擬腳踏車數量 (預設: 3)
--duration <分鐘>   # 模擬持續時間 (預設: 5分鐘)
```

**模擬行為**：
- 隨機租借/歸還腳踏車
- 模擬移動和速度變化
- 電池消耗模擬
- 真實的 GPS 位置變化

### 3. 測試執行腳本 (`run_tests.sh`)

提供便捷的測試執行和管理功能：

**主要功能**：
- 🔍 自動檢查 Docker 服務狀態
- 🚀 一鍵啟動所有服務
- 🧪 運行不同類型的測試
- 📊 顯示彩色輸出和狀態信息
- 📋 查看服務日誌

**腳本特色**：
- 彩色輸出，清晰易讀
- 自動錯誤處理
- 服務狀態檢查
- 完整的測試流程管理

## 🏗️ 架構說明

### 單一隊列架構

```
IoT設備 → MQTT → RabbitMQ → Celery Worker → 處理器
                ↓
            iot_default_q (單一隊列)
                ↓
        基於 message_type 路由
                ↓
    ┌─────────┬─────────┬─────────┐
    │telemetry│  fleet  │  sport  │
    │處理器   │處理器   │處理器   │
    └─────────┴─────────┴─────────┘
```

**優勢**：
- 簡化隊列管理
- 提高資源利用率
- 統一的錯誤處理
- 靈活的消息路由

### 消息格式

所有消息都使用統一的格式：

```json
{
  "message_type": "telemetry|fleet|sport|unknown",
  "bike_id": "bike_001",
  "timestamp": 1753974637,
  "data": {
    // 具體的業務數據
  },
  "metadata": {
    "source": "mqtt",
    "priority": "normal"
  }
}
```

## 🔧 故障排除

### 常見問題

1. **服務未啟動**
   ```bash
   ./koala/mqtt/test/run_tests.sh --start
   ```

2. **MQTT 連接失敗**
   ```bash
   ./koala/mqtt/test/run_tests.sh --logs
   # 檢查 RabbitMQ 和 MQTT 客戶端日誌
   ```

3. **Celery Worker 未運行**
   ```bash
   docker-compose -f backend-local.yml logs koala-iot-default-worker
   ```

4. **測試超時**
   - 檢查網絡連接
   - 確認服務資源充足
   - 調整測試參數

### 日誌查看

```bash
# 查看所有服務日誌
./koala/mqtt/test/run_tests.sh --logs

# 查看特定服務日誌
docker-compose -f backend-local.yml logs koala-mqtt-client
docker-compose -f backend-local.yml logs koala-iot-default-worker
docker-compose -f backend-local.yml logs koala-rabbitmq
```

## 📊 測試結果解讀

### 成功指標

- ✅ 所有測試通過
- ✅ 消息正確路由到對應處理器
- ✅ Celery 任務正常執行
- ✅ 無連接錯誤或超時

### 性能指標

- **消息處理延遲**: < 100ms
- **任務執行時間**: < 50ms
- **並發處理能力**: 支持多個 Worker
- **錯誤恢復**: 自動重連和重試

## 🚀 進階使用

### 自定義測試

您可以修改測試文件來添加自定義測試：

1. 編輯 `test_single_queue_architecture.py`
2. 添加新的測試函數
3. 在 `main()` 函數中調用

### 性能測試

```bash
# 運行長時間的IoT模擬
./koala/mqtt/test/iot_device_simulator.py --bikes 10 --duration 30

# 監控系統資源
docker stats
```

### 生產環境測試

在部署到生產環境前，建議：

1. 運行完整的測試套件
2. 進行壓力測試
3. 驗證錯誤處理機制
4. 檢查日誌和監控

## 📝 更新日誌

- **v1.0.0**: 初始版本，包含基本測試功能
- **v1.1.0**: 添加 IoT 設備模擬器
- **v1.2.0**: 實現單一隊列架構
- **v1.3.0**: 添加測試執行腳本
- **v1.4.0**: 完善文檔和錯誤處理

## 🤝 貢獻

如果您發現問題或有改進建議，請：

1. 檢查現有文檔
2. 運行測試套件確認問題
3. 提供詳細的錯誤信息
4. 提交改進建議

---

**注意**: 運行測試前請確保 Docker 服務正常運行，並且有足夠的系統資源。

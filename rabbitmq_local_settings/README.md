# RabbitMQ 本地開發環境設置指南

本目錄包含用於本地開發的 RabbitMQ 配置和工具腳本。

## 📋 目錄結構

```
rabbitmq_local_settings/
├── README.md                    # 本文件
├── generate-certs.sh            # 生成 SSL 憑證腳本
├── create-mqtt-user.sh          # 建立 MQTT 使用者腳本
├── test-mqtt-connection.py      # MQTT 連線測試程式
├── test-connection.sh           # 執行連線測試的腳本
├── rabbitmq.conf                # RabbitMQ 主配置文件
├── enabled_plugins              # 啟用的 RabbitMQ 插件列表
└── certs/                       # SSL 憑證目錄
    ├── ca_certificate.pem       # CA 憑證
    ├── ca_key.pem              # CA 私鑰
    ├── server_certificate.pem   # 伺服器憑證
    ├── server_key.pem          # 伺服器私鑰
    ├── client_certificate.pem   # 客戶端憑證
    └── client_key.pem          # 客戶端私鑰
```

## 🚀 快速開始

### 1. 啟動 RabbitMQ 服務

```bash
# 從專案根目錄執行
docker-compose -f backend-local.yml up -d koala-rabbitmq
```

### 2. 生成 SSL 憑證（首次設置）

```bash
# 生成用於 MQTTS 的 SSL 憑證
./rabbitmq_local_settings/generate-certs.sh
```

### 3. 建立 MQTT 使用者

```bash
# 建立 MQTT 使用者帳號
./rabbitmq_local_settings/create-mqtt-user.sh
```

### 4. 測試連線

```bash
# 測試所有 MQ 連線
./rabbitmq_local_settings/test-connection.sh
```

## 🔧 詳細說明

### RabbitMQ 服務配置

本地 RabbitMQ 服務提供以下端口：

- **5672** - AMQP 協議（Celery 使用）
- **15672** - RabbitMQ 管理界面
- **1883** - MQTT 協議（明文）
- **8883** - MQTTS 協議（SSL/TLS）

### 認證資訊

系統預設使用以下認證：

#### AMQP 認證
- **admin/p@ss1234** - 管理員帳號
- **mqtt/p@ss1234** - MQTT 專用帳號

#### MQTT 認證
- **mqtt/p@ss1234** - MQTT 專用帳號

### SSL 憑證

`generate-certs.sh` 腳本會生成以下憑證：

- **CA 憑證** - 用於驗證其他憑證
- **伺服器憑證** - RabbitMQ 伺服器使用
- **客戶端憑證** - IoT 設備使用

⚠️ **注意**：這些是自簽名憑證，僅供開發測試使用。

## 🧪 測試功能

### 連線測試

`test-connection.sh` 腳本會測試：

1. **AMQP 連線** (端口 5672)
   - 使用 admin/p@ss1234
   - 使用 mqtt/p@ss1234

2. **MQTT 連線** (端口 1883)
   - 使用 admin/p@ss1234
   - 使用 mqtt/p@ss1234

3. **MQTTS 連線** (端口 8883)
   - 使用 admin/p@ss1234 + SSL 憑證
   - 使用 mqtt/p@ss1234 + SSL 憑證

### 手動測試

您也可以直接執行 Python 測試程式：

```bash
cd rabbitmq_local_settings
python3 test-mqtt-connection.py
```

## 🔍 故障排除

### 常見問題

#### 1. RabbitMQ 容器無法啟動
```bash
# 檢查容器狀態
docker-compose -f backend-local.yml ps

# 查看容器日誌
docker-compose -f backend-local.yml logs koala-rabbitmq
```

#### 2. 憑證生成失敗
```bash
# 確保 OpenSSL 已安裝
openssl version

# 重新生成憑證
./rabbitmq_local_settings/generate-certs.sh
```

#### 3. MQTT 使用者建立失敗
```bash
# 確保 RabbitMQ 已完全啟動
docker-compose -f backend-local.yml up -d koala-rabbitmq
sleep 30

# 重新建立使用者
./rabbitmq_local_settings/create-mqtt-user.sh
```

#### 4. 連線測試失敗
```bash
# 檢查依賴套件
pip install pika paho-mqtt

# 檢查憑證是否存在
ls -la rabbitmq_local_settings/certs/

# 重新執行測試
./rabbitmq_local_settings/test-connection.sh
```

### 管理界面

訪問 RabbitMQ 管理界面：
- **URL**: http://localhost:15672
- **預設帳號**: guest/guest

## 📚 相關文件

- [RabbitMQ 官方文件](https://www.rabbitmq.com/documentation.html)
- [MQTT 協議說明](https://mqtt.org/documentation)
- [Docker Compose 文件](https://docs.docker.com/compose/)

## 🔒 安全注意事項

1. **開發環境專用** - 此配置僅適用於本地開發
2. **自簽名憑證** - 生產環境應使用正式的 SSL 憑證
3. **預設密碼** - 生產環境應更改所有預設密碼
4. **網路安全** - 確保開發環境的網路安全

## 🤝 貢獻

如需修改配置或新增功能，請：

1. 更新相關腳本
2. 更新此 README 文件
3. 測試所有功能正常運作
4. 提交變更

---

**最後更新**: 2024年12月

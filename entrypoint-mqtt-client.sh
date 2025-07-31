#!/usr/bin/env sh

# MQTT 客戶端 entrypoint
# 用於 K8s 部署 paho-mqtt 客戶端服務

echo "Starting MQTT Client Service..."

# 等待數據庫和其他服務就緒
echo "Waiting for dependencies..."
sleep 5

# 檢查必要的環境變數
if [ -z "$RABBITMQ_HOST" ]; then
    echo "Warning: RABBITMQ_HOST not set, using default"
fi

if [ -z "$MQTT_HOST" ]; then
    echo "Warning: MQTT_HOST not set, using RABBITMQ_HOST"
fi

# 啟動 MQTT 客戶端 (daemon 模式)
echo "Starting MQTT client in daemon mode..."
echo "Connecting to MQTT broker: ${MQTT_HOST:-$RABBITMQ_HOST}:${MQTT_PORT:-1883}"
echo "Subscribed topics: bike/+/telemetry, bike/+/fleet, bike/+/sport"

# 使用 daemon 模式啟動，適合 K8s 部署
python manage.py mqtt_client --action start --daemon

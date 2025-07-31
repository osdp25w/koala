#!/bin/bash

# Script to test MQTT connections using test-mqtt-connection.py
# Run from project root (koala/) after RabbitMQ container is running

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
TEST_SCRIPT="$SCRIPT_DIR/test-mqtt-connection.py"

echo "🔍 Testing MQTT connections to RabbitMQ..."

# Check if test script exists
if [[ ! -f "$TEST_SCRIPT" ]]; then
    echo "❌ Test script not found: $TEST_SCRIPT"
    exit 1
fi

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 is not installed or not in PATH"
    exit 1
fi

# Check if required dependencies are installed
echo "📦 Checking dependencies..."
python3 -c "import pika, paho.mqtt.client" 2>/dev/null
if [[ $? -ne 0 ]]; then
    echo "❌ Missing required dependencies: pika, paho-mqtt"
    echo "💡 Install with: pip install pika paho-mqtt"
    exit 1
fi

# Check if certificates exist for MQTTS testing
CERT_DIR="$SCRIPT_DIR/certs"
if [[ ! -f "$CERT_DIR/ca_certificate.pem" ]]; then
    echo "⚠️  CA certificate not found. MQTTS test may fail."
    echo "💡 Generate certificates with: ./rabbitmq_local_settings/generate-certs.sh"
fi

# Run the test script
echo "🚀 Running connection tests..."
cd "$PROJECT_ROOT"
python3 "$TEST_SCRIPT" "$@"

# Check exit code
if [[ $? -eq 0 ]]; then
    echo "✅ All connection tests passed!"
else
    echo "❌ Some connection tests failed."
    echo "💡 Make sure RabbitMQ is running: docker-compose -f backend-local.yml up -d koala-rabbitmq"
    echo "💡 Create MQTT user: ./rabbitmq_local_settings/create-mqtt-user.sh"
    exit 1
fi

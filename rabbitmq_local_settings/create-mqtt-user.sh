#!/bin/bash

# Script to create MQTT user in RabbitMQ (non-interactive)
# Run from project root (koala/) after RabbitMQ container is running

DOCKER_COMPOSE_FILE="backend-local.yml"
SERVICE_NAME="koala-rabbitmq"
MQTT_USERNAME="mqtt"
MQTT_PASSWORD="p@ss1234"
VHOST="/"

# Resolve container ID dynamically to avoid hard-coding the suffix
RABBITMQ_CONTAINER=$(docker-compose -f "$DOCKER_COMPOSE_FILE" ps -q "$SERVICE_NAME")
if [[ -z "$RABBITMQ_CONTAINER" ]]; then
  echo "❌ Unable to find running container for service '$SERVICE_NAME'."
  echo "💡 Start it with: docker-compose -f $DOCKER_COMPOSE_FILE up -d $SERVICE_NAME"
  exit 1
fi

echo "🔐 Setting up MQTT user '$MQTT_USERNAME' in container $RABBITMQ_CONTAINER ..."

# Function to check if RabbitMQ is ready
wait_for_rabbitmq() {
  echo "⏳ Waiting for RabbitMQ to be ready..."
  local max_attempts=30
  local attempt=1
  while [[ $attempt -le $max_attempts ]]; do
    if docker exec "$RABBITMQ_CONTAINER" rabbitmqctl status &>/dev/null; then
      echo "✅ RabbitMQ is ready!"
      return 0
    fi
    sleep 2
    ((attempt++))
  done
  echo "❌ RabbitMQ failed to become ready within timeout"
  return 1
}

create_or_update_user() {
  if docker exec "$RABBITMQ_CONTAINER" rabbitmqctl list_users | grep -q "^$MQTT_USERNAME"; then
    echo "ℹ️  User '$MQTT_USERNAME' already exists – updating password and permissions..."
    docker exec "$RABBITMQ_CONTAINER" rabbitmqctl change_password "$MQTT_USERNAME" "$MQTT_PASSWORD"
  else
    echo "👤 Creating new MQTT user: $MQTT_USERNAME"
    docker exec "$RABBITMQ_CONTAINER" rabbitmqctl add_user "$MQTT_USERNAME" "$MQTT_PASSWORD"
  fi

  # Ensure tags and permissions
  docker exec "$RABBITMQ_CONTAINER" rabbitmqctl set_user_tags "$MQTT_USERNAME" ""
  docker exec "$RABBITMQ_CONTAINER" rabbitmqctl set_permissions -p "$VHOST" "$MQTT_USERNAME" "" ".*" ".*"
}

verify_user() {
  echo "🔍 Verifying MQTT user..."
  docker exec "$RABBITMQ_CONTAINER" rabbitmqctl list_users | grep "$MQTT_USERNAME"
  docker exec "$RABBITMQ_CONTAINER" rabbitmqctl list_permissions -p "$VHOST" | grep "$MQTT_USERNAME"
}

main() {
  wait_for_rabbitmq || exit 1
  create_or_update_user
  verify_user
  echo "🎉 MQTT user '$MQTT_USERNAME' is ready!"
  echo "   Username: $MQTT_USERNAME"
  echo "   Password: $MQTT_PASSWORD"
  echo "   Host: localhost (1883 / 8883)"
}

main

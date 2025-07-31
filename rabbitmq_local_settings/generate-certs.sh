#!/bin/bash

# Script to generate SSL certificates for local MQTTS development
# This creates self-signed certificates for testing purposes only

CERT_DIR="./rabbitmq_local_settings/certs"
DAYS=365

echo "🔐 Generating SSL certificates for MQTTS development..."

# Create certificate directory
mkdir -p "$CERT_DIR"

# Generate CA private key
echo "📋 Generating CA private key..."
openssl genrsa -out "$CERT_DIR/ca_key.pem" 2048

# Generate CA certificate
echo "📋 Generating CA certificate..."
openssl req -new -x509 -days $DAYS -key "$CERT_DIR/ca_key.pem" -out "$CERT_DIR/ca_certificate.pem" \
    -subj "/C=TW/ST=Taiwan/L=Taipei/O=Koala/OU=Development/CN=Koala-CA"

# Generate server private key
echo "📋 Generating server private key..."
openssl genrsa -out "$CERT_DIR/server_key.pem" 2048

# Generate server certificate signing request
echo "📋 Generating server certificate signing request..."
openssl req -new -key "$CERT_DIR/server_key.pem" -out "$CERT_DIR/server.csr" \
    -subj "/C=TW/ST=Taiwan/L=Taipei/O=Koala/OU=Development/CN=localhost"

# Generate server certificate signed by CA
echo "📋 Generating server certificate..."
openssl x509 -req -days $DAYS -in "$CERT_DIR/server.csr" -CA "$CERT_DIR/ca_certificate.pem" \
    -CAkey "$CERT_DIR/ca_key.pem" -CAcreateserial -out "$CERT_DIR/server_certificate.pem"

# Generate client private key for IoT devices
echo "📋 Generating client private key..."
openssl genrsa -out "$CERT_DIR/client_key.pem" 2048

# Generate client certificate signing request
echo "📋 Generating client certificate signing request..."
openssl req -new -key "$CERT_DIR/client_key.pem" -out "$CERT_DIR/client.csr" \
    -subj "/C=TW/ST=Taiwan/L=Taipei/O=Koala/OU=IoT-Device/CN=mqtt-client"

# Generate client certificate signed by CA
echo "📋 Generating client certificate..."
openssl x509 -req -days $DAYS -in "$CERT_DIR/client.csr" -CA "$CERT_DIR/ca_certificate.pem" \
    -CAkey "$CERT_DIR/ca_key.pem" -CAcreateserial -out "$CERT_DIR/client_certificate.pem"

# Bundle files not needed for RabbitMQ MQTT

# Clean up intermediate files
echo "🗑️  Cleaning up intermediate files..."
rm -f "$CERT_DIR/server.csr"
rm -f "$CERT_DIR/client.csr"
rm -f "$CERT_DIR/ca_certificate.srl"

# Set appropriate permissions
chmod 644 "$CERT_DIR"/*.pem
chmod 600 "$CERT_DIR"/*_key.pem  # Private keys should be more restrictive

echo "✅ SSL certificates generated successfully!"
echo "📁 Certificates are located in: $CERT_DIR"
echo ""
echo "📝 Files created:"
echo "   🔐 CA Files:"
echo "      - ca_certificate.pem (CA certificate for verification)"
echo "      - ca_key.pem (CA private key)"
echo "   🖥️  Server Files:"
echo "      - server_certificate.pem (Server certificate)"
echo "      - server_key.pem (Server private key)"
echo "   📱 Client Files (for IoT devices):"
echo "      - client_certificate.pem (Client certificate)"
echo "      - client_key.pem (Client private key)"
echo ""
echo "💡 Usage notes:"
echo "   - For IoT devices with mutual TLS: Use client_certificate.pem + client_key.pem + ca_certificate.pem"
echo "   - For server verification only: Use ca_certificate.pem"
echo "   - RabbitMQ server uses: server_certificate.pem + server_key.pem + ca_certificate.pem"
echo ""
echo "⚠️  These are self-signed certificates for development only!"
echo "🚀 You can now start RabbitMQ with MQTTS support using: docker-compose -f backend-local.yml up"

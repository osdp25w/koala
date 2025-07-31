import ssl
import sys
import traceback
from pathlib import Path

# External dependencies (install via `pip install pika paho-mqtt`)
try:
    import paho.mqtt.client as mqtt  # MQTT
    import pika  # AMQP
except ImportError as exc:  # pragma: no cover
    print('Missing dependency:', exc)
    print('Please run: pip install pika paho-mqtt')
    sys.exit(1)


def test_amqp(host: str, port: int, username: str, password: str) -> bool:
    print('\n🔗 Testing AMQP ({host}:{port})...'.format(host=host, port=port))
    try:
        credentials = pika.PlainCredentials(username, password)
        connection = pika.BlockingConnection(
            pika.ConnectionParameters(
                host=host, port=port, credentials=credentials, heartbeat=0
            )
        )
        channel = connection.channel()
        channel.queue_declare(queue='mq_test_q', durable=False)
        channel.basic_publish(exchange='', routing_key='mq_test_q', body=b'test')
        connection.close()
        print('✅ AMQP connection & publish successful!')
        return True
    except Exception as exc:
        traceback.print_exc()
        print('❌ AMQP test failed:', exc)
        return False


def _on_connect(client, userdata, flags, rc):
    if rc == 0:
        print('✅ MQTT connected!')
    else:
        print('❌ MQTT connection failed with code', rc)


def _on_disconnect(client, userdata, rc):
    print('🔌 MQTT disconnected (code {})'.format(rc))


def test_mqtt(
    host: str,
    port: int,
    username: str,
    password: str,
    tls: bool = False,
    ca_path: Path | None = None,
    cert_path: Path | None = None,
    key_path: Path | None = None,
) -> bool:
    label = 'MQTTS' if tls else 'MQTT'
    print(f"\n🔗 Testing {label} ({host}:{port})...")
    try:
        client = mqtt.Client(client_id=f"mq_test_{label.lower()}")
        client.username_pw_set(username, password)
        client.on_connect = _on_connect
        client.on_disconnect = _on_disconnect

        if tls:
            if ca_path is None:
                raise ValueError('ca_path is required for TLS connection')
            client.tls_set(
                ca_certs=str(ca_path),
                certfile=str(cert_path) if cert_path else None,
                keyfile=str(key_path) if key_path else None,
                tls_version=ssl.PROTOCOL_TLS,
            )
            client.tls_insecure_set(False)

        client.connect(host, port, keepalive=10)
        client.loop_start()
        # wait a moment
        import time

        time.sleep(2)
        client.loop_stop()
        client.disconnect()
        print(f"✅ {label} connection successful!")
        return True
    except Exception as exc:
        traceback.print_exc()
        print(f"❌ {label} test failed:", exc)
        return False


def main():
    # Hard-coded configuration
    host = 'localhost'
    amqp_port = 5672
    mqtt_port = 1883
    mqtts_port = 8883
    ca_cert = 'rabbitmq_local_settings/certs/ca_certificate.pem'
    client_cert = 'rabbitmq_local_settings/certs/client_certificate.pem'
    client_key = 'rabbitmq_local_settings/certs/client_key.pem'

    # Test credentials
    admin_creds = ('admin', 'p@ss1234')
    mqtt_creds = ('mqtt', 'p@ss1234')

    print('🔍 Testing MQTT connections with multiple credentials...')
    print('=' * 60)

    # Test with admin credentials
    print('\n👤 Testing with admin credentials (admin/p@ss1234):')
    print('-' * 40)
    ok_amqp_admin = test_amqp(host, amqp_port, admin_creds[0], admin_creds[1])
    ok_mqtt_admin = test_mqtt(
        host, mqtt_port, admin_creds[0], admin_creds[1], tls=False
    )

    ca_path = Path(ca_cert)
    cert_path = Path(client_cert) if client_cert else None
    key_path = Path(client_key) if client_key else None
    ok_mqtts_admin = test_mqtt(
        host,
        mqtts_port,
        admin_creds[0],
        admin_creds[1],
        tls=True,
        ca_path=ca_path,
        cert_path=cert_path,
        key_path=key_path,
    )

    # Test with mqtt credentials
    print('\n👤 Testing with mqtt credentials (mqtt/p@ss1234):')
    print('-' * 40)
    ok_amqp_mqtt = test_amqp(host, amqp_port, mqtt_creds[0], mqtt_creds[1])
    ok_mqtt_mqtt = test_mqtt(host, mqtt_port, mqtt_creds[0], mqtt_creds[1], tls=False)
    ok_mqtts_mqtt = test_mqtt(
        host,
        mqtts_port,
        mqtt_creds[0],
        mqtt_creds[1],
        tls=True,
        ca_path=ca_path,
        cert_path=cert_path,
        key_path=key_path,
    )

    print('\n' + '=' * 60)
    print('📊 SUMMARY')
    print('=' * 60)
    print('Admin credentials (admin/p@ss1234):')
    print('  AMQP:  ', '✅ PASS' if ok_amqp_admin else '❌ FAIL')
    print('  MQTT:  ', '✅ PASS' if ok_mqtt_admin else '❌ FAIL')
    print('  MQTTS: ', '✅ PASS' if ok_mqtts_admin else '❌ FAIL')
    print()
    print('MQTT credentials (mqtt/p@ss1234):')
    print('  AMQP:  ', '✅ PASS' if ok_amqp_mqtt else '❌ FAIL')
    print('  MQTT:  ', '✅ PASS' if ok_mqtt_mqtt else '❌ FAIL')
    print('  MQTTS: ', '✅ PASS' if ok_mqtts_mqtt else '❌ FAIL')

    # Overall success if at least one set of credentials works for each protocol
    overall_amqp = ok_amqp_admin or ok_amqp_mqtt
    overall_mqtt = ok_mqtt_admin or ok_mqtt_mqtt
    overall_mqtts = ok_mqtts_admin or ok_mqtts_mqtt

    print('\nOverall Results:')
    print('  AMQP:  ', '✅ PASS' if overall_amqp else '❌ FAIL')
    print('  MQTT:  ', '✅ PASS' if overall_mqtt else '❌ FAIL')
    print('  MQTTS: ', '✅ PASS' if overall_mqtts else '❌ FAIL')

    if not (overall_amqp and overall_mqtt and overall_mqtts):
        sys.exit(1)


if __name__ == '__main__':
    main()

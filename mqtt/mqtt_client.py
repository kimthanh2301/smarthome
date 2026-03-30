"""
MQTT Client for Smart Home
"""
import json
import logging
import paho.mqtt.client as mqtt

logger = logging.getLogger(__name__)

MQTT_BROKER = '103.252.136.205'
MQTT_PORT = 1883
MQTT_KEEPALIVE = 60
MQTT_USERNAME = None
MQTT_PASSWORD = None

TOPIC_RECEIVER_PATTERN = 'apikey/+/receiver/+'
TOPIC_FACE_PATTERN = 'apikey/+/face'


class MQTTClient:
    _instance = None
    LOG_INTERVAL_SECONDS = 300
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        self.connected = False
        self._api_key_cache = {}
        self._last_log_time = {}
        self._setup_callbacks()
        self._initialized = True
    
    def _round_sensor_value(self, value, decimals=1):
        try:
            return round(float(value), decimals)
        except (ValueError, TypeError):
            return value
    
    def _should_log_sensor(self, device_id):
        from django.utils import timezone
        
        now = timezone.now()
        last_log = self._last_log_time.get(device_id)
        
        if last_log is None:
            self._last_log_time[device_id] = now
            return True
        
        time_diff = (now - last_log).total_seconds()
        if time_diff >= self.LOG_INTERVAL_SECONDS:
            self._last_log_time[device_id] = now
            return True
        
        return False
    
    def _setup_callbacks(self):
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message
    
    def _on_connect(self, client, userdata, flags, reason_code, properties):
        if reason_code == 0:
            logger.info(f"Connected to MQTT Broker: {MQTT_BROKER}:{MQTT_PORT}")
            self.connected = True
            self.client.subscribe(TOPIC_RECEIVER_PATTERN)
            self.client.subscribe(TOPIC_FACE_PATTERN)
        else:
            logger.error(f"Failed to connect, return code {reason_code}")
            self.connected = False
    
    def _on_disconnect(self, client, userdata, flags, reason_code, properties):
        logger.warning(f"Disconnected from MQTT Broker. Reason: {reason_code}")
        self.connected = False
    
    def _get_user_by_api_key(self, api_key):
        if api_key in self._api_key_cache:
            return self._api_key_cache[api_key]
        
        try:
            from customers.models import Profile
            profile = Profile.objects.select_related('user').filter(api_key=api_key).first()
            if profile:
                self._api_key_cache[api_key] = profile.user
                return profile.user
        except Exception as e:
            logger.error(f"Error getting user by api_key: {e}")
        
        return None
    
    def _parse_topic(self, topic):
        parts = topic.split('/')
        if len(parts) >= 4 and parts[0] == 'apikey':
            return {
                'api_key': parts[1],
                'action': parts[2],
                'device_code': parts[3] if len(parts) > 3 else None
            }
        elif len(parts) == 3 and parts[0] == 'apikey':
            return {
                'api_key': parts[1],
                'action': parts[2],
                'device_code': None
            }
        return None
    
    def _on_message(self, client, userdata, msg):
        try:
            topic = msg.topic
            payload = msg.payload.decode('utf-8')
            
            logger.info(f"Received [{topic}]: {payload}")
            
            topic_info = self._parse_topic(topic)
            if not topic_info:
                return
            
            user = self._get_user_by_api_key(topic_info['api_key'])
            if not user:
                return
            
            try:
                data = json.loads(payload)
            except json.JSONDecodeError:
                data = {'value': payload}
            
            action = topic_info['action']
            device_code = topic_info['device_code']
            
            if action == 'receiver':
                self._handle_receiver(user, device_code, data)
            elif action == 'face':
                self._handle_face_event(user, data)
                
        except Exception as e:
            logger.error(f"Error processing message: {e}")
    
    def _handle_receiver(self, user, device_code, data):
        try:
            from devices.models import Device, SensorLog
            
            if not device_code:
                return
            
            device = Device.objects.filter(
                device_code=device_code,
                user=user
            ).first()
            
            if not device:
                return
            
            value = data.get('value')
            status = data.get('status')
            
            if status is not None and device.device_type == Device.TYPE_RELAY:
                is_on = str(status).lower() in ('on', '1', 'true')
                device.value = '1' if is_on else '0'
                device.save()
                self._send_ws_device_update(user.id, device_code, is_on, device.name)
            
            if device.device_type == Device.TYPE_SENSOR and value is not None:
                from django.utils import timezone
                
                rounded_value = self._round_sensor_value(value, decimals=1)
                device.value = str(rounded_value)
                device.save()
                
                if device.enable_logging and self._should_log_sensor(device.id):
                    SensorLog.objects.create(
                        device=device,
                        value=float(rounded_value),
                        timestamp=timezone.now()
                    )
                
                self._send_ws_sensor_update(user.id, device_code, rounded_value, device.name, device.unit)
                    
        except Exception as e:
            logger.error(f"Error in _handle_receiver: {e}")
    
    def _send_ws_device_update(self, user_id, device_code, status, name=''):
        try:
            from app.consumers import send_device_update_to_websocket
            send_device_update_to_websocket(user_id, device_code, status, name)
        except Exception as e:
            logger.error(f"Error sending WS device update: {e}")
    
    def _send_ws_sensor_update(self, user_id, device_code, value, name='', unit=''):
        try:
            from app.consumers import send_sensor_update_to_websocket
            send_sensor_update_to_websocket(user_id, device_code, value, name, unit)
        except Exception as e:
            logger.error(f"Error sending WS sensor update: {e}")
    
    def _handle_face_event(self, user, data):
        try:
            detected = data.get('detected', False)
            user_code = data.get('user_code')
            confidence = data.get('confidence', 0)
            logger.info(f"Face event - Detected: {detected}, User: {user_code}, Confidence: {confidence}")
        except Exception as e:
            logger.error(f"Error handling face event: {e}")
    
    def connect(self):
        try:
            if MQTT_USERNAME and MQTT_PASSWORD:
                self.client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
            
            logger.info(f"Connecting to MQTT Broker: {MQTT_BROKER}:{MQTT_PORT}")
            self.client.connect(MQTT_BROKER, MQTT_PORT, MQTT_KEEPALIVE)
            return True
        except Exception as e:
            logger.error(f"Failed to connect to MQTT: {e}")
            return False
    
    def disconnect(self):
        self.client.disconnect()
        self.connected = False
    
    def start_loop(self):
        self.client.loop_start()
    
    def stop_loop(self):
        self.client.loop_stop()
    
    def publish(self, topic, payload, qos=1, retain=False):
        try:
            if isinstance(payload, dict):
                payload = json.dumps(payload)
            
            result = self.client.publish(topic, payload, qos=qos, retain=retain)
            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                logger.info(f"Published [{topic}]: {payload}")
                return True
            else:
                logger.error(f"Failed to publish: {result.rc}")
                return False
        except Exception as e:
            logger.error(f"Error publishing message: {e}")
            return False
    
    def control_device(self, api_key, device_code, value):
        topic = f"apikey/{api_key}/control/{device_code}"
        payload = {'value': value}
        return self.publish(topic, payload)
    
    def send_face_event(self, api_key, detected, user_code=None, confidence=0):
        topic = f"apikey/{api_key}/face"
        payload = {
            'detected': detected,
            'user_code': user_code,
            'confidence': confidence,
        }
        return self.publish(topic, payload)
    
    def clear_api_key_cache(self):
        self._api_key_cache.clear()


mqtt_client = MQTTClient()


def get_mqtt_client():
    return mqtt_client

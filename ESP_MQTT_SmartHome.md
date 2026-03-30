# ESP32/ESP8266 MQTT Smart Home - User: pcthuoc

## Thông tin kết nối

| Thông số | Giá trị |
|----------|---------|
| **MQTT Broker** | `103.252.136.205` |
| **Port** | `1883` |
| **API Key** | `78aad22403acfc3e2fe4485532b2a0ca7201f3f585eb6c3a99457305b90075ca` |

## Danh sách thiết bị

| Device Code | Loại | Tên | Đơn vị |
|-------------|------|-----|--------|
| v17 | relay | Đèn | - |
| v2 | relay | Cửa | - |
| v3 | relay | Quạt | - |
| v4 | sensor | Báo cháy | - |
| v5 | sensor | Khí Gas | ppm |
| v6 | sensor | Độ ẩm | % |
| v7 | sensor | Nhiệt độ | °C |

## Topic MQTT

### Gửi dữ liệu lên server (ESP → Server)
```
apikey/{API_KEY}/receiver/{DEVICE_CODE}
```

**Ví dụ:**
- Gửi nhiệt độ: `apikey/78aad22403acfc3e2fe4485532b2a0ca7201f3f585eb6c3a99457305b90075ca/receiver/v7`
- Gửi độ ẩm: `apikey/78aad22403acfc3e2fe4485532b2a0ca7201f3f585eb6c3a99457305b90075ca/receiver/v6`

### Nhận lệnh điều khiển (Server → ESP)
```
apikey/{API_KEY}/control/{DEVICE_CODE}
```

**Ví dụ:**
- Điều khiển đèn: `apikey/78aad22403acfc3e2fe4485532b2a0ca7201f3f585eb6c3a99457305b90075ca/control/v17`

## Payload JSON

### Sensor gửi giá trị
```json
{"value": 25.5}
```

### Relay gửi/nhận trạng thái
```json
{"value": "on"}
```
hoặc
```json
{"value": "off"}
```

---

## Code ESP32/ESP8266

```cpp
#include <WiFi.h>          // ESP32
// #include <ESP8266WiFi.h> // ESP8266
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include <DHT.h>

// ==================== CẤU HÌNH ====================
// WiFi
const char* WIFI_SSID = "YOUR_WIFI_SSID";
const char* WIFI_PASSWORD = "YOUR_WIFI_PASSWORD";

// MQTT
const char* MQTT_BROKER = "103.252.136.205";
const int MQTT_PORT = 1883;
const char* API_KEY = "78aad22403acfc3e2fe4485532b2a0ca7201f3f585eb6c3a99457305b90075ca";

// Device Codes
const char* DEVICE_TEMP = "v7";      // Nhiệt độ
const char* DEVICE_HUMID = "v6";     // Độ ẩm
const char* DEVICE_GAS = "v5";       // Khí Gas
const char* DEVICE_FIRE = "v4";      // Báo cháy
const char* DEVICE_LIGHT = "v17";    // Đèn
const char* DEVICE_DOOR = "v2";      // Cửa
const char* DEVICE_FAN = "v3";       // Quạt

// Chân GPIO
#define DHT_PIN 4           // DHT11/DHT22
#define DHT_TYPE DHT11
#define GAS_PIN 34          // MQ-2 (Analog)
#define FIRE_PIN 35         // Flame sensor (Analog)
#define LIGHT_PIN 16        // Relay đèn
#define DOOR_PIN 17         // Relay cửa
#define FAN_PIN 18          // Relay quạt

// ==================== KHAI BÁO ====================
WiFiClient espClient;
PubSubClient mqtt(espClient);
DHT dht(DHT_PIN, DHT_TYPE);

// Biến
unsigned long lastSensorRead = 0;
const long SENSOR_INTERVAL = 5000;  // Đọc sensor mỗi 5 giây

// ==================== HÀM PHỤ TRỢ ====================

// Tạo topic
String getTopic(const char* action, const char* deviceCode) {
    return String("apikey/") + API_KEY + "/" + action + "/" + deviceCode;
}

// Gửi giá trị sensor
void publishSensorValue(const char* deviceCode, float value) {
    String topic = getTopic("receiver", deviceCode);
    
    StaticJsonDocument<64> doc;
    doc["value"] = value;
    
    char payload[64];
    serializeJson(doc, payload);
    
    mqtt.publish(topic.c_str(), payload);
    Serial.printf("📤 [%s] = %.2f\n", deviceCode, value);
}

// Gửi trạng thái relay
void publishRelayStatus(const char* deviceCode, bool status) {
    String topic = getTopic("receiver", deviceCode);
    
    StaticJsonDocument<64> doc;
    doc["value"] = status ? "on" : "off";
    doc["status"] = status ? "on" : "off";
    
    char payload[64];
    serializeJson(doc, payload);
    
    mqtt.publish(topic.c_str(), payload);
    Serial.printf("📤 [%s] = %s\n", deviceCode, status ? "ON" : "OFF");
}

// Điều khiển relay
void controlRelay(const char* deviceCode, bool state) {
    int pin = -1;
    
    if (strcmp(deviceCode, DEVICE_LIGHT) == 0) pin = LIGHT_PIN;
    else if (strcmp(deviceCode, DEVICE_DOOR) == 0) pin = DOOR_PIN;
    else if (strcmp(deviceCode, DEVICE_FAN) == 0) pin = FAN_PIN;
    
    if (pin >= 0) {
        digitalWrite(pin, state ? HIGH : LOW);
        publishRelayStatus(deviceCode, state);
        Serial.printf("🔌 %s: %s\n", deviceCode, state ? "ON" : "OFF");
    }
}

// ==================== MQTT CALLBACK ====================
void mqttCallback(char* topic, byte* payload, unsigned int length) {
    // Parse payload
    char message[length + 1];
    memcpy(message, payload, length);
    message[length] = '\0';
    
    Serial.printf("📨 [%s]: %s\n", topic, message);
    
    // Parse JSON
    StaticJsonDocument<128> doc;
    DeserializationError error = deserializeJson(doc, message);
    if (error) {
        Serial.println("❌ JSON parse error");
        return;
    }
    
    // Lấy giá trị
    const char* value = doc["value"];
    if (!value) return;
    
    bool state = (strcmp(value, "on") == 0 || strcmp(value, "1") == 0);
    
    // Xác định device từ topic
    String topicStr = String(topic);
    
    if (topicStr.endsWith(DEVICE_LIGHT)) {
        controlRelay(DEVICE_LIGHT, state);
    }
    else if (topicStr.endsWith(DEVICE_DOOR)) {
        controlRelay(DEVICE_DOOR, state);
    }
    else if (topicStr.endsWith(DEVICE_FAN)) {
        controlRelay(DEVICE_FAN, state);
    }
}

// ==================== KẾT NỐI ====================
void connectWiFi() {
    Serial.print("🔌 Connecting to WiFi");
    WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
    
    while (WiFi.status() != WL_CONNECTED) {
        delay(500);
        Serial.print(".");
    }
    
    Serial.println();
    Serial.print("✅ WiFi connected: ");
    Serial.println(WiFi.localIP());
}

void connectMQTT() {
    while (!mqtt.connected()) {
        Serial.print("🔌 Connecting to MQTT...");
        
        String clientId = "ESP-" + String(random(0xffff), HEX);
        
        if (mqtt.connect(clientId.c_str())) {
            Serial.println("✅ Connected!");
            
            // Subscribe các topic điều khiển
            mqtt.subscribe(getTopic("control", DEVICE_LIGHT).c_str());
            mqtt.subscribe(getTopic("control", DEVICE_DOOR).c_str());
            mqtt.subscribe(getTopic("control", DEVICE_FAN).c_str());
            
            Serial.println("📡 Subscribed to control topics");
        } else {
            Serial.printf("❌ Failed, rc=%d. Retry in 5s...\n", mqtt.state());
            delay(5000);
        }
    }
}

// ==================== ĐỌC SENSOR ====================
void readAndPublishSensors() {
    // Đọc DHT
    float temperature = dht.readTemperature();
    float humidity = dht.readHumidity();
    
    if (!isnan(temperature)) {
        publishSensorValue(DEVICE_TEMP, temperature);
    }
    
    if (!isnan(humidity)) {
        publishSensorValue(DEVICE_HUMID, humidity);
    }
    
    // Đọc Gas (MQ-2)
    int gasValue = analogRead(GAS_PIN);
    float gasPPM = map(gasValue, 0, 4095, 0, 1000);  // Chuyển đổi sang ppm
    publishSensorValue(DEVICE_GAS, gasPPM);
    
    // Đọc Fire sensor
    int fireValue = analogRead(FIRE_PIN);
    float fireLevel = map(fireValue, 0, 4095, 100, 0);  // 100 = cháy, 0 = bình thường
    publishSensorValue(DEVICE_FIRE, fireLevel);
}

// ==================== SETUP & LOOP ====================
void setup() {
    Serial.begin(115200);
    Serial.println("\n🏠 Smart Home ESP32 Starting...");
    
    // Khởi tạo GPIO
    pinMode(LIGHT_PIN, OUTPUT);
    pinMode(DOOR_PIN, OUTPUT);
    pinMode(FAN_PIN, OUTPUT);
    
    digitalWrite(LIGHT_PIN, LOW);
    digitalWrite(DOOR_PIN, LOW);
    digitalWrite(FAN_PIN, LOW);
    
    // Khởi tạo DHT
    dht.begin();
    
    // Kết nối WiFi
    connectWiFi();
    
    // Cấu hình MQTT
    mqtt.setServer(MQTT_BROKER, MQTT_PORT);
    mqtt.setCallback(mqttCallback);
    
    // Kết nối MQTT
    connectMQTT();
    
    Serial.println("✅ System Ready!");
}

void loop() {
    // Kiểm tra kết nối
    if (!mqtt.connected()) {
        connectMQTT();
    }
    mqtt.loop();
    
    // Đọc và gửi sensor
    unsigned long now = millis();
    if (now - lastSensorRead >= SENSOR_INTERVAL) {
        lastSensorRead = now;
        readAndPublishSensors();
    }
}
```

---

## Thư viện cần cài đặt (Arduino IDE)

1. **PubSubClient** - MQTT client
2. **ArduinoJson** - JSON parser
3. **DHT sensor library** - Đọc DHT11/DHT22

## Sơ đồ kết nối

```
ESP32/ESP8266
│
├── GPIO 4  ──── DHT11/DHT22 (Data)
├── GPIO 34 ──── MQ-2 Gas Sensor (Analog)
├── GPIO 35 ──── Flame Sensor (Analog)
│
├── GPIO 16 ──── Relay 1 (Đèn)
├── GPIO 17 ──── Relay 2 (Cửa)
└── GPIO 18 ──── Relay 3 (Quạt)
```

## Test với MQTT Explorer

1. Kết nối đến `103.252.136.205:1883`
2. Subscribe: `apikey/78aad22403acfc3e2fe4485532b2a0ca7201f3f585eb6c3a99457305b90075ca/#`
3. Publish test:
   - Topic: `apikey/78aad22403acfc3e2fe4485532b2a0ca7201f3f585eb6c3a99457305b90075ca/receiver/v7`
   - Payload: `{"value": 25.5}`

---

**Dashboard:** https://192.168.17.128:8443/dashboard/

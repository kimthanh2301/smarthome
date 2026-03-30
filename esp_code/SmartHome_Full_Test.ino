/*
 * ==========================================
 * SMART HOME ESP32 - FULL TEST
 * User: pcthuoc
 * ==========================================
 * 
 * RELAY + NÚT NHẤN:
 * - Đèn:  Relay=16, Button=13, Code=v17
 * - Cửa:  Relay=17, Button=14, Code=v2
 * - Quạt: Relay=18, Button=15, Code=v3
 * 
 * SENSOR:
 * - AHT20: SDA=5, SCL=4 (Nhiệt độ v7, Độ ẩm v6)
 * - Gas:   GPIO32 (Analog), Code=v5
 * - Flame: GPIO33 (Digital), Code=v4
 * - PIR:   GPIO12 (Digital)
 * 
 * ==========================================
 */

#include <WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include <Wire.h>
#include <AHT20.h>

// ==================== WIFI ====================
const char* WIFI_SSID = "doantotnghiep";
const char* WIFI_PASSWORD = "123456789";

// ==================== MQTT ====================
const char* MQTT_BROKER = "103.252.136.205";
const int MQTT_PORT = 1883;
const char* API_KEY = "78aad22403acfc3e2fe4485532b2a0ca7201f3f585eb6c3a99457305b90075ca";
const char* MQTT_USER = "78aad22403acfc3e2fe4485532b2a0ca7201f3f585eb6c3a99457305b90075ca";  // API_KEY làm username
const char* MQTT_PASS = "";  // Password rỗng

// ==================== DEVICE CODES ====================
const char* CODE_LIGHT = "v17";   // Đèn
const char* CODE_DOOR = "v2";     // Cửa
const char* CODE_FAN = "v3";      // Quạt
const char* CODE_TEMP = "v7";     // Nhiệt độ
const char* CODE_HUMID = "v6";    // Độ ẩm
const char* CODE_GAS = "v5";      // Khí Gas
const char* CODE_FIRE = "v4";     // Báo cháy
const char* CODE_PIR = "v1";      // Chuyển động (PIR)

// ==================== GPIO RELAY ====================
#define LIGHT_RELAY 16
#define DOOR_RELAY 17
#define FAN_RELAY 18

// ==================== GPIO BUTTON ====================
#define LIGHT_BTN 13
#define DOOR_BTN 14
#define FAN_BTN 15

// ==================== GPIO SENSOR ====================
#define SDA_PIN 5
#define SCL_PIN 4
#define GAS_PIN 32
#define FLAME_PIN 33
#define PIR_PIN 12

// ==================== BIẾN ====================
WiFiClient espClient;
PubSubClient mqtt(espClient);
AHT20 aht20;

// Trạng thái relay
bool lightState = false;
bool doorState = false;
bool fanState = false;

// Trạng thái nút trước đó
bool lastLightBtn = HIGH;
bool lastDoorBtn = HIGH;
bool lastFanBtn = HIGH;

// Thời gian
unsigned long lastSensorSend = 0;
const long SENSOR_INTERVAL = 5000;  // 5 giây

// Ngưỡng cảnh báo
const int GAS_THRESHOLD = 300;      // Ngưỡng gas nguy hiểm (ppm)
bool emergencyMode = false;         // Chế độ khẩn cấp

// Tự động bật đèn khi có chuyển động
unsigned long lightAutoOffTime = 0;
bool lightAutoMode = false;
const int LIGHT_AUTO_DURATION = 30000;  // 30 giây sau khi hết chuyển động thì tắt đèn

// ==================== TẠO TOPIC ====================
String getReceiverTopic(const char* code) {
    return String("apikey/") + API_KEY + "/receiver/" + code;
}

String getControlTopic(const char* code) {
    return String("apikey/") + API_KEY + "/control/" + code;
}

// ==================== GỬI SENSOR ====================
void sendSensorValue(const char* code, float value) {
    String topic = getReceiverTopic(code);
    
    StaticJsonDocument<64> doc;
    doc["value"] = value;
    
    char payload[64];
    serializeJson(doc, payload);
    
    mqtt.publish(topic.c_str(), payload);
    Serial.printf("📤 [%s] = %.2f\n", code, value);
}

// ==================== GỬI RELAY ====================
void sendRelayStatus(const char* code, bool state) {
    String topic = getReceiverTopic(code);
    
    StaticJsonDocument<64> doc;
    doc["value"] = state ? "on" : "off";
    doc["status"] = state ? "on" : "off";
    
    char payload[64];
    serializeJson(doc, payload);
    
    mqtt.publish(topic.c_str(), payload);
    Serial.printf("📤 [%s] = %s\n", code, state ? "ON" : "OFF");
}

// ==================== ĐIỀU KHIỂN RELAY ====================
void setLight(bool state) {
    lightState = state;
    digitalWrite(LIGHT_RELAY, state ? HIGH : LOW);
    sendRelayStatus(CODE_LIGHT, state);
    Serial.printf("💡 Đèn: %s\n", state ? "BẬT" : "TẮT");
}

void setDoor(bool state) {
    doorState = state;
    digitalWrite(DOOR_RELAY, state ? HIGH : LOW);
    sendRelayStatus(CODE_DOOR, state);
    Serial.printf("🚪 Cửa: %s\n", state ? "MỞ" : "ĐÓNG");
}

// Mở cửa tạm thời (5 giây rồi đóng) - dùng cho nhận diện khuôn mặt
unsigned long doorTempOpenTime = 0;
bool doorTempMode = false;
const int DOOR_TEMP_DURATION = 5000;  // 5 giây

void setDoorTemp() {
    Serial.println("🚪👤 Mở cửa tạm thời (nhận diện mặt)...");
    setDoor(true);
    doorTempMode = true;
    doorTempOpenTime = millis();
}

void checkDoorTemp() {
    // Kiểm tra và đóng cửa sau 5 giây
    if (doorTempMode && (millis() - doorTempOpenTime >= DOOR_TEMP_DURATION)) {
        Serial.println("🚪 Tự động đóng cửa sau 5 giây");
        setDoor(false);
        doorTempMode = false;
    }
}

void checkLightAuto() {
    // Tự động tắt đèn sau 30 giây không có chuyển động
    if (lightAutoMode && lightState && (millis() - lightAutoOffTime >= LIGHT_AUTO_DURATION)) {
        Serial.println("💡 Hết chuyển động → Tự động tắt đèn");
        setLight(false);
        lightAutoMode = false;
    }
}

void setFan(bool state) {
    fanState = state;
    digitalWrite(FAN_RELAY, state ? HIGH : LOW);
    sendRelayStatus(CODE_FAN, state);
    Serial.printf("🌀 Quạt: %s\n", state ? "BẬT" : "TẮT");
}

// ==================== MQTT CALLBACK ====================
void mqttCallback(char* topic, byte* payload, unsigned int length) {
    char message[length + 1];
    memcpy(message, payload, length);
    message[length] = '\0';
    
    Serial.printf("\n📨 Nhận: %s\n", message);
    
    StaticJsonDocument<128> doc;
    if (deserializeJson(doc, message)) return;
    
    const char* value = doc["value"];
    if (!value) return;
    
    String topicStr = String(topic);
    
    // Xử lý lệnh điều khiển
    if (topicStr.indexOf(CODE_LIGHT) > 0) {
        bool state = (strcmp(value, "on") == 0) || (strcmp(value, "1") == 0);
        setLight(state);
    }
    else if (topicStr.indexOf(CODE_DOOR) > 0) {
        // Lệnh mở cửa tạm thời (từ nhận diện khuôn mặt)
        if (strcmp(value, "door_temp") == 0) {
            setDoorTemp();
        } else {
            bool state = (strcmp(value, "on") == 0) || (strcmp(value, "1") == 0);
            doorTempMode = false;  // Hủy chế độ tạm thời nếu có lệnh thủ công
            setDoor(state);
        }
    }
    else if (topicStr.indexOf(CODE_FAN) > 0) {
        bool state = (strcmp(value, "on") == 0) || (strcmp(value, "1") == 0);
        setFan(state);
    }
}

// ==================== KẾT NỐI WIFI ====================
void connectWiFi() {
    Serial.print("🔌 Kết nối WiFi: ");
    Serial.println(WIFI_SSID);
    
    WiFi.mode(WIFI_STA);
    WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
    
    int count = 0;
    while (WiFi.status() != WL_CONNECTED && count < 30) {
        delay(500);
        Serial.print(".");
        count++;
    }
    
    if (WiFi.status() == WL_CONNECTED) {
        Serial.println();
        Serial.print("✅ WiFi OK! IP: ");
        Serial.println(WiFi.localIP());
    } else {
        Serial.println("\n❌ WiFi FAIL! Restart...");
        delay(3000);
        ESP.restart();
    }
}

// ==================== KẾT NỐI MQTT ====================
void connectMQTT() {
    while (!mqtt.connected()) {
        Serial.print("🔌 Kết nối MQTT...");
        
        String clientId = "ESP-pcthuoc-" + String(random(0xffff), HEX);
        
        // Kết nối với username = API_KEY, password = ""
        if (mqtt.connect(clientId.c_str(), MQTT_USER, MQTT_PASS)) {
            Serial.println("✅ OK!");
            
            // Subscribe điều khiển relay
            mqtt.subscribe(getControlTopic(CODE_LIGHT).c_str());
            mqtt.subscribe(getControlTopic(CODE_DOOR).c_str());
            mqtt.subscribe(getControlTopic(CODE_FAN).c_str());
            
            Serial.println("📡 Subscribed control topics");
            
            // Đồng bộ trạng thái relay hiện tại lên MQTT
            Serial.println("🔄 Đồng bộ trạng thái relay lên MQTT...");
            sendRelayStatus(CODE_LIGHT, lightState);
            sendRelayStatus(CODE_DOOR, doorState);
            sendRelayStatus(CODE_FAN, fanState);
            Serial.println("✅ Đã đồng bộ trạng thái relay!");
            
        } else {
            Serial.printf("❌ Lỗi: %d. Thử lại...\n", mqtt.state());
            delay(3000);
        }
    }
}

// ==================== ĐỌC NÚT NHẤN ====================
void readButtons() {
    // Nút Đèn
    bool lightBtn = digitalRead(LIGHT_BTN);
    if (lastLightBtn == HIGH && lightBtn == LOW) {
        delay(50);
        setLight(!lightState);
    }
    lastLightBtn = lightBtn;
    
    // Nút Cửa
    bool doorBtn = digitalRead(DOOR_BTN);
    if (lastDoorBtn == HIGH && doorBtn == LOW) {
        delay(50);
        setDoor(!doorState);
    }
    lastDoorBtn = doorBtn;
    
    // Nút Quạt
    bool fanBtn = digitalRead(FAN_BTN);
    if (lastFanBtn == HIGH && fanBtn == LOW) {
        delay(50);
        setFan(!fanState);
    }
    lastFanBtn = fanBtn;
}

// ==================== ĐỌC VÀ GỬI SENSOR ====================
void readAndSendSensors() {
    Serial.println("\n📊 Đọc sensor...");
    
    // AHT20 - Nhiệt độ & Độ ẩm
    float temp = aht20.getTemperature();
    float humid = aht20.getHumidity();
    
    sendSensorValue(CODE_TEMP, temp);
    sendSensorValue(CODE_HUMID, humid);
    Serial.printf("   🌡️ Nhiệt độ: %.1f°C\n", temp);
    Serial.printf("   💧 Độ ẩm: %.1f%%\n", humid);
    
    // MQ-2 Gas
    int gasRaw = analogRead(GAS_PIN);
    float gasPPM = map(gasRaw, 0, 4095, 0, 1000);
    sendSensorValue(CODE_GAS, gasPPM);
    Serial.printf("   💨 Gas: %.0f ppm\n", gasPPM);
    
    // Flame sensor (0 = có lửa)
    int flameRaw = digitalRead(FLAME_PIN);
    float fireLevel = (flameRaw == LOW) ? 100 : 0;
    sendSensorValue(CODE_FIRE, fireLevel);
    Serial.printf("   🔥 Lửa: %s\n", fireLevel > 0 ? "CÓ LỬA!" : "Bình thường");
    
    // PIR - Chuyển động
    int pirValue = digitalRead(PIR_PIN);
    float motionLevel = pirValue ? 100 : 0;
    sendSensorValue(CODE_PIR, motionLevel);
    Serial.printf("   🚶 PIR: %s\n", pirValue ? "CÓ NGƯỜI!" : "Không");
    
    // ==================== TỰ ĐỘNG BẬT ĐÈN KHI CÓ CHUYỂN ĐỘNG ====================
    if (pirValue && !emergencyMode) {
        if (!lightState) {
            Serial.println("🚶💡 Phát hiện chuyển động → Bật đèn!");
            setLight(true);
            lightAutoMode = true;
        }
        // Reset thời gian tắt đèn
        lightAutoOffTime = millis();
    }
    
    // ==================== XỬ LÝ KHẨN CẤP ====================
    bool isDanger = (gasPPM >= GAS_THRESHOLD) || (fireLevel > 0);
    
    if (isDanger && !emergencyMode) {
        // Phát hiện nguy hiểm → BẬT tất cả
        Serial.println("\n🚨🚨🚨 CẢNH BÁO NGUY HIỂM! 🚨🚨🚨");
        Serial.println("🔴 Tự động BẬT đèn, mở cửa, bật quạt!");
        emergencyMode = true;
        
        if (!lightState) setLight(true);
        if (!doorState) setDoor(true);
        if (!fanState) setFan(true);
    }
    else if (!isDanger && emergencyMode) {
        // Hết nguy hiểm → TẮT tất cả
        Serial.println("\n✅ An toàn! Tự động TẮT các thiết bị.");
        emergencyMode = false;
        
        if (lightState) setLight(false);
        if (doorState) setDoor(false);
        if (fanState) setFan(false);
    }
}

// ==================== SETUP ====================
void setup() {
    Serial.begin(115200);
    delay(100);
    
    Serial.println();
    Serial.println("==========================================");
    Serial.println("🏠 SMART HOME ESP32 - pcthuoc");
    Serial.println("==========================================");
    
    // GPIO Relay
    pinMode(LIGHT_RELAY, OUTPUT);
    pinMode(DOOR_RELAY, OUTPUT);
    pinMode(FAN_RELAY, OUTPUT);
    digitalWrite(LIGHT_RELAY, LOW);
    digitalWrite(DOOR_RELAY, LOW);
    digitalWrite(FAN_RELAY, LOW);
    
    // GPIO Button (Pull-up)
    pinMode(LIGHT_BTN, INPUT_PULLUP);
    pinMode(DOOR_BTN, INPUT_PULLUP);
    pinMode(FAN_BTN, INPUT_PULLUP);
    
    // GPIO Sensor
    pinMode(GAS_PIN, INPUT);
    pinMode(FLAME_PIN, INPUT);
    pinMode(PIR_PIN, INPUT);
    
    // AHT20
    Wire.begin(SDA_PIN, SCL_PIN);
    if (aht20.begin() == false) {
        Serial.println("⚠️ AHT20 không tìm thấy!");
    } else {
        Serial.println("✅ AHT20 OK!");
    }
    
    // WiFi
    connectWiFi();
    
    // MQTT
    mqtt.setServer(MQTT_BROKER, MQTT_PORT);
    mqtt.setCallback(mqttCallback);
    mqtt.setBufferSize(512);
    connectMQTT();
    
    Serial.println();
    Serial.println("==========================================");
    Serial.println("✅ HỆ THỐNG SẴN SÀNG!");
    Serial.println("==========================================");
}

// ==================== LOOP ====================
void loop() {
    // Kiểm tra WiFi
    if (WiFi.status() != WL_CONNECTED) {
        connectWiFi();
    }
    
    // Kiểm tra MQTT
    if (!mqtt.connected()) {
        connectMQTT();
    }
    mqtt.loop();
    
    // Đọc nút nhấn
    readButtons();
    
    // Kiểm tra đóng cửa tự động (sau khi nhận diện mặt)
    checkDoorTemp();
    
    // Kiểm tra tắt đèn tự động (sau khi hết chuyển động)
    checkLightAuto();
    
    // Gửi sensor định kỳ
    unsigned long now = millis();
    if (now - lastSensorSend >= SENSOR_INTERVAL) {
        lastSensorSend = now;
        readAndSendSensors();
    }
    
    delay(10);
}

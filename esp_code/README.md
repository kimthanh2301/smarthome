# ESP32 Smart Home - Sơ đồ chân GPIO

## User: pcthuoc
**API Key:** `78aad22403acfc3e2fe4485532b2a0ca7201f3f585eb6c3a99457305b90075ca`

---

## 🔌 RELAY (Output)

| Thiết bị | Device Code | GPIO Relay | GPIO Nút nhấn |
|----------|-------------|------------|---------------|
| Đèn | v17 | 16 | 13 |
| Cửa | v2 | 17 | 14 |
| Quạt | v3 | 18 | 15 |

---

## 📊 SENSOR (Input)

| Thiết bị | Device Code | GPIO | Loại |
|----------|-------------|------|------|
| Nhiệt độ | v7 | SDA:5, SCL:4 | AHT20 (I2C) |
| Độ ẩm | v6 | SDA:5, SCL:4 | AHT20 (I2C) |
| Khí Gas | v5 | 32 | MQ-2 (Analog) |
| Báo cháy | v4 | 33 | Flame (Digital) |
| PIR | - | 12 | PIR (Digital) |

---

## 📝 GHI CHÚ

```
Cập nhật GPIO ở đây, sau đó báo tôi code lại!
```

---

## 🔗 MQTT Topics

- **Gửi dữ liệu:** `apikey/{API_KEY}/receiver/{Vn}`
- **Nhận điều khiển:** `apikey/{API_KEY}/control/{Vn}`
- **Broker:** `103.252.136.205:1883`

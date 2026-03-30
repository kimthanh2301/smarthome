#!/usr/bin/env python3
"""
Script tạo dữ liệu mẫu cho các cảm biến
Chạy: python3 generate_sensor_data.py
"""

import os
import sys
import django
import random
from datetime import timedelta

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
django.setup()

from django.utils import timezone
from devices.models import Device, SensorLog


def generate_data(device_code, hours=24, interval_minutes=30, min_val=0, max_val=100, value_type='float'):
    """
    Tạo dữ liệu mẫu cho sensor
    - device_code: mã thiết bị (v4, v5, v6, v7)
    - hours: số giờ dữ liệu
    - interval_minutes: khoảng cách phút giữa các bản ghi
    - min_val, max_val: khoảng giá trị
    - value_type: 'float', 'int', 'binary'
    """
    try:
        device = Device.objects.get(device_code=device_code)
    except Device.DoesNotExist:
        print(f"❌ Không tìm thấy thiết bị {device_code}")
        return 0
    
    # Xóa dữ liệu cũ (nếu muốn)
    # SensorLog.objects.filter(device=device).delete()
    
    now = timezone.now()
    start_time = now - timedelta(hours=hours)
    
    count = 0
    current_time = start_time
    prev_value = random.uniform(min_val, max_val)
    
    while current_time <= now:
        # Tạo giá trị với biến động tự nhiên
        if value_type == 'binary':
            # Cho cảm biến báo cháy - hầu hết là 0, thỉnh thoảng có 1
            value = 1 if random.random() < 0.05 else 0
        elif value_type == 'int':
            # Biến động ±5 từ giá trị trước
            change = random.randint(-5, 5)
            value = max(min_val, min(max_val, int(prev_value + change)))
            prev_value = value
        else:
            # Float - biến động ±2 từ giá trị trước
            change = random.uniform(-2, 2)
            value = max(min_val, min(max_val, prev_value + change))
            value = round(value, 1)
            prev_value = value
        
        SensorLog.objects.create(
            device=device,
            value=value,
            timestamp=current_time
        )
        count += 1
        current_time += timedelta(minutes=interval_minutes)
    
    print(f"✅ Đã tạo {count} bản ghi cho {device.name} ({device_code})")
    return count


if __name__ == '__main__':
    print("=" * 50)
    print("🚀 Bắt đầu tạo dữ liệu mẫu cho cảm biến")
    print(f"⏰ Thời gian hiện tại (VN): {timezone.localtime(timezone.now()).strftime('%d/%m/%Y %H:%M:%S')}")
    print("=" * 50)
    
    total = 0
    
    # v4 - Báo cháy: binary (0/1), ít khi có cháy
    total += generate_data('v4', hours=24, interval_minutes=5, min_val=0, max_val=1, value_type='binary')
    
    # v5 - Khí Gas: 0-1000 ppm
    total += generate_data('v5', hours=24, interval_minutes=5, min_val=0, max_val=100, value_type='int')
    
    # v6 - Độ ẩm: 40-90%
    total += generate_data('v6', hours=24, interval_minutes=5, min_val=40, max_val=90, value_type='float')
    
    # v7 - Nhiệt độ: 20-40°C
    total += generate_data('v7', hours=24, interval_minutes=5, min_val=22, max_val=38, value_type='float')
    
    print("=" * 50)
    print(f"🎉 Hoàn thành! Tổng cộng {total} bản ghi")
    print("=" * 50)

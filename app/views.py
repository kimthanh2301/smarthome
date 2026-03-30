# -*- encoding: utf-8 -*-
"""
Copyright (c) 2019 - present AppSeed.us
"""

from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404, redirect
from django.template import loader
from django.http import HttpResponse, JsonResponse
from django import template
from django.views.decorators.http import require_POST
from django.utils import timezone
from datetime import timedelta
from devices.models import Device, SensorLog
import json


@login_required(login_url="/login/")
def index(request):
    context = {'segment': 'index'}

    html_template = loader.get_template('index.html')
    return HttpResponse(html_template.render(context, request))


@login_required(login_url="/login/")
def about_page(request):
    """Trang giới thiệu đồ án"""
    context = {'segment': 'about'}
    return render(request, 'about.html', context)


@login_required(login_url="/login/")
def database_schema_page(request):
    """Trang sơ đồ cấu trúc database"""
    context = {'segment': 'database_schema'}
    return render(request, 'database_schema.html', context)


@login_required(login_url="/login/")
def hardware_flow_page(request):
    """Trang lưu đồ hoạt động phần cứng"""
    context = {'segment': 'hardware_flow'}
    return render(request, 'hardware_flow.html', context)


@login_required(login_url="/login/")
def face_recognition_flow_page(request):
    """Trang lưu đồ thuật toán nhận diện khuôn mặt"""
    context = {'segment': 'face_recognition_flow'}
    return render(request, 'face_recognition_flow.html', context)


@login_required(login_url="/login/")
def web_build_guide_page(request):
    """Trang hướng dẫn build hệ thống web"""
    context = {'segment': 'web_build_guide'}
    return render(request, 'web_build_guide.html', context)


@login_required(login_url="/login/")
def esp32_hardware_guide_page(request):
    """Trang hướng dẫn phần cứng ESP32"""
    context = {'segment': 'esp32_hardware_guide'}
    return render(request, 'esp32_hardware_guide.html', context)


@login_required(login_url="/login/")
def realtime_dashboard(request):
    """Dashboard realtime với WebSocket"""
    relays = Device.objects.filter(user=request.user, device_type=Device.TYPE_RELAY)
    sensors = Device.objects.filter(user=request.user, device_type=Device.TYPE_SENSOR)
    
    # Lấy danh sách device_code còn trống
    available_codes = Device.get_available_codes(request.user)
    
    context = {
        'segment': 'dashboard',
        'relays': relays,
        'sensors': sensors,
        'total_devices': relays.count() + sensors.count(),
        'online_devices': Device.objects.filter(user=request.user, is_online=True).count(),
        'available_codes': available_codes,
    }
    return render(request, 'devices/dashboard.html', context)


@login_required(login_url="/login/")
def smart_home_dashboard(request):
    """Dashboard hiển thị tất cả thiết bị smart home của user"""
    relays = Device.objects.filter(user=request.user, device_type=Device.TYPE_RELAY)
    sensors = Device.objects.filter(user=request.user, device_type=Device.TYPE_SENSOR)
    
    # Lấy danh sách device_code còn trống
    available_codes = Device.get_available_codes(request.user)
    
    context = {
        'segment': 'smart_home',
        'relays': relays,
        'sensors': sensors,
        'total_devices': relays.count() + sensors.count(),
        'online_devices': Device.objects.filter(user=request.user, is_online=True).count(),
        'available_codes': available_codes,
    }
    return render(request, 'devices/dashboard.html', context)


@login_required(login_url="/login/")
@require_POST
def toggle_relay(request, device_id):
    """API để bật/tắt relay"""
    device = get_object_or_404(Device, id=device_id, user=request.user, device_type=Device.TYPE_RELAY)
    
    # Toggle value
    new_value = '0' if device.value == '1' else '1'
    device.value = new_value
    device.save()
    
    try:
        from mqtt.mqtt_client import get_mqtt_client
        from customers.models import Profile
        
        profile = Profile.objects.filter(user=request.user).first()
        if profile and profile.api_key:
            mqtt_client = get_mqtt_client()
            
            if not mqtt_client.connected:
                mqtt_client.connect()
                mqtt_client.start_loop()
                import time
                for _ in range(10):
                    if mqtt_client.connected:
                        break
                    time.sleep(0.1)
            
            control_value = 'on' if new_value == '1' else 'off'
            mqtt_client.control_device(profile.api_key, device.device_code, control_value)
    except Exception:
        pass
    
    return JsonResponse({
        'success': True,
        'device_id': device.id,
        'value': device.value,
        'is_on': device.is_on,
        'display_value': device.display_value
    })


@login_required(login_url="/login/")
@require_POST
def add_device(request):
    """Thêm thiết bị mới"""
    from django.contrib import messages
    
    device_code = request.POST.get('device_code', '').strip()
    name = request.POST.get('name', '').strip()
    device_type = request.POST.get('device_type', '')
    unit = request.POST.get('unit', '').strip()
    value = request.POST.get('value', '0').strip() or '0'
    enable_logging = request.POST.get('enable_logging') == '1'
    
    if not device_code or not name or not device_type:
        messages.error(request, 'Vui lòng điền đầy đủ thông tin!')
        return redirect('smart_home')
    
    if device_type not in [Device.TYPE_RELAY, Device.TYPE_SENSOR]:
        messages.error(request, 'Loại thiết bị không hợp lệ!')
        return redirect('smart_home')
    
    # Kiểm tra device_code đã tồn tại chưa
    if Device.objects.filter(user=request.user, device_code=device_code).exists():
        messages.error(request, f'Mã thiết bị {device_code} đã được sử dụng!')
        return redirect('smart_home')
    
    # Tạo thiết bị mới
    device = Device.objects.create(
        user=request.user,
        device_code=device_code,
        name=name,
        device_type=device_type,
        value=value,
        unit=unit if device_type == Device.TYPE_SENSOR else None,
        enable_logging=enable_logging if device_type == Device.TYPE_SENSOR else False,
        is_online=True
    )
    
    messages.success(request, f'Đã thêm thiết bị "{name}" ({device_code}) thành công!')
    return redirect('smart_home')


@login_required(login_url="/login/")
@require_POST
def delete_device(request, device_id):
    """Xóa thiết bị"""
    from django.contrib import messages
    
    device = get_object_or_404(Device, id=device_id, user=request.user)
    device_name = device.name
    device.delete()
    
    messages.success(request, f'Đã xóa thiết bị "{device_name}" thành công!')
    return redirect('smart_home')


@login_required(login_url="/login/")
@require_POST
def edit_device(request, device_id):
    """Chỉnh sửa thiết bị"""
    from django.contrib import messages
    
    device = get_object_or_404(Device, id=device_id, user=request.user)
    
    device_code = request.POST.get('device_code', '').strip()
    name = request.POST.get('name', '').strip()
    unit = request.POST.get('unit', '').strip()
    enable_logging = request.POST.get('enable_logging') == '1'
    
    if not device_code or not name:
        messages.error(request, 'Vui lòng điền đầy đủ thông tin!')
        return redirect('smart_home')
    
    # Kiểm tra device_code có bị trùng không (ngoại trừ device hiện tại)
    if Device.objects.filter(user=request.user, device_code=device_code).exclude(id=device_id).exists():
        messages.error(request, f'Mã thiết bị {device_code} đã được sử dụng!')
        return redirect('smart_home')
    
    device.device_code = device_code
    device.name = name
    if device.device_type == Device.TYPE_SENSOR:
        device.unit = unit
        device.enable_logging = enable_logging
    device.save()
    
    messages.success(request, f'Đã cập nhật thiết bị "{name}" thành công!')
    return redirect('smart_home')


@login_required(login_url="/login/")
def get_device_info(request, device_id):
    """API lấy thông tin thiết bị để edit"""
    device = get_object_or_404(Device, id=device_id, user=request.user)
    
    # Lấy available codes (bao gồm cả code hiện tại của device)
    available_codes = Device.get_available_codes(request.user, exclude_device=device)
    
    return JsonResponse({
        'success': True,
        'device': {
            'id': device.id,
            'device_code': device.device_code or '',
            'name': device.name,
            'device_type': device.device_type,
            'unit': device.unit or '',
            'enable_logging': device.enable_logging,
        },
        'available_codes': available_codes
    })


@login_required(login_url="/login/")
def get_chart_data(request):
    """API lấy dữ liệu đồ thị cho các sensor có enable_logging=True"""
    # Lấy khoảng thời gian từ query params
    hours = int(request.GET.get('hours', 24))
    
    # Giới hạn tối đa 7 ngày
    if hours > 168:
        hours = 168
    
    # Thời điểm bắt đầu
    start_time = timezone.now() - timedelta(hours=hours)
    
    # Lấy tất cả sensor có enable_logging=True của user
    sensors = Device.objects.filter(
        user=request.user,
        device_type=Device.TYPE_SENSOR,
        enable_logging=True
    )
    
    series_data = []
    
    for sensor in sensors:
        # Lấy logs trong khoảng thời gian
        logs = SensorLog.objects.filter(
            device=sensor,
            timestamp__gte=start_time
        ).order_by('timestamp')
        
        # Format data cho ApexCharts
        data_points = []
        for log in logs:
            # Convert timestamp sang milliseconds cho JavaScript
            timestamp_ms = int(log.timestamp.timestamp() * 1000)
            try:
                value = float(log.value)
            except (ValueError, TypeError):
                value = 0
            data_points.append({
                'x': timestamp_ms,
                'y': round(value, 2)
            })
        
        # Thêm vào series nếu có data
        if data_points:
            series_data.append({
                'name': sensor.name,
                'device_code': sensor.device_code,
                'unit': sensor.unit or '',
                'data': data_points
            })
    
    return JsonResponse({
        'success': True,
        'series': series_data,
        'start_time': start_time.isoformat(),
        'end_time': timezone.now().isoformat()
    })


@login_required(login_url="/login/")
def pages(request):
    context = {}
    # All resource paths end in .html.
    # Pick out the html file name from the url. And load that template.
    try:

        load_template = request.path.split('/')[-1]
        context['segment'] = load_template

        html_template = loader.get_template(load_template)
        return HttpResponse(html_template.render(context, request))

    except template.TemplateDoesNotExist:

        html_template = loader.get_template('page-404.html')
        return HttpResponse(html_template.render(context, request))

    except:

        html_template = loader.get_template('page-500.html')
        return HttpResponse(html_template.render(context, request))

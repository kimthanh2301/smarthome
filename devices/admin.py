from django.contrib import admin
from django.shortcuts import render, redirect
from django.urls import path
from django.contrib import messages
from django import forms
from django.utils import timezone
from datetime import datetime, timedelta
import csv
import io
from .models import Device, SensorLog


class CsvImportForm(forms.Form):
    """Form upload file CSV"""
    csv_file = forms.FileField(label='File CSV')
    

class GenerateSampleDataForm(forms.Form):
    """Form tạo dữ liệu mẫu"""
    device = forms.ModelChoiceField(
        queryset=Device.objects.filter(device_type=Device.TYPE_SENSOR),
        label='Cảm biến'
    )
    hours = forms.IntegerField(
        initial=24, 
        min_value=1, 
        max_value=168,
        label='Số giờ dữ liệu'
    )
    interval_minutes = forms.IntegerField(
        initial=30,
        min_value=1,
        max_value=60,
        label='Khoảng cách (phút)'
    )
    min_value = forms.FloatField(initial=20, label='Giá trị min')
    max_value = forms.FloatField(initial=35, label='Giá trị max')


@admin.register(Device)
class DeviceAdmin(admin.ModelAdmin):
    list_display = ['device_code', 'name', 'user', 'device_type', 'value', 'unit', 'is_online', 'enable_logging', 'updated_at']
    list_filter = ['device_type', 'is_online', 'enable_logging', 'user']
    search_fields = ['name', 'user__username', 'device_code']
    readonly_fields = ['created_at', 'updated_at']
    list_editable = ['enable_logging']  # Cho phép sửa nhanh từ list
    
    fieldsets = (
        ('Thông tin cơ bản', {
            'fields': ('user', 'device_code', 'name', 'device_type')
        }),
        ('Giá trị', {
            'fields': ('value', 'unit', 'is_online', 'enable_logging')
        }),
        ('Thời gian', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(SensorLog)
class SensorLogAdmin(admin.ModelAdmin):
    list_display = ['device', 'value', 'timestamp_vn', 'timestamp']
    list_filter = ['device', 'timestamp']
    search_fields = ['device__name']
    readonly_fields = ['timestamp']
    date_hierarchy = 'timestamp'
    change_list_template = 'admin/devices/sensorlog/change_list.html'
    
    def timestamp_vn(self, obj):
        """Hiển thị thời gian theo múi giờ Việt Nam"""
        return timezone.localtime(obj.timestamp).strftime('%d/%m/%Y %H:%M:%S')
    timestamp_vn.short_description = 'Thời gian (VN)'
    timestamp_vn.admin_order_field = 'timestamp'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('device')
    
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('import-csv/', self.admin_site.admin_view(self.import_csv), name='sensorlog_import_csv'),
            path('generate-sample/', self.admin_site.admin_view(self.generate_sample_data), name='sensorlog_generate_sample'),
        ]
        return custom_urls + urls
    
    def import_csv(self, request):
        """Import dữ liệu từ file CSV"""
        if request.method == 'POST':
            form = CsvImportForm(request.POST, request.FILES)
            if form.is_valid():
                csv_file = request.FILES['csv_file']
                
                try:
                    # Đọc file CSV
                    decoded_file = csv_file.read().decode('utf-8')
                    reader = csv.DictReader(io.StringIO(decoded_file))
                    
                    count = 0
                    for row in reader:
                        device_code = row.get('device_code', '').strip()
                        value = row.get('value', '0')
                        timestamp_str = row.get('timestamp', '')
                        
                        # Tìm device theo code
                        try:
                            device = Device.objects.get(device_code=device_code)
                        except Device.DoesNotExist:
                            continue
                        
                        # Parse timestamp (hỗ trợ nhiều format)
                        timestamp = None
                        if timestamp_str:
                            for fmt in ['%Y-%m-%d %H:%M:%S', '%d/%m/%Y %H:%M:%S', '%Y-%m-%dT%H:%M:%S']:
                                try:
                                    # Parse như local time (Vietnam)
                                    naive_dt = datetime.strptime(timestamp_str.strip(), fmt)
                                    # Gán timezone Vietnam
                                    timestamp = timezone.make_aware(naive_dt, timezone.get_current_timezone())
                                    break
                                except ValueError:
                                    continue
                        
                        if not timestamp:
                            timestamp = timezone.now()
                        
                        SensorLog.objects.create(
                            device=device,
                            value=float(value),
                            timestamp=timestamp
                        )
                        count += 1
                    
                    messages.success(request, f'Đã import {count} bản ghi thành công!')
                    return redirect('..')
                    
                except Exception as e:
                    messages.error(request, f'Lỗi: {str(e)}')
        else:
            form = CsvImportForm()
        
        context = {
            'form': form,
            'title': 'Import dữ liệu từ CSV',
            'opts': self.model._meta,
        }
        return render(request, 'admin/devices/sensorlog/import_csv.html', context)
    
    def generate_sample_data(self, request):
        """Tạo dữ liệu mẫu cho sensor"""
        import random
        
        if request.method == 'POST':
            form = GenerateSampleDataForm(request.POST)
            if form.is_valid():
                device = form.cleaned_data['device']
                hours = form.cleaned_data['hours']
                interval = form.cleaned_data['interval_minutes']
                min_val = form.cleaned_data['min_value']
                max_val = form.cleaned_data['max_value']
                
                # Tính thời gian bắt đầu (theo múi giờ hiện tại - Vietnam)
                now = timezone.now()
                start_time = now - timedelta(hours=hours)
                
                count = 0
                current_time = start_time
                
                while current_time <= now:
                    # Tạo giá trị ngẫu nhiên với biến động nhẹ
                    value = random.uniform(min_val, max_val)
                    
                    SensorLog.objects.create(
                        device=device,
                        value=round(value, 1),
                        timestamp=current_time
                    )
                    count += 1
                    current_time += timedelta(minutes=interval)
                
                messages.success(request, f'Đã tạo {count} bản ghi cho {device.name}!')
                return redirect('..')
        else:
            form = GenerateSampleDataForm()
        
        context = {
            'form': form,
            'title': 'Tạo dữ liệu mẫu cho cảm biến',
            'opts': self.model._meta,
        }
        return render(request, 'admin/devices/sensorlog/generate_sample.html', context)


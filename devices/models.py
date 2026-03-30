# -*- encoding: utf-8 -*-
from django.db import models
from django.contrib.auth.models import User
from django.utils.translation import gettext as _


class Device(models.Model):
    """
    Model lưu trữ thông tin thiết bị smart home
    - Relay: điều khiển bật/tắt (đèn, quạt, máy bơm...)
    - Sensor: đọc giá trị cảm biến (nhiệt độ, độ ẩm, khí ga, chuyển động...)
    """
    
    # Loại thiết bị
    TYPE_RELAY = 'relay'
    TYPE_SENSOR = 'sensor'
    TYPE_CHOICES = [
        (TYPE_RELAY, _('Relay (Bật/Tắt)')),
        (TYPE_SENSOR, _('Cảm biến')),
    ]
    
    # Số lượng device code tối đa
    MAX_DEVICE_CODE = 50
    
    # Fields
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='devices')
    device_code = models.CharField(
        _('Mã thiết bị'),
        max_length=10,
        help_text=_('VD: v1, v2, v3...')
    )
    name = models.CharField(_('Tên thiết bị'), max_length=100)
    device_type = models.CharField(
        _('Loại thiết bị'),
        max_length=20,
        choices=TYPE_CHOICES,
        default=TYPE_RELAY
    )
    
    # Giá trị linh hoạt - có thể lưu ON/OFF (1/0) hoặc giá trị số (nhiệt độ, độ ẩm...)
    value = models.CharField(
        _('Giá trị'),
        max_length=50,
        default='0',
        help_text=_('Relay: 0=OFF, 1=ON | Sensor: giá trị đo được')
    )
    
    # Đơn vị đo (cho sensor)
    unit = models.CharField(
        _('Đơn vị'),
        max_length=20,
        blank=True,
        null=True,
        help_text=_('VD: °C, %, ppm...')
    )
    
    # Trạng thái online/offline
    is_online = models.BooleanField(_('Đang hoạt động'), default=False)
    
    # Bật/tắt ghi log để hiển thị đồ thị
    enable_logging = models.BooleanField(_('Ghi log đồ thị'), default=False)
    
    # Thời gian
    created_at = models.DateTimeField(_('Ngày tạo'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Cập nhật lần cuối'), auto_now=True)
    
    class Meta:
        verbose_name = _('Thiết bị')
        verbose_name_plural = _('Thiết bị')
        ordering = ['-created_at']
        unique_together = ['user', 'device_code']  # Mỗi user không được trùng device_code
    
    @classmethod
    def get_available_codes(cls, user, exclude_device=None):
        """Lấy danh sách device_code còn trống cho user"""
        used_codes = cls.objects.filter(user=user)
        if exclude_device:
            used_codes = used_codes.exclude(id=exclude_device.id)
        used_codes = set(used_codes.values_list('device_code', flat=True))
        
        all_codes = [f'v{i}' for i in range(1, cls.MAX_DEVICE_CODE + 1)]
        return [code for code in all_codes if code not in used_codes]
    
    def __str__(self):
        return f"{self.name} ({self.get_device_type_display()})"
    
    @property
    def is_on(self):
        """Kiểm tra relay đang bật hay tắt"""
        return self.value == '1' or self.value.lower() == 'on'
    
    @property
    def display_value(self):
        """Hiển thị giá trị đẹp hơn"""
        if self.device_type == self.TYPE_RELAY:
            return 'BẬT' if self.is_on else 'TẮT'
        else:
            if self.unit:
                return f"{self.value} {self.unit}"
            return self.value


class SensorLog(models.Model):
    """
    Model lưu trữ lịch sử giá trị cảm biến để vẽ đồ thị
    - Mỗi bản ghi là 1 data point tại 1 thời điểm
    - Dùng để vẽ chart theo thời gian
    """
    
    device = models.ForeignKey(
        Device, 
        on_delete=models.CASCADE, 
        related_name='logs',
        verbose_name=_('Thiết bị')
    )
    
    # Giá trị số để dễ vẽ chart
    value = models.FloatField(_('Giá trị'), default=0)
    
    # Thời gian ghi nhận (cho phép set thủ công)
    timestamp = models.DateTimeField(_('Thời gian'), db_index=True)
    
    class Meta:
        verbose_name = _('Log cảm biến')
        verbose_name_plural = _('Logs cảm biến')
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['device', '-timestamp']),
        ]
    
    def __str__(self):
        return f"{self.device.name}: {self.value} @ {self.timestamp.strftime('%d/%m/%Y %H:%M:%S')}"
    
    @classmethod
    def log_value(cls, device, value=None):
        """
        Ghi log giá trị cảm biến
        - device: Device instance
        - value: giá trị (nếu None sẽ lấy từ device.value)
        """
        if device.device_type != Device.TYPE_SENSOR:
            return None
        
        try:
            val = float(value if value is not None else device.value)
        except (ValueError, TypeError):
            val = 0
        
        return cls.objects.create(device=device, value=val)
    
    @classmethod
    def get_chart_data(cls, device, hours=24, limit=100):
        """
        Lấy dữ liệu để vẽ chart
        - device: Device instance
        - hours: số giờ gần đây
        - limit: giới hạn số điểm data
        Returns: list of {'timestamp': ..., 'value': ...}
        """
        from django.utils import timezone
        from datetime import timedelta
        
        since = timezone.now() - timedelta(hours=hours)
        logs = cls.objects.filter(
            device=device,
            timestamp__gte=since
        ).order_by('timestamp')[:limit]
        
        return [
            {
                'timestamp': log.timestamp.strftime('%H:%M'),
                'value': log.value
            }
            for log in logs
        ]


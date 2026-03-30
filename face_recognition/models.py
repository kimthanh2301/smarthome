# -*- encoding: utf-8 -*-
"""
Face Recognition Models
"""

from django.db import models
from django.contrib.auth.models import User
import os


def user_face_upload_path(instance, filename):
    """Tạo đường dẫn lưu ảnh khuôn mặt"""
    return f'face_dataset/{instance.face_user.user_code}_{instance.face_user.name}/{filename}'


class FaceUser(models.Model):
    """Người dùng đăng ký nhận diện khuôn mặt"""
    user_code = models.CharField(max_length=50, unique=True, verbose_name="Mã người dùng")
    name = models.CharField(max_length=100, verbose_name="Họ tên")
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='face_users', verbose_name="Chủ sở hữu")
    is_active = models.BooleanField(default=True, verbose_name="Đang hoạt động")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Ngày tạo")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Ngày cập nhật")
    
    class Meta:
        verbose_name = "Người dùng Face ID"
        verbose_name_plural = "Người dùng Face ID"
        ordering = ['-created_at']
        unique_together = ['owner', 'user_code']
    
    def __str__(self):
        return f"{self.user_code} - {self.name}"
    
    @property
    def face_count(self):
        return self.face_images.count()


class FaceImage(models.Model):
    """Ảnh khuôn mặt của người dùng"""
    face_user = models.ForeignKey(FaceUser, on_delete=models.CASCADE, related_name='face_images', verbose_name="Người dùng")
    image_path = models.CharField(max_length=500, verbose_name="Đường dẫn ảnh")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Ngày tạo")
    
    class Meta:
        verbose_name = "Ảnh khuôn mặt"
        verbose_name_plural = "Ảnh khuôn mặt"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.face_user.name} - {os.path.basename(self.image_path)}"


class AttendanceLog(models.Model):
    """Lịch sử điểm danh / nhận diện"""
    EVENT_CHECKIN = 'checkin'
    EVENT_CHECKOUT = 'checkout'
    EVENT_CHECK = 'check'
    EVENT_CHOICES = [
        (EVENT_CHECKIN, 'Check-in'),
        (EVENT_CHECKOUT, 'Check-out'),
        (EVENT_CHECK, 'Check'),
    ]
    
    face_user = models.ForeignKey(FaceUser, on_delete=models.CASCADE, related_name='attendance_logs', verbose_name="Người dùng")
    event_type = models.CharField(max_length=20, choices=EVENT_CHOICES, default=EVENT_CHECK, verbose_name="Loại sự kiện")
    confidence = models.FloatField(default=0, verbose_name="Độ tin cậy")
    timestamp = models.DateTimeField(auto_now_add=True, verbose_name="Thời gian")
    
    class Meta:
        verbose_name = "Lịch sử điểm danh"
        verbose_name_plural = "Lịch sử điểm danh"
        ordering = ['-timestamp']
    
    def __str__(self):
        return f"{self.face_user.name} - {self.event_type} - {self.timestamp.strftime('%H:%M %d/%m/%Y')}"


class FaceRecognitionStatus(models.Model):
    """Trạng thái điểm danh gần nhất của người dùng"""
    face_user = models.OneToOneField(FaceUser, on_delete=models.CASCADE, related_name='recognition_status', verbose_name="Người dùng")
    last_event = models.CharField(max_length=20, choices=AttendanceLog.EVENT_CHOICES, null=True, blank=True, verbose_name="Sự kiện cuối")
    last_time = models.DateTimeField(null=True, blank=True, verbose_name="Thời gian cuối")
    
    class Meta:
        verbose_name = "Trạng thái nhận diện"
        verbose_name_plural = "Trạng thái nhận diện"
    
    def __str__(self):
        return f"{self.face_user.name} - {self.last_event}"

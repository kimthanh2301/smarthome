from django.contrib import admin
from .models import FaceUser, FaceImage, AttendanceLog, FaceRecognitionStatus


@admin.register(FaceUser)
class FaceUserAdmin(admin.ModelAdmin):
    list_display = ['user_code', 'name', 'owner', 'face_count', 'is_active', 'created_at']
    list_filter = ['is_active', 'owner', 'created_at']
    search_fields = ['user_code', 'name']
    list_editable = ['is_active']


@admin.register(FaceImage)
class FaceImageAdmin(admin.ModelAdmin):
    list_display = ['face_user', 'image_path', 'created_at']
    list_filter = ['face_user', 'created_at']
    search_fields = ['face_user__name', 'face_user__user_code']


@admin.register(AttendanceLog)
class AttendanceLogAdmin(admin.ModelAdmin):
    list_display = ['face_user', 'event_type', 'confidence', 'timestamp']
    list_filter = ['event_type', 'timestamp', 'face_user']
    search_fields = ['face_user__name', 'face_user__user_code']
    date_hierarchy = 'timestamp'


@admin.register(FaceRecognitionStatus)
class FaceRecognitionStatusAdmin(admin.ModelAdmin):
    list_display = ['face_user', 'last_event', 'last_time']
    list_filter = ['last_event']

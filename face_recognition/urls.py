# -*- encoding: utf-8 -*-
from django.urls import path
from . import views

urlpatterns = [
    # Quản lý người dùng
    path('users/', views.face_users_list, name='face_users_list'),
    path('users/add/', views.add_face_user, name='add_face_user'),
    path('users/<int:user_id>/delete/', views.delete_face_user, name='delete_face_user'),
    path('users/<int:user_id>/upload/', views.upload_face_images, name='upload_face_images'),
    path('users/<int:user_id>/faces/', views.get_user_faces, name='get_user_faces'),
    path('faces/<int:image_id>/delete/', views.delete_face_image, name='delete_face_image'),
    
    # Test Camera (local webcam)
    path('camera/', views.test_camera, name='test_camera'),
    path('camera/feed/', views.video_feed, name='video_feed'),
    path('camera/recognize/', views.recognize_frame, name='recognize_frame'),
    path('camera/logs/', views.get_today_logs, name='get_today_logs'),
    path('reload/', views.reload_database, name='reload_face_db'),
    
    # ESP32 Camera Stream
    path('esp32/', views.esp32_camera_dashboard, name='esp32_camera_dashboard'),
    path('esp32/feed/', views.esp32_video_feed, name='esp32_video_feed'),
    path('esp32/feed/raw/', views.esp32_video_feed_raw, name='esp32_video_feed_raw'),
    path('esp32/status/', views.esp32_camera_status, name='esp32_camera_status'),
    path('esp32/reconnect/', views.esp32_camera_reconnect, name='esp32_camera_reconnect'),
    path('esp32/capture/', views.esp32_capture_frame, name='esp32_capture_frame'),
]

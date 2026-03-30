# -*- encoding: utf-8 -*-
"""
Copyright (c) 2019 - present AppSeed.us
"""

from django.urls import path, re_path
from app import views

urlpatterns = [

    # Trang chủ = Dashboard
    path('', views.smart_home_dashboard, name='home'),
    
    # Smart Home Dashboard
    path('smart-home/', views.smart_home_dashboard, name='smart_home'),
    path('smart-home/toggle/<int:device_id>/', views.toggle_relay, name='toggle_relay'),
    path('smart-home/add/', views.add_device, name='add_device'),
    path('smart-home/delete/<int:device_id>/', views.delete_device, name='delete_device'),
    path('smart-home/edit/<int:device_id>/', views.edit_device, name='edit_device'),
    path('smart-home/device/<int:device_id>/', views.get_device_info, name='get_device_info'),
    path('smart-home/chart-data/', views.get_chart_data, name='get_chart_data'),

    # Trang giới thiệu đồ án
    path('about/', views.about_page, name='about'),
    
    # Sơ đồ cấu trúc database
    path('database-schema/', views.database_schema_page, name='database_schema'),
    
    # Lưu đồ hoạt động phần cứng
    path('hardware-flow/', views.hardware_flow_page, name='hardware_flow'),
    
    # Lưu đồ thuật toán nhận diện khuôn mặt
    path('face-recognition-flow/', views.face_recognition_flow_page, name='face_recognition_flow'),
    
    # Hướng dẫn build hệ thống
    path('guide/web-build/', views.web_build_guide_page, name='web_build_guide'),
    path('guide/esp32-hardware/', views.esp32_hardware_guide_page, name='esp32_hardware_guide'),

    # Matches any html file
    re_path(r'^.*\.html', views.pages, name='pages'),

]

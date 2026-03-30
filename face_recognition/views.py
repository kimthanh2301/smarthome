# -*- encoding: utf-8 -*-
"""
Face Recognition Views
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, StreamingHttpResponse
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.utils import timezone
from datetime import datetime
import os
import base64

from .models import FaceUser, FaceImage, AttendanceLog


@login_required(login_url="/login/")
def face_users_list(request):
    """Trang quản lý người dùng Face ID"""
    face_users = FaceUser.objects.filter(owner=request.user).prefetch_related('face_images')
    today = timezone.now().date()
    
    # Thống kê
    total_users = face_users.count()
    today_logs = AttendanceLog.objects.filter(
        face_user__owner=request.user,
        timestamp__date=today
    ).count()
    
    # Logs gần đây
    recent_logs = AttendanceLog.objects.filter(
        face_user__owner=request.user
    ).select_related('face_user')[:10]
    
    context = {
        'segment': 'face_users',
        'face_users': face_users,
        'total_users': total_users,
        'today_logs': today_logs,
        'recent_logs': recent_logs,
    }
    return render(request, 'face_recognition/users_list.html', context)


@login_required(login_url="/login/")
@require_POST
def add_face_user(request):
    """Thêm người dùng mới"""
    import random
    import string
    
    name = request.POST.get('name', '').strip()
    
    if not name:
        messages.error(request, 'Vui lòng nhập họ tên!')
        return redirect('face_users_list')
    
    # Tự động tạo mã người dùng
    while True:
        user_code = 'U' + ''.join(random.choices(string.digits, k=4))
        if not FaceUser.objects.filter(user_code=user_code).exists():
            break
    
    FaceUser.objects.create(
        user_code=user_code,
        name=name,
        owner=request.user
    )
    
    messages.success(request, f'Đã thêm "{name}" (Mã: {user_code}) thành công!')
    return redirect('face_users_list')


@login_required(login_url="/login/")
@require_POST
def delete_face_user(request, user_id):
    """Xóa người dùng"""
    face_user = get_object_or_404(FaceUser, id=user_id, owner=request.user)
    name = face_user.name
    
    # Xóa thư mục ảnh
    try:
        from django.conf import settings
        import shutil
        user_folder = os.path.join(settings.MEDIA_ROOT, 'face_dataset', f"{face_user.user_code}_{face_user.name}")
        if os.path.exists(user_folder):
            shutil.rmtree(user_folder)
    except:
        pass
    
    face_user.delete()
    messages.success(request, f'Đã xóa "{name}"!')
    return redirect('face_users_list')


@login_required(login_url="/login/")
@require_POST
def upload_face_images(request, user_id):
    """Upload ảnh khuôn mặt (từ file hoặc camera)"""
    face_user = get_object_or_404(FaceUser, id=user_id, owner=request.user)
    
    image_data_list = []
    
    # Lấy ảnh từ file upload
    images = request.FILES.getlist('face_images')
    for img in images:
        image_data_list.append(img.read())
    
    # Lấy ảnh từ camera (base64)
    camera_images = request.POST.getlist('camera_images')
    for cam_img in camera_images:
        if cam_img and ',' in cam_img:
            img_data = cam_img.split(',')[1]
            image_data_list.append(base64.b64decode(img_data))
    
    if not image_data_list:
        return JsonResponse({'success': False, 'error': 'Không có ảnh nào'})
    
    try:
        from .face_utils import register_face_images
        
        result = register_face_images(face_user, image_data_list)
        
        if result['success']:
            return JsonResponse({
                'success': True,
                'message': f'Đã lưu {result["saved_count"]} ảnh',
                'saved_count': result['saved_count']
            })
        else:
            return JsonResponse({
                'success': False,
                'error': result.get('error', 'Không có ảnh hợp lệ (không phát hiện khuôn mặt)')
            })
    except ImportError as e:
        return JsonResponse({'success': False, 'error': 'InsightFace chưa được cài đặt'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required(login_url="/login/")
def get_user_faces(request, user_id):
    """API lấy danh sách ảnh của user"""
    face_user = get_object_or_404(FaceUser, id=user_id, owner=request.user)
    
    faces = []
    for face_img in face_user.face_images.all():
        faces.append({
            'id': face_img.id,
            'path': face_img.image_path,
            'filename': os.path.basename(face_img.image_path),
            'created_at': face_img.created_at.strftime('%d/%m/%Y %H:%M')
        })
    
    return JsonResponse({
        'success': True,
        'user': {
            'id': face_user.id,
            'user_code': face_user.user_code,
            'name': face_user.name,
        },
        'faces': faces
    })


@login_required(login_url="/login/")
@require_POST  
def delete_face_image(request, image_id):
    """Xóa một ảnh khuôn mặt"""
    face_image = get_object_or_404(FaceImage, id=image_id, face_user__owner=request.user)
    
    # Xóa file
    try:
        if os.path.exists(face_image.image_path):
            os.remove(face_image.image_path)
    except:
        pass
    
    face_image.delete()
    return JsonResponse({'success': True})


# ============ TEST CAMERA ============

@login_required(login_url="/login/")
def test_camera(request):
    """Trang test camera nhận diện"""
    face_users = FaceUser.objects.filter(owner=request.user, is_active=True)
    
    # Logs hôm nay
    today = timezone.now().date()
    today_logs = AttendanceLog.objects.filter(
        face_user__owner=request.user,
        timestamp__date=today
    ).select_related('face_user').order_by('-timestamp')[:20]
    
    context = {
        'segment': 'test_camera',
        'face_users': face_users,
        'today_logs': today_logs,
    }
    return render(request, 'face_recognition/test_camera.html', context)


@login_required(login_url="/login/")
def video_feed(request):
    """Stream video với nhận diện"""
    return StreamingHttpResponse(
        generate_video_frames(request.user),
        content_type='multipart/x-mixed-replace; boundary=frame'
    )


def generate_video_frames(user):
    """Generator stream video"""
    try:
        from .face_utils import CameraManager, process_frame, face_database, load_face_database_from_db
        import cv2
        
        # Load face database
        if not face_database:
            load_face_database_from_db()
        
        camera_manager = CameraManager.get_instance()
        cap = camera_manager.get_camera()
        
        while True:
            success, frame = cap.read()
            if not success:
                break
            
            # Xử lý nhận diện
            processed_frame, _ = process_frame(frame, face_database)
            
            # Encode JPEG
            _, buffer = cv2.imencode('.jpg', processed_frame)
            frame_bytes = buffer.tobytes()
            
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
    
    except Exception:
        yield b'--frame\r\nContent-Type: text/plain\r\n\r\nCamera Error\r\n'


@login_required(login_url="/login/")
@require_POST
def recognize_frame(request):
    """API nhận diện từ frame gửi lên (cho webcam JS)"""
    try:
        import json
        import cv2
        import numpy as np
        from .face_utils import process_frame, face_database, load_face_database_from_db
        
        # Load database nếu chưa có
        if not face_database:
            load_face_database_from_db()
        
        # Lấy image data từ request
        data = json.loads(request.body)
        image_data = data.get('image', '')
        
        if not image_data:
            return JsonResponse({'success': False, 'error': 'No image data'})
        
        # Decode base64 image
        if ',' in image_data:
            image_data = image_data.split(',')[1]
        
        img_bytes = base64.b64decode(image_data)
        nparr = np.frombuffer(img_bytes, np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if frame is None:
            return JsonResponse({'success': False, 'error': 'Invalid image'})
        
        # Xử lý nhận diện
        processed_frame, recognized_users = process_frame(frame, face_database)
        
        # Encode lại frame đã xử lý
        _, buffer = cv2.imencode('.jpg', processed_frame)
        processed_base64 = base64.b64encode(buffer).decode('utf-8')
        
        return JsonResponse({
            'success': True,
            'processed_image': f'data:image/jpeg;base64,{processed_base64}',
            'recognized': recognized_users
        })
    
    except ImportError:
        return JsonResponse({'success': False, 'error': 'InsightFace chưa cài đặt'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required(login_url="/login/")
def get_today_logs(request):
    """API lấy logs hôm nay"""
    today = timezone.now().date()
    logs = AttendanceLog.objects.filter(
        face_user__owner=request.user,
        timestamp__date=today
    ).select_related('face_user').order_by('-timestamp')[:30]
    
    logs_data = [{
        'name': log.face_user.name,
        'user_code': log.face_user.user_code,
        'event': log.get_event_type_display(),
        'confidence': round(log.confidence * 100, 1),
        'time': log.timestamp.strftime('%H:%M:%S'),
    } for log in logs]
    
    return JsonResponse({'success': True, 'logs': logs_data})


@login_required(login_url="/login/")
def reload_database(request):
    """Reload face database"""
    try:
        from .face_utils import load_face_database_from_db
        result = load_face_database_from_db()
        return JsonResponse({
            'success': True,
            'message': f'Đã reload {len(result)} người'
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


# ============ ESP32 CAMERA STREAM ============

@login_required(login_url="/login/")
def esp32_camera_dashboard(request):
    """Dashboard camera ESP32 với nhận diện khuôn mặt"""
    from .camera_stream import DEFAULT_ESP32_CAMERA_URL
    
    face_users = FaceUser.objects.filter(owner=request.user, is_active=True)
    
    # Logs hôm nay
    today = timezone.now().date()
    today_logs = AttendanceLog.objects.filter(
        face_user__owner=request.user,
        timestamp__date=today
    ).select_related('face_user').order_by('-timestamp')[:20]
    
    # Lấy URL camera từ settings hoặc request
    camera_url = request.GET.get('camera_url', DEFAULT_ESP32_CAMERA_URL)
    
    context = {
        'segment': 'esp32_camera',
        'face_users': face_users,
        'today_logs': today_logs,
        'camera_url': camera_url,
        'default_camera_url': DEFAULT_ESP32_CAMERA_URL,
    }
    return render(request, 'face_recognition/esp32_camera_dashboard.html', context)


@login_required(login_url="/login/")
def esp32_video_feed(request):
    """Stream video từ ESP32 với nhận diện khuôn mặt"""
    from .camera_stream import generate_mjpeg_stream, DEFAULT_ESP32_CAMERA_URL
    
    camera_url = request.GET.get('camera_url', DEFAULT_ESP32_CAMERA_URL)
    with_recognition = request.GET.get('recognition', 'true').lower() == 'true'
    
    return StreamingHttpResponse(
        generate_mjpeg_stream(camera_url, with_recognition=with_recognition, user=request.user),
        content_type='multipart/x-mixed-replace; boundary=frame'
    )


@login_required(login_url="/login/")
def esp32_video_feed_raw(request):
    """Stream video từ ESP32 không xử lý (raw)"""
    from .camera_stream import generate_mjpeg_stream, DEFAULT_ESP32_CAMERA_URL
    
    camera_url = request.GET.get('camera_url', DEFAULT_ESP32_CAMERA_URL)
    
    return StreamingHttpResponse(
        generate_mjpeg_stream(camera_url, with_recognition=False),
        content_type='multipart/x-mixed-replace; boundary=frame'
    )


@login_required(login_url="/login/")
def esp32_camera_status(request):
    """API lấy trạng thái camera ESP32"""
    from .camera_stream import ESP32CameraStream, DEFAULT_ESP32_CAMERA_URL
    
    camera_url = request.GET.get('camera_url', DEFAULT_ESP32_CAMERA_URL)
    
    try:
        camera = ESP32CameraStream.get_instance(camera_url)
        status = camera.get_status()
        return JsonResponse({
            'success': True,
            'status': status
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


@login_required(login_url="/login/")
@require_POST
def esp32_camera_reconnect(request):
    """API reconnect camera ESP32"""
    from .camera_stream import ESP32CameraStream, DEFAULT_ESP32_CAMERA_URL
    import json
    
    try:
        data = json.loads(request.body) if request.body else {}
        camera_url = data.get('camera_url', DEFAULT_ESP32_CAMERA_URL)
        
        # Remove và tạo lại instance
        ESP32CameraStream.remove_instance(camera_url)
        camera = ESP32CameraStream.get_instance(camera_url)
        
        if camera.start():
            return JsonResponse({
                'success': True,
                'message': 'Camera reconnected successfully'
            })
        else:
            return JsonResponse({
                'success': False,
                'error': camera.error_message or 'Connection failed'
            })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


@login_required(login_url="/login/")
@require_POST
def esp32_capture_frame(request):
    """Capture một frame từ ESP32 camera"""
    from .camera_stream import get_single_frame, DEFAULT_ESP32_CAMERA_URL
    import json
    
    try:
        data = json.loads(request.body) if request.body else {}
        camera_url = data.get('camera_url', DEFAULT_ESP32_CAMERA_URL)
        with_recognition = data.get('recognition', True)
        
        frame, result = get_single_frame(camera_url, with_recognition=with_recognition)
        
        if frame is None:
            return JsonResponse({
                'success': False,
                'error': result or 'Failed to capture frame'
            })
        
        # Encode frame to base64
        import cv2
        _, buffer = cv2.imencode('.jpg', frame)
        frame_base64 = base64.b64encode(buffer).decode('utf-8')
        
        return JsonResponse({
            'success': True,
            'image': f'data:image/jpeg;base64,{frame_base64}',
            'recognized': result if isinstance(result, list) else []
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        })

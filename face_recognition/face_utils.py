# -*- encoding: utf-8 -*-
"""
Face Recognition Utilities
"""

import cv2
import numpy as np
import os
from datetime import datetime, timedelta
from django.conf import settings

# Cấu hình
FACE_RECOGNITION_THRESHOLD = 0.5
ATTENDANCE_INTERVAL_SECONDS = 15  # 15 giây giữa các lần mở cửa
FACE_DATASET_DIR = os.path.join(settings.MEDIA_ROOT, 'face_dataset')
os.makedirs(FACE_DATASET_DIR, exist_ok=True)

# Provider list cho InsightFace
PROVIDER_LIST = [
    'CUDAExecutionProvider',
    'DmlExecutionProvider', 
    'CPUExecutionProvider'
]

# Global variables
face_analyzer = None
face_database = {}
last_attendance_time = {}


def initialize_face_analyzer():
    """Khởi tạo FaceAnalysis với fallback"""
    global face_analyzer
    
    if face_analyzer is not None:
        return face_analyzer
    
    try:
        from insightface.app import FaceAnalysis
        
        for provider in PROVIDER_LIST:
            try:
                face_analyzer = FaceAnalysis(name='buffalo_l', providers=[provider])
                face_analyzer.prepare(ctx_id=0, det_size=(640, 640))
                return face_analyzer
            except Exception:
                pass
        
        raise RuntimeError("Không thể khởi tạo FaceAnalysis với bất kỳ provider nào")
    except ImportError:
        return None


def load_face_database_from_db():
    """Load face database từ Django models"""
    global face_database
    
    from .models import FaceUser, FaceImage
    
    analyzer = initialize_face_analyzer()
    if analyzer is None:
        return {}
    
    face_db = {}
    user_info = {}
    
    face_users = FaceUser.objects.filter(is_active=True).prefetch_related('face_images')
    
    for face_user in face_users:
        for face_image in face_user.face_images.all():
            image_path = face_image.image_path
            
            if os.path.exists(image_path):
                img = cv2.imread(image_path)
                if img is not None:
                    faces = analyzer.get(img)
                    if faces:
                        embedding = faces[0].normed_embedding
                        user_key = f"{face_user.user_code}_{face_user.name}"
                        
                        if user_key not in face_db:
                            face_db[user_key] = []
                            user_info[user_key] = {
                                "name": face_user.name,
                                "user_code": face_user.user_code,
                                "face_user_id": face_user.id
                            }
                        
                        face_db[user_key].append(embedding)
    
    # Tính trung bình embedding cho mỗi người
    averaged_db = {}
    for user_key, embeddings in face_db.items():
        if embeddings:
            averaged_embedding = np.mean(embeddings, axis=0)
            averaged_db[user_key] = {
                "embedding": averaged_embedding,
                "info": user_info[user_key]
            }
    
    face_database = averaged_db
    return face_database


def detect_faces(image):
    """Phát hiện khuôn mặt trong ảnh"""
    analyzer = initialize_face_analyzer()
    if analyzer is None:
        return []
    return analyzer.get(image)


def recognize_face(face_embedding, face_db=None):
    """Nhận diện khuôn mặt dựa trên embedding"""
    from sklearn.metrics.pairwise import cosine_similarity
    
    if face_db is None:
        face_db = face_database
    
    match_info = None
    max_similarity = -1
    
    for user_key, data in face_db.items():
        db_embedding = data["embedding"]
        similarity = cosine_similarity([face_embedding], [db_embedding])[0][0]
        
        if similarity > max_similarity:
            max_similarity = similarity
            if similarity > FACE_RECOGNITION_THRESHOLD:
                match_info = data["info"]
            else:
                match_info = None
    
    return match_info, max_similarity


def can_record_attendance(user_code):
    """Kiểm tra có thể ghi nhận điểm danh không (tránh spam)"""
    global last_attendance_time
    
    current_time = datetime.now()
    
    if user_code in last_attendance_time:
        last_time = last_attendance_time[user_code]
        time_diff = current_time - last_time
        
        if time_diff < timedelta(seconds=ATTENDANCE_INTERVAL_SECONDS):
            return False
    
    last_attendance_time[user_code] = current_time
    return True


def log_attendance(face_user, event_type, confidence):
    """Ghi nhận điểm danh vào database"""
    from .models import AttendanceLog, FaceRecognitionStatus
    from django.utils import timezone
    import logging
    
    logger = logging.getLogger(__name__)
    
    # Tạo log điểm danh
    AttendanceLog.objects.create(
        face_user=face_user,
        event_type=event_type,
        confidence=confidence
    )
    
    # Cập nhật trạng thái
    status, created = FaceRecognitionStatus.objects.get_or_create(face_user=face_user)
    status.last_event = event_type
    status.last_time = timezone.now()
    status.save()
    
    # Mở cửa khi nhận diện thành công
    if event_type == 'check':
        try:
            logger.info(f"[FACE] Nhận diện thành công: {face_user.name} - Đang mở cửa...")
            send_door_open_command(face_user)
            logger.info(f"[FACE] Đã gửi lệnh mở cửa cho {face_user.name}")
        except Exception as e:
            logger.error(f"[FACE] Lỗi mở cửa: {e}")


def send_door_open_command(face_user):
    """Gửi lệnh mở cửa qua MQTT khi nhận diện thành công"""
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        from mqtt.mqtt_client import get_mqtt_client
        from customers.models import Profile
        
        profile = Profile.objects.filter(user=face_user.owner).first()
        if not profile or not profile.api_key:
            logger.warning(f"[FACE] Không tìm thấy API key cho user: {face_user.owner}")
            return False
        
        mqtt_client = get_mqtt_client()
        
        if not mqtt_client.connected:
            logger.info("[FACE] MQTT chưa kết nối, đang kết nối...")
            mqtt_client.connect()
            mqtt_client.start_loop()
            import time
            for _ in range(10):
                if mqtt_client.connected:
                    break
                time.sleep(0.1)
        
        if not mqtt_client.connected:
            logger.error("[FACE] Không thể kết nối MQTT")
            return False
        
        # Gửi lệnh mở cửa - sử dụng relay v2 (hoặc device code tương ứng)
        # Gửi lệnh "on" để mở cửa
        CODE_DOOR = "v2"
        result = mqtt_client.control_device(profile.api_key, CODE_DOOR, "on")
        logger.info(f"[FACE] Đã gửi lệnh mở cửa: {CODE_DOOR} = on cho API key: {profile.api_key[:8]}... Result: {result}")
        
        # Tự động đóng cửa sau 3 giây
        import threading
        def auto_close_door():
            import time
            time.sleep(3)
            try:
                mqtt_client.control_device(profile.api_key, CODE_DOOR, "off")
                logger.info(f"[FACE] Đã gửi lệnh đóng cửa tự động: {CODE_DOOR} = off")
            except Exception as e:
                logger.error(f"[FACE] Lỗi đóng cửa tự động: {e}")
        
        threading.Thread(target=auto_close_door, daemon=True).start()
        
        return result
        
    except Exception as e:
        logger.error(f"[FACE] Lỗi gửi lệnh MQTT: {e}")
        return False


def process_frame(frame, face_db=None):
    """Xử lý frame để nhận diện khuôn mặt"""
    from .models import FaceUser
    
    if face_db is None:
        face_db = face_database
    
    display_frame = frame.copy()
    recognized_users = []
    
    analyzer = initialize_face_analyzer()
    if analyzer is None:
        return display_frame, recognized_users
    
    try:
        faces = analyzer.get(frame)
        
        for face in faces:
            face_embedding = face.normed_embedding
            match_info, max_similarity = recognize_face(face_embedding, face_db)
            
            # Lấy tọa độ khuôn mặt
            bbox = face.bbox.astype(int)
            left, top, right, bottom = bbox[0], bbox[1], bbox[2], bbox[3]
            
            if match_info:
                color = (0, 255, 0)
                name = match_info["name"]
                user_code = match_info["user_code"]
                face_user_id = match_info["face_user_id"]
                
                label = f"{name} ({max_similarity:.2f})"
                
                if can_record_attendance(user_code):
                    try:
                        face_user = FaceUser.objects.get(id=face_user_id)
                        log_attendance(face_user, 'check', max_similarity)
                        recognized_users.append({
                            "user_code": user_code,
                            "name": name,
                            "event": "check",
                            "confidence": float(max_similarity)
                        })
                    except FaceUser.DoesNotExist:
                        pass
            else:
                color = (0, 0, 255)
                label = f"Unknown ({max_similarity:.2f})"
            
            # Vẽ khung và label
            cv2.rectangle(display_frame, (left, top), (right, bottom), color, 2)
            cv2.putText(display_frame, label, (left, top - 10),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
    
    except Exception:
        pass
    
    return display_frame, recognized_users


def register_face_images(face_user, images):
    """Đăng ký ảnh khuôn mặt cho user"""
    from .models import FaceImage
    
    analyzer = initialize_face_analyzer()
    if analyzer is None:
        return {"success": False, "error": "Face analyzer chưa được khởi tạo"}
    
    # Tạo thư mục cho user
    user_folder = os.path.join(FACE_DATASET_DIR, f"{face_user.user_code}_{face_user.name}")
    os.makedirs(user_folder, exist_ok=True)
    
    saved_images = []
    sequence_number = face_user.face_images.count() + 1
    
    for image_data in images:
        try:
            # Decode ảnh
            if isinstance(image_data, bytes):
                nparr = np.frombuffer(image_data, np.uint8)
                img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            else:
                img = image_data
            
            if img is None:
                continue
            
            # Phát hiện khuôn mặt
            faces = analyzer.get(img)
            
            if not faces:
                continue
            
            if len(faces) > 1:
                continue  # Bỏ qua ảnh có nhiều khuôn mặt
            
            # Tạo tên file
            image_filename = f"{face_user.name}_{sequence_number:04d}.jpg"
            sequence_number += 1
            
            image_path = os.path.join(user_folder, image_filename)
            success = cv2.imwrite(image_path, img)
            
            if not success:
                continue
            
            # Lưu vào database
            FaceImage.objects.create(
                face_user=face_user,
                image_path=image_path
            )
            saved_images.append(image_path)
        
        except Exception:
            continue
    
    # Reload face database
    if saved_images:
        load_face_database_from_db()
    
    return {
        "success": len(saved_images) > 0,
        "saved_count": len(saved_images),
        "saved_images": saved_images
    }


# Camera Manager (Singleton)
class CameraManager:
    _instance = None
    _camera = None
    
    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    def __init__(self):
        if CameraManager._instance is not None:
            raise Exception("Singleton class - sử dụng get_instance()")
        self._camera = None
    
    def get_camera(self, camera_id=0):
        if self._camera is None:
            self._camera = cv2.VideoCapture(camera_id)
        return self._camera
    
    def release_camera(self):
        if self._camera is not None:
            self._camera.release()
            self._camera = None

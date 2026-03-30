# -*- encoding: utf-8 -*-
"""
ESP32 Camera Stream Handler
Xử lý MJPEG stream từ ESP32-CAM và nhận diện khuôn mặt
"""

import cv2
import numpy as np
import threading
import time
import queue
from urllib.request import urlopen
from urllib.error import URLError
import logging

logger = logging.getLogger(__name__)


class ESP32CameraStream:
    """
    Class xử lý MJPEG stream từ ESP32-CAM
    """
    _instances = {}
    _lock = threading.Lock()
    
    def __init__(self, stream_url, buffer_size=10):
        self.stream_url = stream_url
        self.buffer_size = buffer_size
        self.frame_queue = queue.Queue(maxsize=buffer_size)
        self.running = False
        self.thread = None
        self.last_frame = None
        self.last_frame_time = 0
        self.fps = 0
        self.connected = False
        self.error_message = None
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 5
        
    @classmethod
    def get_instance(cls, stream_url):
        """Singleton pattern cho mỗi camera URL"""
        with cls._lock:
            if stream_url not in cls._instances:
                cls._instances[stream_url] = cls(stream_url)
            return cls._instances[stream_url]
    
    @classmethod
    def remove_instance(cls, stream_url):
        """Xóa instance khi không cần thiết"""
        with cls._lock:
            if stream_url in cls._instances:
                cls._instances[stream_url].stop()
                del cls._instances[stream_url]
    
    def start(self):
        """Bắt đầu đọc stream"""
        if self.running:
            return True
        
        self.running = True
        self.thread = threading.Thread(target=self._read_stream, daemon=True)
        self.thread.start()
        
        # Đợi kết nối
        timeout = 5
        start_time = time.time()
        while not self.connected and time.time() - start_time < timeout:
            if self.error_message:
                return False
            time.sleep(0.1)
        
        return self.connected
    
    def stop(self):
        """Dừng stream"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=2)
        self.connected = False
    
    def _read_stream(self):
        """Thread đọc MJPEG stream"""
        bytes_buffer = b''
        stream = None
        frame_count = 0
        fps_start_time = time.time()
        
        while self.running:
            try:
                if stream is None:
                    logger.info(f"Connecting to camera: {self.stream_url}")
                    stream = urlopen(self.stream_url, timeout=10)
                    self.connected = True
                    self.error_message = None
                    self.reconnect_attempts = 0
                    logger.info("Camera connected successfully")
                
                # Đọc chunk từ stream
                chunk = stream.read(4096)
                if not chunk:
                    raise ConnectionError("Stream ended")
                
                bytes_buffer += chunk
                
                # Tìm JPEG frame
                while True:
                    # Tìm markers JPEG
                    start = bytes_buffer.find(b'\xff\xd8')  # SOI
                    end = bytes_buffer.find(b'\xff\xd9')    # EOI
                    
                    if start != -1 and end != -1 and end > start:
                        # Extract frame
                        jpg_bytes = bytes_buffer[start:end+2]
                        bytes_buffer = bytes_buffer[end+2:]
                        
                        # Decode JPEG
                        nparr = np.frombuffer(jpg_bytes, dtype=np.uint8)
                        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                        
                        if frame is not None:
                            self.last_frame = frame
                            self.last_frame_time = time.time()
                            
                            # Thêm vào queue (drop old frames nếu đầy)
                            try:
                                self.frame_queue.put_nowait(frame)
                            except queue.Full:
                                try:
                                    self.frame_queue.get_nowait()
                                    self.frame_queue.put_nowait(frame)
                                except:
                                    pass
                            
                            # Tính FPS
                            frame_count += 1
                            elapsed = time.time() - fps_start_time
                            if elapsed >= 1.0:
                                self.fps = frame_count / elapsed
                                frame_count = 0
                                fps_start_time = time.time()
                    else:
                        break
                        
            except (URLError, ConnectionError, TimeoutError) as e:
                self.connected = False
                self.error_message = str(e)
                logger.error(f"Camera connection error: {e}")
                
                if stream:
                    try:
                        stream.close()
                    except:
                        pass
                    stream = None
                
                self.reconnect_attempts += 1
                if self.reconnect_attempts > self.max_reconnect_attempts:
                    logger.error("Max reconnect attempts reached")
                    self.running = False
                    break
                
                # Đợi trước khi reconnect
                time.sleep(2)
                bytes_buffer = b''
                
            except Exception as e:
                logger.error(f"Stream error: {e}")
                time.sleep(0.1)
        
        if stream:
            try:
                stream.close()
            except:
                pass
        
        self.connected = False
    
    def get_frame(self):
        """Lấy frame mới nhất"""
        try:
            return self.frame_queue.get_nowait()
        except queue.Empty:
            return self.last_frame
    
    def get_status(self):
        """Lấy trạng thái camera"""
        return {
            'connected': self.connected,
            'fps': round(self.fps, 1),
            'error': self.error_message,
            'url': self.stream_url
        }


class FaceRecognitionStream:
    """
    Class xử lý nhận diện khuôn mặt trên camera stream
    """
    
    def __init__(self, camera_stream, face_database=None):
        self.camera = camera_stream
        self.face_database = face_database or {}
        self.running = False
        self.thread = None
        self.last_processed_frame = None
        self.recognized_users = []
        self.processing_fps = 0
        self.skip_frames = 2  # Xử lý 1 trong N frames để giảm tải CPU
        
    def start(self):
        """Bắt đầu xử lý nhận diện"""
        if self.running:
            return
        
        self.running = True
        self.thread = threading.Thread(target=self._process_loop, daemon=True)
        self.thread.start()
    
    def stop(self):
        """Dừng xử lý"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=2)
    
    def update_database(self, face_database):
        """Cập nhật face database"""
        self.face_database = face_database
    
    def _process_loop(self):
        """Thread xử lý nhận diện"""
        from .face_utils import process_frame
        
        frame_count = 0
        process_count = 0
        fps_start_time = time.time()
        
        while self.running:
            frame = self.camera.get_frame()
            
            if frame is None:
                time.sleep(0.01)
                continue
            
            frame_count += 1
            
            # Skip frames để giảm tải
            if frame_count % (self.skip_frames + 1) != 0:
                continue
            
            try:
                # Xử lý nhận diện
                processed_frame, recognized = process_frame(frame, self.face_database)
                
                self.last_processed_frame = processed_frame
                self.recognized_users = recognized
                
                process_count += 1
                
            except Exception as e:
                logger.error(f"Processing error: {e}")
                self.last_processed_frame = frame
            
            # Tính processing FPS
            elapsed = time.time() - fps_start_time
            if elapsed >= 1.0:
                self.processing_fps = process_count / elapsed
                process_count = 0
                fps_start_time = time.time()
    
    def get_frame(self):
        """Lấy frame đã xử lý"""
        return self.last_processed_frame
    
    def get_raw_frame(self):
        """Lấy frame gốc từ camera"""
        return self.camera.get_frame()


def generate_mjpeg_stream(camera_url, with_recognition=True, user=None):
    """
    Generator tạo MJPEG stream với/không nhận diện
    """
    from .face_utils import face_database, load_face_database_from_db, process_frame
    
    # Load face database nếu chưa có
    if with_recognition and not face_database:
        load_face_database_from_db()
    
    # Khởi tạo camera stream
    camera = ESP32CameraStream.get_instance(camera_url)
    
    if not camera.running:
        if not camera.start():
            # Trả về error frame
            error_img = np.zeros((480, 640, 3), dtype=np.uint8)
            cv2.putText(error_img, "Camera Connection Failed", (100, 240),
                       cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
            cv2.putText(error_img, camera.error_message or "Unknown error", (50, 280),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
            _, buffer = cv2.imencode('.jpg', error_img)
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
            return
    
    frame_count = 0
    skip_recognize = 3  # Nhận diện 1 trong N frames
    last_processed = None
    
    try:
        while True:
            frame = camera.get_frame()
            
            if frame is None:
                time.sleep(0.01)
                continue
            
            output_frame = frame
            frame_count += 1
            
            if with_recognition:
                # Chỉ nhận diện định kỳ để tiết kiệm CPU
                if frame_count % skip_recognize == 0 or last_processed is None:
                    try:
                        output_frame, _ = process_frame(frame, face_database)
                        last_processed = output_frame
                    except Exception as e:
                        logger.error(f"Recognition error: {e}")
                        output_frame = frame
                else:
                    output_frame = last_processed if last_processed is not None else frame
            
            # Thêm thông tin FPS
            cv2.putText(output_frame, f"FPS: {camera.fps:.1f}", (10, 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            
            # Encode và yield
            _, buffer = cv2.imencode('.jpg', output_frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
            
            # Giới hạn frame rate output
            time.sleep(0.03)  # ~30 FPS max
            
    except GeneratorExit:
        logger.info("Stream generator closed")
    except Exception as e:
        logger.error(f"Stream error: {e}")


def get_single_frame(camera_url, with_recognition=True):
    """
    Lấy một frame đơn từ camera
    """
    from .face_utils import face_database, load_face_database_from_db, process_frame
    
    camera = ESP32CameraStream.get_instance(camera_url)
    
    if not camera.running:
        camera.start()
        time.sleep(1)  # Đợi kết nối
    
    frame = camera.get_frame()
    
    if frame is None:
        return None, "No frame available"
    
    if with_recognition:
        if not face_database:
            load_face_database_from_db()
        
        try:
            processed_frame, recognized = process_frame(frame, face_database)
            return processed_frame, recognized
        except Exception as e:
            return frame, str(e)
    
    return frame, []


# Cấu hình camera mặc định
DEFAULT_ESP32_CAMERA_URL = "http://192.168.137.108/mjpeg/1"

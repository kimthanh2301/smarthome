"""
Job Scheduler for Smart Home
Chạy các tác vụ định kỳ và kết nối MQTT
"""
import django
import os
import sys
import logging
import time
from datetime import datetime

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
django.setup()

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.executors.pool import ThreadPoolExecutor
from apscheduler.jobstores.memory import MemoryJobStore
from django.conf import settings

from .mqtt_client import get_mqtt_client, MQTT_BROKER, MQTT_PORT

logger = logging.getLogger(__name__)


def create_scheduler():
    """Tạo scheduler instance"""
    jobstores = {
        'default': MemoryJobStore()
    }
    executors = {
        'default': ThreadPoolExecutor(max_workers=5)
    }
    job_defaults = {
        'coalesce': True,
        'max_instances': 3,
        'misfire_grace_time': 60
    }
    scheduler = BlockingScheduler(
        jobstores=jobstores,
        executors=executors,
        job_defaults=job_defaults,
        timezone=settings.TIME_ZONE
    )
    return scheduler


def check_mqtt_connection():
    """Job: Kiểm tra kết nối MQTT"""
    client = get_mqtt_client()
    if not client.connected:
        logger.warning("⚠️ MQTT disconnected, attempting to reconnect...")
        if client.connect():
            client.start_loop()
            logger.info("✅ MQTT reconnected successfully")
    else:
        logger.debug("✅ MQTT connection OK")


def heartbeat_job():
    """Job: Heartbeat - chạy mỗi 15 giây"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    logger.info(f"💓 Heartbeat: {now}")
    
    # Gửi heartbeat qua MQTT
    client = get_mqtt_client()
    if client.connected:
        client.publish('smarthome/heartbeat', {
            'timestamp': now,
            'status': 'alive'
        })


def sync_device_status():
    """Job: Đồng bộ trạng thái thiết bị - chạy mỗi 30 giây"""
    try:
        from devices.models import Device
        
        client = get_mqtt_client()
        if not client.connected:
            return
        
        # Request status từ tất cả devices đang online
        devices = Device.objects.filter(is_online=True)
        for device in devices:
            client.publish('smarthome/device/request_status', {
                'device_code': device.device_code
            })
        
        logger.info(f"📡 Requested status for {devices.count()} devices")
    except Exception as e:
        logger.error(f"Error syncing device status: {e}")


def cleanup_old_logs():
    """Job: Dọn dẹp logs cũ - chạy mỗi ngày"""
    try:
        from devices.models import SensorLog
        from datetime import timedelta
        from django.utils import timezone
        
        # Xóa logs cũ hơn 30 ngày
        cutoff_date = timezone.now() - timedelta(days=30)
        deleted, _ = SensorLog.objects.filter(timestamp__lt=cutoff_date).delete()
        
        if deleted > 0:
            logger.info(f"🗑️ Cleaned up {deleted} old sensor logs")
    except Exception as e:
        logger.error(f"Error cleaning up logs: {e}")


def config_jobs(scheduler):
    """Cấu hình các jobs"""
    # Check MQTT connection mỗi 30 giây
    scheduler.add_job(
        check_mqtt_connection,
        'interval',
        seconds=30,
        id='check_mqtt',
        name='Check MQTT Connection'
    )
    
    # Heartbeat mỗi 15 giây
    scheduler.add_job(
        heartbeat_job,
        'interval',
        seconds=15,
        id='heartbeat',
        name='Heartbeat'
    )
    
    # Sync device status mỗi 30 giây
    scheduler.add_job(
        sync_device_status,
        'interval',
        seconds=30,
        id='sync_devices',
        name='Sync Device Status'
    )
    
    # Cleanup logs mỗi ngày lúc 3:00 AM
    scheduler.add_job(
        cleanup_old_logs,
        'cron',
        hour=3,
        minute=0,
        id='cleanup_logs',
        name='Cleanup Old Logs'
    )
    
    logger.info("📋 Jobs configured successfully")
    return scheduler


def start_scheduler():
    """Start scheduler với MQTT connection"""
    logger.info(f"Starting MQTT Scheduler - Broker: {MQTT_BROKER}:{MQTT_PORT}")
    
    client = get_mqtt_client()
    if client.connect():
        client.start_loop()
        logger.info("MQTT Connected")
    else:
        logger.warning("MQTT Connection failed, will retry...")
    
    while True:
        try:
            scheduler = create_scheduler()
            config_jobs(scheduler)
            logger.info("Scheduler started")
            scheduler.start()
        except KeyboardInterrupt:
            logger.info("Scheduler stopped by user")
            client.stop_loop()
            client.disconnect()
            break
        except Exception as e:
            logger.error(f"Scheduler error: {e}")
            time.sleep(10)


if __name__ == '__main__':
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    start_scheduler()

"""
WebSocket Consumer for Smart Home Dashboard
Realtime updates for devices and sensors
"""
import json
import logging
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from asgiref.sync import sync_to_async

logger = logging.getLogger(__name__)


class DashboardConsumer(AsyncWebsocketConsumer):
    """WebSocket consumer for dashboard realtime updates"""
    
    async def connect(self):
        """Handle WebSocket connection"""
        self.user = self.scope.get('user')
        
        if not self.user or not self.user.is_authenticated:
            await self.close()
            return
        
        # Join user-specific group
        self.group_name = f'dashboard_{self.user.id}'
        
        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )
        
        await self.accept()
        logger.info(f"WebSocket connected: {self.user.username}")
        await self.send_initial_data()
    
    async def disconnect(self, close_code):
        """Handle WebSocket disconnection"""
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(
                self.group_name,
                self.channel_name
            )
        logger.info(f"WebSocket disconnected: {close_code}")
    
    async def receive(self, text_data):
        """Handle incoming WebSocket messages"""
        try:
            data = json.loads(text_data)
            action = data.get('action')
            
            if action == 'control_device':
                await self.handle_control_device(data)
            elif action == 'get_devices':
                await self.send_initial_data()
                
        except json.JSONDecodeError:
            logger.error("Invalid JSON received")
    
    async def handle_control_device(self, data):
        """Handle device control from WebSocket"""
        device_code = data.get('device_code')
        value = data.get('value')
        
        if not device_code or value is None:
            return
        
        # Update device in database
        device = await self.update_device_status(device_code, value)
        
        if device:
            # Send MQTT command
            await self.send_mqtt_command(device_code, value)
            
            # Broadcast to group
            await self.channel_layer.group_send(
                self.group_name,
                {
                    'type': 'device_update',
                    'device_code': device_code,
                    'status': value,
                    'name': device['name'],
                }
            )
    
    @database_sync_to_async
    def update_device_status(self, device_code, value):
        """Update device status in database"""
        try:
            from devices.models import Device
            device = Device.objects.filter(
                device_code=device_code,
                user=self.user
            ).first()
            
            if device and device.device_type == Device.TYPE_RELAY:
                device.is_on = str(value).lower() in ('on', '1', 'true')
                device.save()
                return {'name': device.name, 'status': device.is_on, 'device_code': device.device_code}
        except Exception as e:
            logger.error(f"Error updating device: {e}")
        return None
    
    async def send_mqtt_command(self, device_code, value):
        """Send MQTT command to device"""
        try:
            from mqtt.mqtt_client import get_mqtt_client
            from customers.models import Profile
            
            profile = await database_sync_to_async(
                lambda: Profile.objects.filter(user=self.user).first()
            )()
            
            if profile and profile.api_key:
                client = get_mqtt_client()
                if client.connected:
                    client.control_device(profile.api_key, device_code, value)
        except Exception as e:
            logger.error(f"Error sending MQTT: {e}")
    
    @database_sync_to_async
    def get_devices_data(self):
        """Get all devices for user"""
        from devices.models import Device, SensorLog
        from django.utils import timezone
        
        devices = Device.objects.filter(
            user=self.user
        ).order_by('device_code')
        
        result = {
            'relays': [],
            'sensors': []
        }
        
        for device in devices:
            device_data = {
                'id': device.id,
                'device_code': device.device_code,
                'name': device.name,
                'status': device.is_on,
            }
            
            if device.device_type == Device.TYPE_RELAY:
                result['relays'].append(device_data)
            else:
                # Get latest sensor value
                latest_log = SensorLog.objects.filter(
                    device=device
                ).order_by('-timestamp').first()
                
                device_data['value'] = latest_log.value if latest_log else device.value
                device_data['unit'] = device.unit or ''
                device_data['last_update'] = latest_log.timestamp.strftime('%H:%M %d/%m/%Y') if latest_log else ''
                result['sensors'].append(device_data)
        
        return result
    
    async def send_initial_data(self):
        """Send initial device data to client"""
        from django.utils import timezone
        
        devices = await self.get_devices_data()
        
        await self.send(text_data=json.dumps({
            'type': 'initial_data',
            'devices': devices,
            'timestamp': timezone.now().strftime('%H:%M %d/%m/%Y'),
        }))
    
    # Event handlers for group messages
    async def device_update(self, event):
        """Handle device update event"""
        from django.utils import timezone
        
        await self.send(text_data=json.dumps({
            'type': 'device_update',
            'device_code': event['device_code'],
            'status': event['status'],
            'name': event.get('name', ''),
            'timestamp': timezone.now().strftime('%H:%M %d/%m/%Y'),
        }))
    
    async def sensor_update(self, event):
        """Handle sensor update event"""
        from django.utils import timezone
        
        await self.send(text_data=json.dumps({
            'type': 'sensor_update',
            'device_code': event['device_code'],
            'value': event['value'],
            'name': event.get('name', ''),
            'unit': event.get('unit', ''),
            'timestamp': timezone.now().strftime('%H:%M %d/%m/%Y'),
        }))


# Helper function to send updates from MQTT
def send_device_update_to_websocket(user_id, device_code, status, name=''):
    """Send device update to WebSocket from anywhere"""
    from channels.layers import get_channel_layer
    from asgiref.sync import async_to_sync
    
    try:
        channel_layer = get_channel_layer()
        group_name = f'dashboard_{user_id}'
        
        async_to_sync(channel_layer.group_send)(
            group_name,
            {
                'type': 'device_update',
                'device_code': device_code,
                'status': status,
                'name': name,
            }
        )
    except Exception:
        pass


def send_sensor_update_to_websocket(user_id, device_code, value, name='', unit=''):
    """Send sensor update to WebSocket from anywhere"""
    from channels.layers import get_channel_layer
    from asgiref.sync import async_to_sync
    
    try:
        channel_layer = get_channel_layer()
        group_name = f'dashboard_{user_id}'
        
        async_to_sync(channel_layer.group_send)(
            group_name,
            {
                'type': 'sensor_update',
                'device_code': device_code,
                'value': value,
                'name': name,
                'unit': unit,
            }
        )
    except Exception:
        pass

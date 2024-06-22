import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from .models import ChatMessage
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
import base64
from datetime import datetime

class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.room_name = self.scope['url_route']['kwargs']['room_name']
        self.room_group_name = f'chat_{self.room_name}'

        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        await self.accept()

    async def disconnect(self, close_code):
        # Leave room group
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        data = json.loads(text_data)
        message_type = data.get('type', 'chat_message')

        if message_type == 'load_messages':
            await self.send_previous_messages()
        elif message_type == 'chat_message':
            message = data['message']
            username = data['username']
            file = data.get('file')

            if file:
                file_url = await self.save_file(file['name'], file['content'])
                await self.save_message(username, message, file_url, file['name'], file['type'])
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        'type': 'chat_message',
                        'message': message,
                        'username': username,
                        'file_url': file_url,
                        'file_name': file['name'],
                        'file_type': file['type'],
                        'timestamp': datetime.now().isoformat(),
                    }
                )
            else:
                await self.save_message(username, message)
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        'type': 'chat_message',
                        'message': message,
                        'username': username,
                        'timestamp': datetime.now().isoformat(),
                    }
                )

    async def chat_message(self, event):
        # Send message to WebSocket
        await self.send(text_data=json.dumps(event))

    async def send_previous_messages(self):
        previous_messages = await self.get_previous_messages()
        await self.send(text_data=json.dumps({
            'type': 'previous_messages',
            'messages': previous_messages
        }))

    @database_sync_to_async
    def save_file(self, filename, content):
        decoded_file = base64.b64decode(content)
        file_path = default_storage.save(f'chat_files/{filename}', ContentFile(decoded_file))
        return default_storage.url(file_path)

    @database_sync_to_async
    def save_message(self, username, message, file_url=None, file_name=None, file_type=None):
        ChatMessage.objects.create(
            room_name=self.room_name,
            username=username,
            message=message,
            file_url=file_url,
            file_name=file_name,
            file_type=file_type
        )

    @database_sync_to_async
    def get_previous_messages(self):
        messages = ChatMessage.objects.filter(room_name=self.room_name).order_by('-timestamp')[:50]
        return [
            {
                'message': msg.message,
                'username': msg.username,
                'file_url': msg.file_url,
                'file_name': msg.file_name,
                'file_type': msg.file_type,
                'timestamp': msg.timestamp.isoformat(),
            }
            for msg in reversed(messages)
        ]

import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
import base64

class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.room_name = self.scope['url_route']['kwargs']['room_name']
        self.room_group_name = f'chat_{self.room_name}'

        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        data = json.loads(text_data)
        message = data['message']
        username = data['username']
        file = data.get('file')

        if file:
            file_url = await self.save_file(file['name'], file['content'])
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'chat_message',
                    'message': message,
                    'username': username,
                    'file_url': file_url,
                }
            )
        else:
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'chat_message',
                    'message': message,
                    'username': username,
                }
            )

    async def chat_message(self, event):
        message = event['message']
        username = event['username']
        file_url = event.get('file_url')

        await self.send(text_data=json.dumps({
            'message': message,
            'username': username,
            'file_url': file_url,
        }))

    @database_sync_to_async
    def save_file(self, filename, content):
        decoded_file = base64.b64decode(content)
        file_path = default_storage.save(f'chat_files/{filename}', ContentFile(decoded_file))
        return default_storage.url(file_path)
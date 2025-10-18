import os
import json
import requests
import jwt
from datetime import datetime
from appwrite.client import Client
from appwrite.permission import Permission
from appwrite.role import Role
from appwrite.services.databases import Databases
from appwrite.id import ID

APPWRITE_ENDPOINT = os.environ.get('APPWRITE_ENDPOINT')
APPWRITE_PROJECT_ID = os.environ.get('APPWRITE_PROJECT_ID')
DATABASE_ID = os.environ.get('DATABASE_ID')
SESSIONS_COLLECTION_ID = os.environ.get('SESSIONS_COLLECTION_ID')

VIDEOSDK_API_KEY = os.environ.get('VIDEOSDK_API_KEY')
VIDEOSDK_SECRET_KEY = os.environ.get('VIDEOSDK_SECRET_KEY')

VIDEOSDK_API_BASE = "https://api.videosdk.live/v2"


def generate_videosdk_token():
    EXPIRY_TIME = int(datetime.now().timestamp()) + 7200
    payload = {
        'apikey': VIDEOSDK_API_KEY,
        'permissions': ['allow_join', 'allow_start_recording', 'allow_end_recording'],
        'iat': int(datetime.now().timestamp()),
        'exp': EXPIRY_TIME
    }
    token = jwt.encode(payload, VIDEOSDK_SECRET_KEY, algorithm = 'HS256')
    return token


def create_videosdk_meeting():
    auth_token = generate_videosdk_token()

    headers = {'Authorization' : auth_token,'Content-Type' : 'application/json'}

    data = {
        "autoCloseConfig": "manual"
    }

    try:
        response = requests.post(f'{VIDEOSDK_API_BASE}/rooms', headers = headers, json = data)
        response.raise_for_status()
        data = response.json()
        return data.get('roomId')

    except requests.exceptions.RequestException as e:
        error_message = f"Error creating VideoSDK meeting. Status: {response.status_code if 'response' in locals() else 'N/A'}. Error: {e}"
        print(error_message)
        raise Exception("Failed to contact VideoSDK API or create meeting room.")


def main(context):
    try:
        client = Client()
        client.set_endpoint(APPWRITE_ENDPOINT)
        client.set_project(APPWRITE_PROJECT_ID)
        client.set_key(context.req.headers["x-appwrite-key"])

        databases = Databases(client)

        if not context.req.body_json:
            return context.res.json({'error': 'Missing request body.'}, 400)

        payload = context.req.body_json

        sender_id = payload.get('senderId')
        receiver_id = payload.get('receiverId')
        schedule_details = payload.get('scheduleDetails')
        conversation_id = payload.get('conversationId')

        if not all([sender_id, receiver_id, schedule_details, conversation_id]):
            return context.res.json({'error': 'Missing required fields.'}, 400)

        meeting_id = create_videosdk_meeting()

        if not meeting_id:
            raise Exception("VideoSDK meetingId was not returned.")

        session_document = {
            'meetingId': meeting_id,
            'conversationId': conversation_id,
            'participants': [sender_id, receiver_id],
            'scheduleDetails': json.dumps(schedule_details),
            'status': 'SCHEDULED'
        }

        databases.create_document(
            database_id = DATABASE_ID,
            collection_id = SESSIONS_COLLECTION_ID,
            document_id = ID.unique(),
            data = session_document,
            permissions = [
                Permission.read(Role.user(sender_id)),
                Permission.read(Role.user(receiver_id)),
                Permission.write(Role.user(sender_id)),
                Permission.write(Role.user(receiver_id)),
            ]
        )

        join_token = generate_videosdk_token()

        return context.res.json({
            'success': True,
            'meetingId': meeting_id,
            'joinToken': join_token
        }, 201)

    except Exception as e:
        context.log(f"Function Error: {e}")
        return context.res.json({'error': f'Server Error: Failed to process request. {str(e)}'}, 500)

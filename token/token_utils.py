import datetime
import os
from datetime import timezone
import jwt


def main(context):
    context.log("JWT Generator Function Started.")

    VIDEO_SDK_API_KEY = os.environ.get('VIDEO_SDK_API_KEY')
    VIDEO_SDK_SECRET_KEY = os.environ.get('VIDEO_SDK_SECRET_KEY')

    try:
        payload = {
            'apikey': VIDEO_SDK_API_KEY,
            'permissions': [
                'allow_join',  # Allow joining meetings
                'allow_mod',  # Allow moderator actions (mute/unmute/remove)
                'allow_create',  # Allow creating new meetings
                'allow_recording_read',  # Read access to recordings
                'allow_recording_edit',  # Edit/delete recordings
                'allow_streaming',  # Start/stop live streaming
                'allow_hls',  # Start/stop HLS
                'allow_transcription',  # Start/stop transcription
                'allow_room_read',  # Read existing rooms
                'allow_room_edit',  # Edit existing rooms
                'allow_playlist_read',  # Read playlist data
                'allow_playlist_edit',  # Edit playlists
                'allow_webhook',  # Manage webhooks
                'allow_custom_events'
            ],
            'iat': datetime.datetime.now(timezone.utc),
            'exp': datetime.datetime.now(timezone.utc) + datetime.timedelta(hours = 1)
        }

        token = jwt.encode(
            payload,
            VIDEO_SDK_SECRET_KEY,
            algorithm = 'HS256'
        )

        context.log("JWT successfully generated.")
        return context.res.json({'token': token}, 200)

    except Exception as e:
        context.log(f"Error generating JWT: {e}")
        return context.res.json({'error': 'Internal server error during token generation'}, 500)

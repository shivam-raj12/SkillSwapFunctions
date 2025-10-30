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
            'permissions': ['allow_recording_read', 'allow_recording_edit'],
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
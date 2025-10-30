import os
import json
from appwrite.client import Client
from appwrite.services.databases import Databases
from appwrite.query import Query
from appwrite.id import ID

APPWRITE_API_KEY = os.environ.get('APPWRITE_API_KEY')
DATABASE_ID = os.environ.get('APPWRITE_DATABASE_ID')
ACTIVITY_COLLECTION_ID = os.environ.get('ACTIVITY_COLLECTION_ID')
PROFILES_COLLECTION_ID = os.environ.get('PROFILES_COLLECTION_ID')

COLLECTION_MAP = {
    'profiles': {'name': 'Profile', 'user_field': 'userId'},
    'conversations': {'name': 'Conversation', 'user_field': 'ownerId'},
    'meetings': {'name': 'Meeting', 'user_field': 'participants'},  # Now uses the full list
}


def get_profile_name(databases, user_id):
    if not user_id or user_id == 'system' or not PROFILES_COLLECTION_ID:
        return None

    try:
        result = databases.list_documents(
            database_id = DATABASE_ID,
            collection_id = PROFILES_COLLECTION_ID,
            queries = [
                Query.equal('userId', user_id),
                Query.select(['name'])  # Only fetch the name field
            ]
        )
        if result['documents']:
            return result['documents'][0].get('name', f"User {user_id[:8]}")

    except Exception as e:
        print(f"Error fetching profile for {user_id}: {e}")

    return f"User {user_id[:8]}"  # Fallback name


def create_meeting_activities(databases, document_data, old_document_data, action):
    activities = []
    meeting_id = document_data.get('meetingId', 'a skill swap')
    participants = document_data.get('participants', [])
    new_status = document_data.get('status')
    old_status = old_document_data.get('status') if old_document_data else None

    participant_names = {user_id: get_profile_name(databases, user_id) for user_id in participants}

    for user_id in participants:
        other_participants = [p_id for p_id in participants if p_id != user_id]

        description = ""

        if action == 'created':
            other_names = ', '.join([participant_names.get(o_id, 'another user') for o_id in other_participants])
            description = f"You scheduled a new skill swap with {other_names} (ID: {meeting_id})."

        elif action == 'updated':
            if new_status == 'COMPLETED' and old_status != 'COMPLETED':
                description = f"Great! Your skill swap (ID: {meeting_id}) is now completed."
            else:
                description = f"Your skill swap details (ID: {meeting_id}) were updated."

        if description:
            description = (description[:97] + '...') if len(description) > 100 else description

            activities.append({
                'userId': user_id,
                'description': description,
                'collection': 'Meeting',
                'documentId': document_data.get('$id'),
                'action': action,
            })

    return activities


def create_single_activity(databases, collection_id, document_data, action):
    collection_info = COLLECTION_MAP.get(collection_id)
    collection_name = collection_info['name']

    user_id = document_data.get(collection_info['user_field'], 'system')
    if user_id == 'system':
        return None

    description = ""

    if collection_id == 'conversations' and action == 'created':
        other_user_id = document_data.get('otherUserId')
        other_user_name = get_profile_name(databases, other_user_id)
        description = f"You started a new skill swap conversation with {other_user_name}."

    elif collection_id == 'profiles':
        user_name = document_data.get('name', 'Your Profile')
        if action == 'created':
            description = f"Welcome! Your profile '{user_name}' was created."
        elif action == 'updated':
            description = f"Your profile '{user_name}' was successfully updated."

    if description:
        description = (description[:97] + '...') if len(description) > 100 else description
        return {
            'userId': user_id,
            'description': description,
            'collection': collection_name,
            'documentId': document_data.get('$id'),
            'action': action,
        }
    return None


def main(context):
    context.log("Activity Logger Function Started.")

    if not all([APPWRITE_API_KEY, DATABASE_ID, ACTIVITY_COLLECTION_ID, PROFILES_COLLECTION_ID]):
        context.log("Error: Missing one or more required environment variables.")
        return

    try:
        client = (Client()
                  .set_endpoint("https://cloud.appwrite.io/v1")
                  .set_project(os.environ["APPWRITE_FUNCTION_PROJECT_ID"])
                  .set_key(context.req.headers["x-appwrite-key"])
                  )
        databases = Databases(client)

        event_data = json.loads(context.req.body_json)
        document_data = event_data.get('payload', {})
        old_document_data = event_data.get('old', {})

        if not document_data or not document_data.get('$collectionId'):
            context.log("Error: Event payload is missing document data or collection ID.")
            return

        collection_id = document_data['$collectionId']
        event_name = context.req.headers.get('x-appwrite-event', '')
        action = 'update' if 'documents.update' in event_name else 'create'

        context.log(f"Processing event for Collection: {collection_id}, Action: {action}")

        activities_to_log = []

        if collection_id == 'meetings':
            activities_to_log = create_meeting_activities(databases, document_data, old_document_data, action)
        elif collection_id == 'conversations' and action == 'update':
            context.log("Ignoring conversation update event.")
            return
        else:
            activity = create_single_activity(databases, collection_id, document_data, action)
            if activity:
                activities_to_log.append(activity)

        if activities_to_log:
            context.log(f"Logging {len(activities_to_log)} total activities.")

            for activity_data in activities_to_log:
                databases.create_document(
                    database_id = DATABASE_ID,
                    collection_id = ACTIVITY_COLLECTION_ID,
                    document_id = ID.unique(),
                    data = activity_data
                )
            context.log("All activities successfully logged.")
        else:
            context.log("No activity generated for this event based on rules.")

    except Exception as e:
        context.log(f"An unexpected error occurred: {e}")
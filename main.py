import json
import os
from appwrite.client import Client
from appwrite.services.databases import Databases
from appwrite.query import Query
from appwrite.id import ID

DATABASE_ID = os.environ.get('APPWRITE_DATABASE_ID')
CONVERSATIONS_COLLECTION_ID = os.environ.get('CONVERSATIONS_COLLECTION_ID')


def update_summary(client, owner_id, other_user_id, last_message_text, last_message_timestamp, unread_count_change,
                   is_increment = False):
    databases = Databases(client)
    try:
        response = databases.list_documents(
            database_id = DATABASE_ID,
            collection_id = CONVERSATIONS_COLLECTION_ID,
            queries = [
                Query.equal('ownerId', owner_id),
                Query.equal('otherUserId', other_user_id),
                Query.limit(1)
            ]
        )

        if response['total'] > 0:
            doc = response['documents'][0]
            document_id = doc['$id']
            current_unread_count = doc['unreadCount']

            if is_increment:
                new_unread_count = current_unread_count + unread_count_change
            else:
                new_unread_count = unread_count_change

            databases.update_document(
                database_id = DATABASE_ID,
                collection_id = CONVERSATIONS_COLLECTION_ID,
                document_id = document_id,
                data = {
                    'lastMessageText': last_message_text,
                    'lastMessageTimestamp': last_message_timestamp,
                    'unreadCount': new_unread_count
                }
            )

        else:
            databases.create_document(
                database_id = DATABASE_ID,
                collection_id = CONVERSATIONS_COLLECTION_ID,
                document_id = ID.unique(),
                data = {
                    'ownerId': owner_id,
                    'otherUserId': other_user_id,
                    'lastMessageText': last_message_text,
                    'lastMessageTimestamp': last_message_timestamp,
                    'unreadCount': unread_count_change
                }
            )

    except Exception as e:
        print(f"Error updating summary for owner {owner_id}: {e}")
        raise e


def main(context):
    client = (Client()
              .set_endpoint("https://cloud.appwrite.io/v1")
              .set_project(os.environ["APPWRITE_FUNCTION_PROJECT_ID"])
              .set_key(context.req.headers["x-appwrite-key"])
              )

    try:
        if not context.req.body:
            return context.res.json({'ok': False, 'message': 'Request body is empty'}, 400)

        message_document = context.req.body if isinstance(context.req.body, dict) else json.loads(context.req.body)

        sender_id = message_document.get('senderId')
        text = message_document.get('text')
        message_timestamp = message_document.get('$createdAt')
        conversation_id = message_document.get('conversationId')

        if not all([sender_id, conversation_id, text]):
            context.log('Missing senderId, conversationId, or text.')
            return context.res.json({'ok': False, 'message': 'Invalid message payload'}, 400)

        user_ids = conversation_id.split('_')

        user_a, user_b = user_ids

        recipient_id = user_b if sender_id == user_a else user_a

        update_summary(
            client = client,
            owner_id = sender_id,
            other_user_id = recipient_id,
            last_message_text = text,
            last_message_timestamp = message_timestamp,
            unread_count_change = 0,
            is_increment = False
        )

        update_summary(
            client = client,
            owner_id = recipient_id,
            other_user_id = sender_id,
            last_message_text = text,
            last_message_timestamp = message_timestamp,
            unread_count_change = 1,
            is_increment = True
        )

        return context.res.json({'ok': True, 'message': 'Conversation summaries updated successfully.'})

    except Exception as e:
        context.log(f'Function execution failed: {e}')
        return context.res.json({'ok': False, 'error': str(e)}, 500)

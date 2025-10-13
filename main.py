import os
from appwrite.client import Client
from appwrite.id import ID
from appwrite.query import Query
from appwrite.services.databases import Databases

DATABASE_ID = os.environ['APPWRITE_DATABASE_ID']
CONVERSATIONS_COLLECTION_ID = os.environ['CONVERSATIONS_COLLECTION_ID']


def update_summary(client, owner_id, other_user_id, last_message_text, last_message_timestamp, is_increment):
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

        document_id = response['documents'][0]['$id'] if response['total'] > 0 else None

        if document_id:
            if is_increment:
                databases.update_document(
                    database_id = DATABASE_ID,
                    collection_id = CONVERSATIONS_COLLECTION_ID,
                    document_id = document_id,
                    data = {
                        'lastMessageText': last_message_text,
                        'lastMessageTimestamp': last_message_timestamp,
                    }
                )
                databases.increment_document_attribute(
                    database_id = DATABASE_ID,
                    collection_id = CONVERSATIONS_COLLECTION_ID,
                    document_id = document_id,
                    attribute = 'unreadCount',
                    value = 1
                )

            else:
                databases.update_document(
                    database_id = DATABASE_ID,
                    collection_id = CONVERSATIONS_COLLECTION_ID,
                    document_id = document_id,
                    data = {
                        'lastMessageText': last_message_text,
                        'lastMessageTimestamp': last_message_timestamp,
                        'unreadCount': 0
                    }
                )

        else:
            initial_unread_count = 1 if is_increment else 0

            databases.create_document(
                database_id = DATABASE_ID,
                collection_id = CONVERSATIONS_COLLECTION_ID,
                document_id = ID.unique(),
                data = {
                    'ownerId': owner_id,
                    'otherUserId': other_user_id,
                    'lastMessageText': last_message_text,
                    'lastMessageTimestamp': last_message_timestamp,
                    'unreadCount': initial_unread_count
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
        if not context.req.body_json:
            return context.res.json({'ok': False, 'message': 'Request body is empty'})

        message_document = context.req.body_json

        sender_id = message_document.get('senderId')
        text = message_document.get('text')
        message_timestamp = message_document.get('$createdAt')
        conversation_id = message_document.get('conversationId')

        if not all([sender_id, conversation_id, text]):
            context.log('Missing senderId, conversationId, or text.')
            return context.res.json({'ok': False, 'message': 'Invalid message payload'})

        user_ids = conversation_id.split('_')
        user_a, user_b = user_ids
        recipient_id = user_b if sender_id == user_a else user_a

        update_summary(
            client = client,
            owner_id = sender_id,
            other_user_id = recipient_id,
            last_message_text = text,
            last_message_timestamp = message_timestamp,
            is_increment = False
        )

        update_summary(
            client = client,
            owner_id = recipient_id,
            other_user_id = sender_id,
            last_message_text = text,
            last_message_timestamp = message_timestamp,
            is_increment = True
        )

        return context.res.json({'ok': True, 'message': 'Conversation summaries updated successfully.'})

    except Exception as e:
        context.log(f'Function execution failed: {e}')
        return context.res.json({'ok': False, 'error': str(e)})
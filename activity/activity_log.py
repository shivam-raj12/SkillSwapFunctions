import os
import re
from appwrite.client import Client
from appwrite.query import Query
from appwrite.services.databases import Databases

# Initialize Appwrite Client
DATABASE_ID = os.environ.get("APPWRITE_DATABASE_ID")
ACTIVITY_COLLECTION_ID = "activity"


def getNameWithId(databases: Databases, user_id: str):
    try:
        profiles = databases.list_documents(
            database_id=DATABASE_ID,
            collection_id="profiles",
            queries = [
                Query.equal("userId", user_id),
                Query.limit(1)
            ]
        )
        if profiles.get("total", 0) > 0:
            first_doc = profiles["documents"][0]
            return first_doc.get("name", "Unknown User")

            # No matching profile found
        return "Unknown User"
    except Exception as e:
        print(f"getNameWithId failed for {user_id}: {e}")
        return "Unknown User"


def write_activity(databases: Databases, user_id: str, description: str):
    try:
        databases.create_document(
            database_id=DATABASE_ID,
            collection_id=ACTIVITY_COLLECTION_ID,
            document_id="unique()",
            data={
                "userId": user_id,
                "description": description[:100]  # limit to 100 chars
            }
        )
        print(f"Activity logged for {user_id}: {description}")
    except Exception as e:
        print(f"Failed to write activity: {e}")


def main(context):
    client = (Client()
              .set_endpoint("https://fra.cloud.appwrite.io/v1")
              .set_project("skill-swap")
              .set_key(context.req.headers["x-appwrite-key"])
              )
    database = Databases(client)
    body = context.req.body_json
    headers = context.req.headers
    event = headers.get("x-appwrite-event", "")

    # --- Detect which collection triggered this ---
    match = re.search(r"collections\.(\w+)\.documents\.\w+\.(create|update)", event)
    if not match:
        return context.res.json({"status": "ignored", "reason": "not a tracked collection"})

    collection, action = match.groups()

    # --- Handle profiles ---
    if collection == "profiles":
        user_id = body.get("userId")
        if not user_id:
            return context.res.json({"status": "error", "reason": "missing userId"})

        if action == "create":
            desc = f"Welcome {getNameWithId(database, user_id)}! Your profile has been created."
        else:
            desc = f"Profile updated for {getNameWithId(database, user_id)}."

        write_activity(database, user_id, desc)

    # --- Handle meetings ---
    elif collection == "meetings":
        participants = body.get("participants", [])
        if not participants or len(participants) != 2:
            return context.res.json({"status": "error", "reason": "invalid participants"})

        # Identify both participants
        user_a, user_b = participants
        name_a = getNameWithId(database, user_a)
        name_b = getNameWithId(database, user_b)

        if action == "create":
            desc_a = f"You scheduled a meeting with {name_b}."
            desc_b = f"You scheduled a meeting with {name_a}."
            write_activity(database, user_a, desc_a)
            write_activity(database, user_b, desc_b)

        elif action == "update":
            status = body.get("status", "").upper()
            if status == "COMPLETED":
                desc_a = f"You completed a swap with {name_b}."
                desc_b = f"You completed a swap with {name_a}."
                write_activity(database, user_a, desc_a)
                write_activity(database, user_b, desc_b)
            else:
                desc_a = f"Meeting updated with {name_b}."
                desc_b = f"Meeting updated with {name_a}."
                write_activity(database, user_a, desc_a)
                write_activity(database, user_b, desc_b)

    # --- Handle conversations ---
    elif collection == "conversations" and action == "create":
        owner_id = body.get("ownerId")
        other_id = body.get("otherUserId")
        if not owner_id or not other_id:
            return context.res.json({"status": "error", "reason": "missing conversation ids"})

        other_name = getNameWithId(database, other_id)
        desc = f"{other_name} sent you a new message."
        write_activity(database, owner_id, desc)

    else:
        return context.res.json({"status": "ignored", "reason": "unsupported event"})

    # --- Return success ---
    return context.res.json({"status": "success", "event": event})

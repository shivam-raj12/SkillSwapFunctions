import os
import re
from appwrite.client import Client
from appwrite.query import Query
from appwrite.services.databases import Databases


# Initialize Appwrite Client
DATABASE_ID = os.environ.get("APPWRITE_DATABASE_ID")
ACTIVITY_COLLECTION_ID = "activity"


def getNameWithId(databases: Databases, user_id: str, context):
    try:
        context.log(f"Fetching profile for user_id={user_id}...")
        profiles = databases.list_documents(
            database_id=DATABASE_ID,
            collection_id="profiles",
            queries=[
                Query.equal("userId", user_id),
                Query.limit(1)
            ]
        )
        total = profiles.get("total", 0)
        context.log(f"Profile query returned {total} results for {user_id}.")

        if total > 0:
            first_doc = profiles["documents"][0]
            name = first_doc.get("name", "Unknown User")
            context.log(f"Found profile name for {user_id}: {name}")
            return name

        context.log(f"No profile found for {user_id}, returning 'Unknown User'.")
        return "Unknown User"

    except Exception as e:
        context.log(f"getNameWithId failed for {user_id}: {e}")
        return "Unknown User"


def write_activity(databases: Databases, user_id: str, description: str, context):
    try:
        context.log(f"Writing activity for {user_id}: {description}")
        databases.create_document(
            database_id=DATABASE_ID,
            collection_id=ACTIVITY_COLLECTION_ID,
            document_id="unique()",
            data={
                "userId": user_id,
                "description": description[:100]  # limit to 100 chars
            }
        )
        context.log(f"✅ Activity successfully logged for {user_id}: {description}")
    except Exception as e:
        context.log(f"❌ Failed to write activity for {user_id}: {e}")


def main(context):
    context.log("⚙️ Starting Activity Logger Function...")

    try:
        client = (
            Client()
            .set_endpoint("https://fra.cloud.appwrite.io/v1")
            .set_project("skill-swap")
            .set_key(context.req.headers["x-appwrite-key"])
        )
        context.log("✅ Appwrite Client initialized successfully.")
    except Exception as e:
        context.log(f"❌ Client initialization failed: {e}")
        return context.res.json({"status": "error", "reason": "client initialization failed"})

    database = Databases(client)
    body = context.req.body_json
    headers = context.req.headers
    event = headers.get("x-appwrite-event", "")

    context.log(f"Received event: {event}")
    context.log(f"Request body: {body}")

    # --- Detect which collection triggered this ---
    match = re.search(
        r"(?:.*\.)?(?:collections|tables)\.(\w+)\.(?:documents|rows)\.[\w-]+\.(create|update)",
        event
    )
    if not match:
        context.log("⚠️ Not a tracked collection. Exiting.")
        return context.res.json({"status": "ignored", "reason": "not a tracked collection"})

    collection, action = match.groups()
    context.log(f"Detected collection={collection}, action={action}")

    # --- Handle profiles ---
    if collection == "profiles":
        user_id = body.get("userId")
        if not user_id:
            context.log("❌ Missing userId in profile event body.")
            return context.res.json({"status": "error", "reason": "missing userId"})

        if action == "create":
            desc = f"Welcome {getNameWithId(database, user_id, context)}! Your profile has been created."
        else:
            desc = f"Profile updated for {getNameWithId(database, user_id, context)}."

        write_activity(database, user_id, desc, context)

    # --- Handle meetings ---
    elif collection == "meetings":
        participants = body.get("participants", [])
        context.log(f"Meeting event detected with participants={participants}")

        if not participants or len(participants) != 2:
            context.log("❌ Invalid participants data in meeting event.")
            return context.res.json({"status": "error", "reason": "invalid participants"})

        # Identify both participants
        user_a, user_b = participants
        name_a = getNameWithId(database, user_a, context)
        name_b = getNameWithId(database, user_b, context)

        context.log(f"Resolved participant names: {user_a} → {name_a}, {user_b} → {name_b}")

        if action == "create":
            desc_a = f"You scheduled a meeting with {name_b}."
            desc_b = f"You scheduled a meeting with {name_a}."
            write_activity(database, user_a, desc_a, context)
            write_activity(database, user_b, desc_b, context)

        elif action == "update":
            status = body.get("status", "").upper()
            context.log(f"Meeting update detected: status={status}")
            if status == "COMPLETED":
                desc_a = f"You completed a swap with {name_b}."
                desc_b = f"You completed a swap with {name_a}."
            else:
                desc_a = f"Meeting updated with {name_b}."
                desc_b = f"Meeting updated with {name_a}."
            write_activity(database, user_a, desc_a, context)
            write_activity(database, user_b, desc_b, context)

    # --- Handle conversations ---
    elif collection == "conversations" and action == "create":
        owner_id = body.get("ownerId")
        other_id = body.get("otherUserId")
        context.log(f"Conversation event detected: ownerId={owner_id}, otherUserId={other_id}")

        if not owner_id or not other_id:
            context.log("❌ Missing conversation participant IDs.")
            return context.res.json({"status": "error", "reason": "missing conversation ids"})

        other_name = getNameWithId(database, other_id, context)
        desc = f"{other_name} sent you a new message."
        write_activity(database, owner_id, desc, context)

    else:
        context.log(f"⚠️ Unsupported collection or action: {collection}.{action}")
        return context.res.json({"status": "ignored", "reason": "unsupported event"})

    context.log("✅ Activity processing complete.")
    return context.res.json({"status": "success", "event": event})

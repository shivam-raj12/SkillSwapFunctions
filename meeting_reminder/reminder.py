import os
import json
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from appwrite.client import Client
from appwrite.services.databases import Databases
from appwrite.services.messaging import Messaging
from appwrite.query import Query
from appwrite.id import ID

# Environment variables
URL_HOST = os.environ.get("URL_HOST")

def get_day_name(date_obj):
    return date_obj.strftime('%A')

def main(context):
    context.log("⚙️ Reminder Cron Function started.")

    # 1️⃣ Initialize Appwrite Client
    try:
        client = (
            Client()
            .set_endpoint("https://fra.cloud.appwrite.io/v1")
            .set_project("skill-swap")
            .set_key(context.req.headers["x-appwrite-key"])
        )
        context.log("✅ Appwrite Client initialized.")
    except Exception as e:
        context.log(f"❌ Client initialization failed: {e}")
        return context.res.json({"success": False, "error": "Client initialization failed."})

    databases = Databases(client)
    messaging = Messaging(client)

    # 2️⃣ Current UTC time
    now_utc = datetime.now(timezone.utc).replace(second=0, microsecond=0)  # Round to minute
    query_time_utc = (now_utc + timedelta(minutes=15)).strftime("%H:%M")  # Meetings 15 min ahead
    context.log(f"Current UTC time: {now_utc.strftime('%H:%M')}, Query UTC time: {query_time_utc}")

    try:
        # 3️⃣ Query meetings scheduled at query_time_utc
        response = databases.list_documents(
            database_id="68de2d7c003c475d5c24",
            collection_id="meetings",
            queries=[
                Query.equal("status", "SCHEDULED"),
                Query.contains("scheduleDetails", f'"utcTime": "{query_time_utc}"')
            ]
        )
        meetings = response.get("documents", [])
        if not meetings:
            context.log("No meetings found for this time.")
            return context.res.json({"success": True, "message": "No meetings to send."})

        sent_count = 0

        for meeting in meetings:
            try:
                details = json.loads(meeting.get("scheduleDetails", "{}"))
            except json.JSONDecodeError:
                context.log(f"Skipping meeting {meeting.get('$id')}: Invalid JSON in scheduleDetails.")
                continue

            utc_time_str = details.get("utcTime")
            user_timezone = details.get("timezone")
            meeting_id = meeting.get("meetingId")
            schedule_frequency = details.get("frequency", "").strip()
            start_date_str = details.get("startDate")
            time = datetime.strptime(utc_time_str, "%H:%M").replace(tzinfo=ZoneInfo("UTC")).astimezone(ZoneInfo(user_timezone))

            if not utc_time_str or not user_timezone or not start_date_str:
                context.log(f"Skipping meeting {meeting.get('$id')}: Missing required fields.")
                continue

            # Parse start date and UTC time
            try:
                start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
                meeting_time_utc = datetime.strptime(utc_time_str, "%H:%M").time()
                meeting_datetime_utc = datetime.combine(start_date, meeting_time_utc, tzinfo=ZoneInfo("UTC"))
            except Exception as e:
                context.log(f"Skipping meeting {meeting.get('$id')}: Invalid date/time format: {e}")
                continue

            # Convert to participant local time
            try:
                local_tz = ZoneInfo(user_timezone)
                meeting_local_time = meeting_datetime_utc.astimezone(local_tz)
                reminder_local_time = meeting_local_time - timedelta(minutes=15)
            except Exception as e:
                context.log(f"Skipping meeting {meeting.get('$id')}: Invalid timezone '{user_timezone}': {e}")
                continue

            # Current time in local timezone
            now_local = datetime.now(tz=local_tz)

            # 4️⃣ Check if reminder should be sent
            if abs((reminder_local_time - now_local).total_seconds()) <= 60:  # ±1 min window
                current_day_name = get_day_name(now_local)
                normalized_frequency = schedule_frequency.lower()
                should_send = False

                if normalized_frequency == "daily":
                    should_send = True
                elif normalized_frequency == "weekends only":
                    if current_day_name in ["Saturday", "Sunday"]:
                        should_send = True
                elif current_day_name.lower() == normalized_frequency.lower():
                    should_send = True

                if should_send:
                    participant_targets = meeting.get("participants", [])
                    if not participant_targets:
                        context.log(f"Skipping meeting {meeting.get('$id')}: No participants found.")
                        continue

                    url = f"{URL_HOST}/meetings/{meeting_id}"
                    time_display = meeting_local_time.strftime("%H:%M")

                    # 5️⃣ Send email
                    messaging.create_email(
                        message_id=ID.unique(),
                        subject="⏰ The Clock Is Ticking! Join Your SkillSwap Session in 15 Minutes!",
                        content=f"<!DOCTYPE html><html lang=\"en\"><head><meta charset=\"UTF-8\"><meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\"><title>SkillSwap Final Countdown</title></head><body style=\"margin: 0; padding: 0; background-color: #0d121c; font-family: 'Arial', sans-serif;\"><center style=\"width: 100%; background-color: #0d121c;\"><div style=\"max-width: 600px; margin: 30px auto; background-color: #10141f; border-radius: 12px; overflow: hidden; box-shadow: 0 0 40px rgba(64, 224, 208, 0.15); border: 2px solid #1a1e2b;\"><table role=\"presentation\" cellspacing=\"0\" cellpadding=\"0\" border=\"0\" width=\"100%\" style=\"padding: 25px 30px; background-color: #151927;\"><tr><td align=\"left\"><h2 style=\"font-size: 28px; font-weight: bold; margin: 0; color: #ffffff;\"><span style=\"color: #40e0d0;\">SkillSwap</span> Session</h2></td><td align=\"right\"><span style=\"font-size: 16px; font-weight: bold; color: #1ed760; border: 2px solid #1ed760; padding: 5px 10px; border-radius: 6px;\">READY</span></td></tr></table><table role=\"presentation\" cellspacing=\"0\" cellpadding=\"0\" border=\"0\" width=\"100%\" style=\"padding: 30px 30px 40px 30px; text-align: center;\"><tr><td style=\"background-color: #0d121c; padding: 25px; border-radius: 10px; border: 1px solid #1a1e2b;\"><p style=\"color: #ffffff; font-size: 18px; margin: 0 0 5px 0;\">Starting In...</p><h1 style=\"color: #1ed760; font-size: 55px; font-weight: 900; margin: 0; text-shadow: 0 0 10px rgba(30, 215, 96, 0.7);\">15 MINS</h1></td></tr><tr><td style=\"padding-top: 25px;\"><p style=\"color: #b0b4bf; font-size: 16px; line-height: 1.6;\">It's almost time to trade your skills! Don't miss this opportunity to connect and share what you know with people all over the world.</p></td></tr><tr><td style=\"padding: 15px 0;\"><p style=\"color: #40e0d0; font-size: 18px; font-weight: bold; margin: 0;\">Your Session Time: <span style=\"color: #ffffff;\">{time}</span></p></td></tr><tr><td style=\"padding: 25px 0 0 0;\"><a href=\"{url}\" target=\"_blank\" style=\"background-color: #40e0d0; color: #000000; text-decoration: none; padding: 18px 40px; border-radius: 4px; font-weight: bold; font-size: 18px; display: inline-block; box-shadow: 0 5px 20px rgba(64, 224, 208, 0.4);\">ENTER THE EXCHANGE</a></td></tr></table><table role=\"presentation\" cellspacing=\"0\" cellpadding=\"0\" border=\"0\" width=\"100%\" style=\"padding: 20px 30px; background-color: #0d121c; border-top: 1px solid #1a1e2b;\"><tr><td align=\"center\"><p style=\"color: #6a748c; font-size: 12px; margin: 0 0 5px 0;\">Trade your skills for knowledge you want. No money, just sharing.</p><p style=\"color: #b0b4bf; font-size: 14px; margin: 0;\">The SkillSwap Team</p></td></tr></table></div></center></body></html>",
                        users=participant_targets,
                        html=True
                    )

                    context.log(f"✅ Sent reminder for meeting {meeting_id} at {time_display} ({user_timezone})")
                    sent_count += 1

        context.log(f"All reminders processed. Total sent: {sent_count}")
        return context.res.json({"success": True, "processed_reminders": sent_count})

    except Exception as e:
        context.log(f"Unexpected error: {e}")
        return context.res.json({"success": False, "error": str(e)})

import os
import json
from datetime import datetime, timedelta
from appwrite.client import Client
from appwrite.services.databases import Databases
from appwrite.services.messaging import Messaging
from appwrite.query import Query
from appwrite.id import ID

DATABASE_ID = os.environ.get("MEETINGS_DATABASE_ID", "default_database_id")
COLLECTION_ID = os.environ.get("MEETINGS_COLLECTION_ID", "meetings")
URL_HOST = os.environ.get("URL_HOST")


def get_day_name(date_obj):
    return date_obj.strftime('%A')


def main(context):
    try:
        client = (Client()
                  .set_endpoint("https://cloud.appwrite.io/v1")
                  .set_project(os.environ["APPWRITE_FUNCTION_PROJECT_ID"])
                  .set_key(context.req.headers["x-appwrite-key"])
                  )
    except Exception as e:
        context.log(f"Client initialization failed: {e}")
        return context.res.json({'success': False, 'error': 'Client initialization failed.'})

    databases = Databases(client)
    messaging = Messaging(client)

    context.log("Scheduled Reminder Cron function started.")

    now_utc = datetime.utcnow()
    future_time_utc = now_utc + timedelta(minutes = 15)
    target_scheduled_time = future_time_utc.strftime('%H:%M')

    current_day_name = get_day_name(future_time_utc)

    context.log(
        f"Current UTC time: {now_utc.strftime('%H:%M')}. Target Time (15 min future): {target_scheduled_time} ({current_day_name})")

    search_fragment = f'"time": "{target_scheduled_time}"'
    context.log(f"Searching for meetings with fragment: {search_fragment}")

    try:
        response = databases.list_documents(
            database_id = DATABASE_ID,
            collection_id = COLLECTION_ID,
            queries = [
                Query.contains('scheduleDetails', search_fragment),
                Query.equal('status', 'SCHEDULED')
            ]
        )

        schedules = response.get('documents', [])
        if not schedules:
            context.log('No meetings found to schedule.')
            return context.res.json({'success': True, 'message': 'No meetings found to schedule.'})

        context.log(f"Found {len(schedules)} meeting(s) matching the time.")

        sent_count = 0
        for schedule in schedules:
            try:
                details = json.loads(schedule.get('scheduleDetails'))
            except json.JSONDecodeError as e:
                context.log(f"Error parsing JSON for document {schedule.get('$id')}: {e}")
                continue

            schedule_frequency = details.get('frequency', '').strip()  # e.g., "Friday", "daily", or "Weekends Only"
            start_date_str = details.get('startDate')
            time = details.get("time")
            meeting_id = schedule.get("meetingId")
            try:
                start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
            except ValueError:
                context.log(f"Invalid startDate format for document {schedule.get('$id')}.")
                continue

            should_send = False

            if now_utc.date() < start_date.date():
                context.log(f"Skipping {schedule.get('$id')}: Schedule starts later than today.")
                continue

            normalized_frequency = schedule_frequency.lower()

            if normalized_frequency == 'daily':
                should_send = True
            elif normalized_frequency == 'weekends only':
                if current_day_name in ['Saturday', 'Sunday']:
                    should_send = True
            elif current_day_name == schedule_frequency:
                should_send = True

            if should_send:
                context.log(f"Sending reminder for meeting ID: {schedule.get('meetingId')} on {schedule_frequency}.")

                participant_targets = schedule.get('participants', [])

                if not participant_targets:
                    context.log(f"Skipping {schedule.get('$id')}: No participants found.")
                    continue

                url = f"{URL_HOST}/meetings/{meeting_id}"
                messaging.create_email(
                    message_id = ID.unique(),
                    subject = "⏰ The Clock Is Ticking! Join Your SkillSwap Session in 15 Minutes!",
                    content = f"<!DOCTYPE html><html lang=\"en\"><head><meta charset=\"UTF-8\"><meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\"><title>SkillSwap Final Countdown</title></head><body style=\"margin: 0; padding: 0; background-color: #0d121c; font-family: 'Arial', sans-serif;\"><center style=\"width: 100%; background-color: #0d121c;\"><div style=\"max-width: 600px; margin: 30px auto; background-color: #10141f; border-radius: 12px; overflow: hidden; box-shadow: 0 0 40px rgba(64, 224, 208, 0.15); border: 2px solid #1a1e2b;\"><table role=\"presentation\" cellspacing=\"0\" cellpadding=\"0\" border=\"0\" width=\"100%\" style=\"padding: 25px 30px; background-color: #151927;\"><tr><td align=\"left\"><h2 style=\"font-size: 28px; font-weight: bold; margin: 0; color: #ffffff;\"><span style=\"color: #40e0d0;\">SkillSwap</span> Session</h2></td><td align=\"right\"><span style=\"font-size: 16px; font-weight: bold; color: #1ed760; border: 2px solid #1ed760; padding: 5px 10px; border-radius: 6px;\">READY</span></td></tr></table><table role=\"presentation\" cellspacing=\"0\" cellpadding=\"0\" border=\"0\" width=\"100%\" style=\"padding: 30px 30px 40px 30px; text-align: center;\"><tr><td style=\"background-color: #0d121c; padding: 25px; border-radius: 10px; border: 1px solid #1a1e2b;\"><p style=\"color: #ffffff; font-size: 18px; margin: 0 0 5px 0;\">Starting In...</p><h1 style=\"color: #1ed760; font-size: 55px; font-weight: 900; margin: 0; text-shadow: 0 0 10px rgba(30, 215, 96, 0.7);\">15 MINS</h1></td></tr><tr><td style=\"padding-top: 25px;\"><p style=\"color: #b0b4bf; font-size: 16px; line-height: 1.6;\">It's almost time to trade your skills! Don't miss this opportunity to connect and share what you know with people all over the world.</p></td></tr><tr><td style=\"padding: 15px 0;\"><p style=\"color: #40e0d0; font-size: 18px; font-weight: bold; margin: 0;\">Your Session Time: <span style=\"color: #ffffff;\">{time}</span></p></td></tr><tr><td style=\"padding: 25px 0 0 0;\"><a href=\"{url}\" target=\"_blank\" style=\"background-color: #40e0d0; color: #000000; text-decoration: none; padding: 18px 40px; border-radius: 4px; font-weight: bold; font-size: 18px; display: inline-block; box-shadow: 0 5px 20px rgba(64, 224, 208, 0.4);\">ENTER THE EXCHANGE</a></td></tr></table><table role=\"presentation\" cellspacing=\"0\" cellpadding=\"0\" border=\"0\" width=\"100%\" style=\"padding: 20px 30px; background-color: #0d121c; border-top: 1px solid #1a1e2b;\"><tr><td align=\"center\"><p style=\"color: #6a748c; font-size: 12px; margin: 0 0 5px 0;\">Trade your skills for knowledge you want. No money, just sharing.</p><p style=\"color: #b0b4bf; font-size: 14px; margin: 0;\">The SkillSwap Team</p></td></tr></table></div></center></body></html>",
                    users = participant_targets,
                    html = True
                )
                sent_count += 1

        context.log(f"Successfully processed and sent {sent_count} reminders.")
        return context.res.json(
            {'success': True, 'processed_reminders': sent_count, 'matched_meetings': len(schedules)})

    except Exception as e:
        context.log(f"An unexpected error occurred during database access or messaging: {e}")
        return context.res.json({'success': False, 'error': str(e)})

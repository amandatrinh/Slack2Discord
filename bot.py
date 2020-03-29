from slackeventsapi import SlackEventAdapter
from slack import WebClient
import os
import requests
from secret import *
import datetime
USERS = {}
CHANNELS = {}

# Our app's Slack Event Adapter for receiving actions via the Events API
slack_signing_secret = SLACK_SIGNING_SECRET
slack_events_adapter = SlackEventAdapter(slack_signing_secret, "/slack/events")

# Create a SlackClient for your bot to use for Web API requests
slack_bot_token = SLACK_BOT_TOKEN
slack_client = WebClient(token=slack_bot_token)

# Example responder to greetings
@slack_events_adapter.on("message")
def handle_message(event_data):
    #print({str(k).encode("utf-8"): str(v).encode("utf-8") for k,v in event_data["event"].items()})
    print(event_data["token"])
    message = event_data["event"]
    channel = get_channel(message["channel"])
    timestamp = datetime.datetime.fromtimestamp(int(message["ts"].split(".")[0]))
    timestamp = timestamp.strftime('%I:%M %p')
    # If the incoming message contains "hi", then respond with a "Hello" message
    if message.get("subtype") is None:
        name = get_user(message["user"])
        message = f"```[#{channel}- {timestamp}] {message['text']}```"
        message = message.encode("utf-8")
        requests.post(DISCORD_WEBHOOK, data={'content': message, 'username': name})
    elif message.get("subtype") == "message_changed":
        name = get_user(message["message"]["user"])
        original_timestamp= datetime.datetime.fromtimestamp(int(message["previous_message"]["ts"].split(".")[0]))
        original_timestamp= original_timestamp.strftime('%I:%M %p')
        message = f"```[#{channel}- {original_timestamp}] {message['previous_message']['text']}\n[#{channel}- {timestamp}](edited) {message['message']['text']} ```"
        message = message.encode("utf-8")
        requests.post(DISCORD_WEBHOOK, data={'content': message, 'username': name})


def get_user(user):
    baseurl = "https://slack.com/api/users.profile.get"
    if user not in USERS:
        r = requests.get(baseurl, params={"token": SLACK_BOT_TOKEN, "user": user})
        USERS[user] = r.json()["profile"]["real_name"]
    return USERS[user]
    print(r.text)

def get_channel(channel):
    baseurl = "https://slack.com/api/conversations.info"
    if channel not in CHANNELS:
        r = requests.get(baseurl, params={"token": SLACK_BOT_TOKEN, "channel": channel})
        print(r.text)
        CHANNELS[channel] = r.json()["channel"]["name"]
    return CHANNELS[channel]


    
# Error events
@slack_events_adapter.on("error")
def error_handler(err):
    print("ERROR: " + str(err))

# Once we have our event listeners configured, we can start the
# Flask server with the default `/events` endpoint on port 3000
slack_events_adapter.start(port=3000)

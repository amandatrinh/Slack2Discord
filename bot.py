from flask import Flask, request
from slackeventsapi import SlackEventAdapter
from slack import WebClient
import os
import requests
from secret import *
import datetime
import pymongo

client = pymongo.MongoClient(MONGO_URI)
db = client.slack
workspace = db.workspace

# Our app's Slack Event Adapter for receiving actions via the Events API
slack_signing_secret = SLACK_SIGNING_SECRET

app = Flask(__name__)
slack_events_adapter = SlackEventAdapter(slack_signing_secret, "/slack/events", app)
@app.route('/all', methods=["GET"])
def test():
    return str(db.all())
@app.route("/begin_auth", methods=["GET"])
def pre_install():
    return '<a href="https://slack.com/oauth/v2/authorize?client_id=1034716147943.1032721399013&user_scope=users.profile:read,channels:history,channels:read"><img alt="Add to Slack" height="40" width="139" src="https://platform.slack-edge.com/img/add_to_slack.png" srcset="https://platform.slack-edge.com/img/add_to_slack.png 1x, https://platform.slack-edge.com/img/add_to_slack@2x.png 2x"></a>'

@app.route("/callback", methods=["GET"])
def authenticate():
    code = request.args.get('code')
    r = requests.post('https://slack.com/api/oauth.v2.access', data={'client_id': CLIENT_ID, 'client_secret': CLIENT_SECRET, 'code': code})
    response = r.json()

    if response["ok"]:
        team_id = response["team"]["id"]
        user_id = response['authed_user']['id']
        team = workspace.find_one({'_id': team_id})

        if team is None:
            workspace.insert_one({
                '_id': team_id,
                'name': response["team"]["name"],
                'authed_users': {
                    user_id : {'token': response["authed_user"]["access_token"], 'webhook': ''} 
                },
                'users': {},
                'channels': {}
            })
        else: 
            workspace.update_one({'_id': team_id}, {'$set': {f'authed_users.{user_id}':{'token': response["authed_user"]["access_token"], 'webhook': ''}}})


    return f"Click on this <a href='/{team_id}/{user_id}'>link</a> to edit your discord webhook."

@app.route('/<tid>/<uid>', methods=["GET"])
def modify_webhook(tid, uid):
    team = workspace.find_one({'_id': tid})
    webhook = team['authed_users'][uid]['webhook']

    return f'<html><body>Your current Discord webhook URL is: { "N/A" if webhook == "" else webhook }<form action="/{tid}/{uid}/submit"><label for="discord_url">Discord Webhook URL:</label><input type="text" id="discord_url" name="discord_url"><br><br><input type="submit" value="Submit"></form></body></html>'

@app.route('/<tid>/<uid>/submit', methods=["GET"])
def submit_webhook(tid, uid):
    webhook = request.args.get('discord_url')
    workspace.update_one({'_id': tid}, {'$set': {f'authed_users.{uid}.webhook': webhook}})
    return f'Success! Your discord webhook is now {webhook}'

@slack_events_adapter.on("message")
def handle_message(event_data):
    team_id = event_data["team_id"]

    team = workspace.find_one({'_id': team_id})
    users = team['authed_users']

    for user in users:
        TOKEN, DISCORD_WEBHOOK = users[user]['token'], users[user]['webhook']
        if DISCORD_WEBHOOK != '':
            message = event_data["event"]
            channel = get_channel(team_id, message["channel"], TOKEN)
            utc_dt = utc.localize(datetime.datetime.utcfromtimestamp(int(message["ts"].split(".")[0])))
            us_tz = timezone("America/Los_Angeles")
            us_dt = us_tz.normalize(utc_dt.astimezone(us_tz))
            timestamp = us_dt.strftime('%I:%M %p')

            if message.get("subtype") is None:
                name = get_user(team_id, message["user"], TOKEN)
                message = f"```[#{channel}- {timestamp}] {message['text']}```"
                message = message.encode("utf-8")
                requests.post(DISCORD_WEBHOOK, data={'content': message, 'username': name})
            elif message.get("subtype") == "message_changed":
                name = get_user(team_id, message["message"]["user"], TOKEN)
                utc_dt_og = utc.localize(datetime.datetime.utcfromtimestamp(int(message["previous_message"]["ts"].split(".")[0]))
                us_dt_og = us_tz.normalize(utc_dt.astimezone(us_tz))
                original_timestamp = us_dt_og.strftime('%I:%M %p')
                message = f"```[#{channel}- {original_timestamp}] {message['previous_message']['text']}\n[#{channel}- {timestamp}](edited) {message['message']['text']} ```"
                message = message.encode("utf-8")
                requests.post(DISCORD_WEBHOOK, data={'content': message, 'username': name})


def get_user(team_id, user_id, token):
    base_url = "https://slack.com/api/users.profile.get"
    users = workspace.find_one({'_id': team_id}, projection=['users'])['users']
    if user_id not in users:
        r = requests.get(base_url, params={"token": token, "user": user_id})
        users = workspace.update_one({'_id': team_id}, {'$set': {f'users.{user_id}': r.json()["profile"]["real_name"]}})

    return users[user_id]

def get_channel(team_id ,channel_id, token):
    base_url = "https://slack.com/api/conversations.info"
    channels = workspace.find_one({'_id': team_id}, projection=['channels'])['channels']
    if channel_id not in channels:
        r = requests.get(base_url, params={"token": token, "channel": channel_id})
        workspace.update_one({'_id': team_id}, {'$set': {f'channels.{channel_id}': r.json()["channel"]["name"]}})

    return channels[channel_id]

# Error events
@slack_events_adapter.on("error")
def error_handler(err):
    print("ERROR: " + str(err))

# Once we have our event listeners configured, we can start the
# Flask server with the default `/events` endpoint on port 3000
if __name__ == "__main__":
  app.run(port=3000)

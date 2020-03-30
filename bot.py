from flask import Flask, request
from slackeventsapi import SlackEventAdapter
from slack import WebClient
import os
import requests
from secret import *
import datetime
from tinydb import TinyDB, Query

db = TinyDB('db.json')

USERS = {}
CHANNELS = {}

# Our app's Slack Event Adapter for receiving actions via the Events API
slack_signing_secret = SLACK_SIGNING_SECRET

app = Flask(__name__)
slack_events_adapter = SlackEventAdapter(slack_signing_secret, "/slack/events", app)

@app.route("/begin_auth", methods=["GET"])
def pre_install():
    return '<a href="https://slack.com/oauth/v2/authorize?client_id=1034716147943.1032721399013&user_scope=users.profile:read,channels:history,channels:read"><img alt="Add to Slack" height="40" width="139" src="https://platform.slack-edge.com/img/add_to_slack.png" srcset="https://platform.slack-edge.com/img/add_to_slack.png 1x, https://platform.slack-edge.com/img/add_to_slack@2x.png 2x"></a>'

@app.route("/callback", methods=["GET"])
def authenticate():
    code = request.args.get('code')
    print(code)
    r = requests.post('https://slack.com/api/oauth.v2.access', data={'client_id': CLIENT_ID, 'client_secret': CLIENT_SECRET, 'code': code})
    response = r.json()

    if response["ok"]:
        team_id = response["team"]["id"]
        user_id = response['authed_user']['id']
        Team = Query()
        id = db.search(Team.id == team_id)
        if len(id) == 0:
            db.insert({
                'id': team_id,
                'name': response["team"]["name"],
                'authed_users': {
                    user_id : {'token': response["authed_user"]["access_token"], 'webhook': ''} 
                }
            })
        else:
            id = id[0]
            authed_users = id['authed_users']
            authed_users[response['authed_user']['id']] = {'token': response["authed_user"]["access_token"], 'webhook': ''} 
            db.update({'authed_users' : authed_users}, Team.id == response["team"]["id"])

    return f"Click on this <a href='https://8d15df90.ngrok.io/{team_id}/{user_id}'>link</a> to edit your discord webhook."

@app.route('/<tid>/<uid>', methods=["GET"])
def modify_webhook(tid, uid):
    Team = Query()
    team = db.search(Team.id == tid)[0]
    webhook = authed_users = team['authed_users'][uid]['webhook']

    return f'<html><body>"Your current Discord webhook URL is: { "N/A" if webhook == "" else webhook }<form action="/{tid}/{uid}/submit"><label for="discord_url">Discord Webhook URL:</label><input type="text" id="discord_url" name="discord_url"><br><br><input type="submit" value="Submit"></form></body></html>'

@app.route('/<tid>/<uid>/submit', methods=["GET"])
def submit_webhook(tid, uid):
    Team = Query()
    team = db.search(Team.id == tid)[0]
    authed_users = team['authed_users']
    authed_users[uid]['webhook'] = request.args.get('discord_url')
    db.update({'authed_users': authed_users }, Team.id == tid)
    return 'Success!'

@slack_events_adapter.on("message")
def handle_message(event_data):
    print(event_data["token"])
    team_id = event_data["team_id"]
    Team = Query()
    users = db.search(Team.id == team_id)[0]['authed_users']

    for user in users:
        TOKEN, DISCORD_WEBHOOK = users[user]['token'], users[user]['webhook']
        if DISCORD_WEBHOOK == '':
            return

        message = event_data["event"]
        channel = get_channel(message["channel"], TOKEN)
        timestamp = datetime.datetime.fromtimestamp(int(message["ts"].split(".")[0]))
        timestamp = timestamp.strftime('%I:%M %p')

        if message.get("subtype") is None:
            name = get_user(message["user"], TOKEN)
            message = f"```[#{channel}- {timestamp}] {message['text']}```"
            message = message.encode("utf-8")
            requests.post(DISCORD_WEBHOOK, data={'content': message, 'username': name})
        elif message.get("subtype") == "message_changed":
            name = get_user(message["message"]["user"], TOKEN)
            original_timestamp= datetime.datetime.fromtimestamp(int(message["previous_message"]["ts"].split(".")[0]))
            original_timestamp= original_timestamp.strftime('%I:%M %p')
            message = f"```[#{channel}- {original_timestamp}] {message['previous_message']['text']}\n[#{channel}- {timestamp}](edited) {message['message']['text']} ```"
            message = message.encode("utf-8")
            requests.post(DISCORD_WEBHOOK, data={'content': message, 'username': name})


def get_user(user, token):
    baseurl = "https://slack.com/api/users.profile.get"
    if user not in USERS:
        r = requests.get(baseurl, params={"token": token, "user": user})
        USERS[user] = r.json()["profile"]["real_name"]
    return USERS[user]
    print(r.text)

def get_channel(channel, token):
    baseurl = "https://slack.com/api/conversations.info"
    if channel not in CHANNELS:
        r = requests.get(baseurl, params={"token": token, "channel": channel})
        print(r.text)
        CHANNELS[channel] = r.json()["channel"]["name"]
    return CHANNELS[channel]

# Error events
@slack_events_adapter.on("error")
def error_handler(err):
    print("ERROR: " + str(err))

# Once we have our event listeners configured, we can start the
# Flask server with the default `/events` endpoint on port 3000
if __name__ == "__main__":
  app.run(port=3000)
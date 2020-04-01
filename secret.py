import os
SLACK_SIGNING_SECRET = os.environ.get('SLACK_SIGNING_SECRET', '')
CLIENT_ID = os.environ.get('CLIENT_ID', '')
CLIENT_SECRET = os.environ.get('CLIENT_SECRET', '')
MONGO_URI = os.environ.get('MONGO_URI', '')


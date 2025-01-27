import json
from types import SimpleNamespace

import requests

from secrets import AUTH_USERNAME, AUTH_PASSWORD

HOSTNAME_ENTRYWAY = "bsky.social"
AUTH_METHOD_PASSWORD, AUTH_METHOD_TOKEN = range(2)

"""
Usage:
session.get(hostname="api.bsky.chat",  endpoint="xrpc/chat.bsky.convo.listConvos")
session.get(hostname="api.bsky.chat",  endpoint="xrpc/chat.bsky.convo.getConvo", params={"convoId": convo.id})
session.get(hostname="api.bsky.chat",  endpoint="xrpc/chat.bsky.convo.getMessages", params={"convoId": convo.id})
session.post(hostname="api.bsky.chat", endpoint="xrpc/chat.bsky.convo.sendMessage", params={"convoId": convo.id, "message": {"text": "message text"}})
session.get(hostname="api.bsky.chat", endpoint="xrpc/chat.bsky.convo.getLog", params={"cursor": "2222222tc2d5v"})

session.get(hostname="api.bsky.app",  endpoint="xrpc/app.bsky.notification.listNotifications", params={"cursor": "2024-07-09T00:37:17.385Z"})
session.post(hostname="api.bsky.app",  endpoint="xrpc/app.bsky.notification.updateSeen", params={"seenAt": "2025-01-26T00:00:00Z"})
"""

class Session(object):

    def __init__(self):
        self.session = self.post(endpoint="xrpc/com.atproto.server.createSession", auth_method=AUTH_METHOD_PASSWORD)

    def refresh_session(self):
        self.session = self.post(endpoint="xrpc/com.atproto.server.refreshSession", use_refresh_token=True)

    def call(self, method=requests.get, hostname=HOSTNAME_ENTRYWAY, endpoint=None, auth_method=AUTH_METHOD_TOKEN, params=None, use_refresh_token=False):

        uri = f"https://{hostname}/{endpoint}"
        args = {}

        if auth_method == AUTH_METHOD_TOKEN and not use_refresh_token:
            args["headers"] = {"Authorization": f"Bearer {self.session.accessJwt}"}
        elif auth_method == AUTH_METHOD_TOKEN and use_refresh_token:
            args["headers"] = {"Authorization": f"Bearer {self.session.refreshJwt}"}
        elif auth_method == AUTH_METHOD_PASSWORD:
            args["json"] = {"identifier": AUTH_USERNAME, "password": AUTH_PASSWORD}

        if params and method == requests.get:
            args["params"] = params
        elif params and method == requests.post:
            if "json" in args:
                args["json"].update(params)
            else:
                args["json"] = params

        r = method(uri, **args)

        if r.status_code == 400 and r.json()["error"] == "ExpiredToken":
            self.refresh_session()
            args["headers"] = {"Authorization": f"Bearer {self.session.accessJwt}"}
            r = method(uri, **args)

        if r.status_code != 200:
            print(r.text)

        assert r.status_code == 200, f"r.status_code: {r.status_code}"

        try:
            if r.text:
                return json.loads(r.text, object_hook=lambda d: SimpleNamespace(**d))
            else:
                return None
        except json.JSONDecodeError as e:
            print(r.status_code)
            print(r.text)
            print(e)
            raise

    def post(self, **kwargs):
        kwargs["method"] = requests.post
        return self.call(**kwargs)

    def get(self, **kwargs):
        kwargs["method"] = requests.get
        return self.call(**kwargs)

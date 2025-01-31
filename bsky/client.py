import json
import inspect
from types import SimpleNamespace
from datetime import datetime
import requests

from database.models import BskySession, BskyAPICursor, BskyUserProfile
from bsky.secrets import AUTH_USERNAME, AUTH_PASSWORD

HOSTNAME_ENTRYWAY = "bsky.social"
AUTH_METHOD_PASSWORD, AUTH_METHOD_TOKEN = range(2)
SESSION_METHOD_CREATE, SESSION_METHOD_REFRESH = range(2)
ZERO_CURSOR = "2222222222222"

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
        # note - don't add class attributes that aren't json serializable
        try:
            self.load_serialized_session()
        except Exception as e:
            print(f"+++++++ NO SERIALIZED SESSION: {e} ++++++++++")
            self.create_session()


    def process_cursor(func):
        """Decorator for any api call that returns a cursor, this looks up the previous
        cursor from the database, applies it to the call, and saves the newly returned
        cursor to the database."""

        ins = inspect.signature(func)
        _endpoint = ins.parameters["endpoint"].default

        def inner(self, **kwargs):
            endpoint = kwargs.get("endpoint", _endpoint)
            previous_cursor = BskyAPICursor.select().where(endpoint==endpoint).order_by(BskyAPICursor.timestamp.desc()).first()
            kwargs["cursor"] = previous_cursor.cursor if previous_cursor else ZERO_CURSOR
            response = func(self, **kwargs)
            try:
                save_cursor = response.cursor
                if previous_cursor and previous_cursor.cursor == save_cursor:
                    # don't save a new cursor record if it hasn't changed
                    pass
                else:
                    BskyAPICursor.create(endpoint=endpoint, cursor=save_cursor)
            except AttributeError:
                print(f"no cursor in response for {endpoint}")

            return response

        return inner


    def create_session(self, method=SESSION_METHOD_CREATE):

        try:
            if method == SESSION_METHOD_CREATE:
                print("++++++++++++ NEW SESSION ++++++++++++")
                session = self.post(endpoint="xrpc/com.atproto.server.createSession", auth_method=AUTH_METHOD_PASSWORD)
            elif method == SESSION_METHOD_REFRESH:
                print("++++++++++++ REFRESH SESSION ++++++++++++")
                session = self.post(endpoint="xrpc/com.atproto.server.refreshSession", use_refresh_token=True)
            self.exception = None
            self.accessJwt = session.accessJwt
            self.refreshJwt = session.refreshJwt
            self.did = session.did
        except Exception as e:
            self.exception = f"{e.__class__.__name__} - {e}"

        self.create_method = method
        self.created_at = datetime.now().isoformat()

        self.serialize()
        print(json.dumps(self.__dict__, indent=4))

        bs = BskySession(**self.__dict__)
        bs.save()


    def refresh_session(self):
        self.create_session(method=SESSION_METHOD_REFRESH)

    def serialize(self):
        bs = BskySession(**self.__dict__)
        bs.save()

    def load_serialized_session(self):
        db_session = BskySession.select().order_by(BskySession.created_at.desc())[0]
        self.__dict__ = db_session.__dict__["__data__"]


    def call(self, method=requests.get, hostname=HOSTNAME_ENTRYWAY, endpoint=None, auth_method=AUTH_METHOD_TOKEN, params=None, use_refresh_token=False, data=None, headers=None):

        uri = f"https://{hostname}/{endpoint}"

        args = {}
        args["headers"] = headers or {}

        if auth_method == AUTH_METHOD_TOKEN and not use_refresh_token:
            args["headers"].update({"Authorization": f"Bearer {self.accessJwt}"})
        elif auth_method == AUTH_METHOD_TOKEN and use_refresh_token:
            args["headers"].update({"Authorization": f"Bearer {self.refreshJwt}"})
        elif auth_method == AUTH_METHOD_PASSWORD:
            args["json"] = {"identifier": AUTH_USERNAME, "password": AUTH_PASSWORD}

        if params and method == requests.get:
            args["params"] = params
        elif data and method == requests.post:
            args["data"] = data
        elif params and method == requests.post:
            if "json" in args:
                args["json"].update(params)
            else:
                args["json"] = params

        r = method(uri, **args)

        if r.status_code == 400 and r.json()["error"] == "ExpiredToken":
            self.refresh_session()
            args["headers"]["Authorization"] = f"Bearer {self.accessJwt}"
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

    def upload_file(self, image_data, mimetype):
        return self.post(data=image_data, endpoint="xrpc/com.atproto.repo.uploadBlob", headers={"Content-Type": mimetype})

    def create_record(self, post):
        params = {
            "repo": self.did,
            "collection": "app.bsky.feed.post",
            "record": post,
        }
        return self.post(endpoint="xrpc/com.atproto.repo.createRecord", params=params)


    def get_profile(self, actor):
        endpoint = "xrpc/app.bsky.actor.getProfile"
        return self.get(endpoint=endpoint, params={"actor": actor})


    @process_cursor
    def get_convo_logs(self, endpoint="xrpc/chat.bsky.convo.getLog", cursor=None):
        # usage notes: https://github.com/bluesky-social/atproto/issues/2760
        return self.get(hostname="api.bsky.chat", endpoint=endpoint, params={"cursor": cursor})


if __name__=="__main__":
    s = Session()
    # s.get_convo_logs()
    # actor = "did:plc:5euo5vsiaqnxplnyug3k3art"
    actor = "stroma-news.bsky.social"
    user = BskyUserProfile.get_or_create_from_api(actor, s)
    print(user.id)

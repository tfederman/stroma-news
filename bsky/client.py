import json
import inspect
from types import SimpleNamespace
from datetime import datetime
import requests

from database.models import BskySession, BskyAPICursor, BskyUserProfile, BskyAPIResponseError
from settings import log, AUTH_USERNAME, AUTH_PASSWORD

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
        try:
            self.load_serialized_session()
        except Exception as e:
            self.create_session()


    def process_cursor(func):
        """Decorator for any api call that returns a cursor, this looks up the previous
        cursor from the database, applies it to the call, and saves the newly returned
        cursor to the database."""

        ins = inspect.signature(func)
        _endpoint = ins.parameters["endpoint"].default

        def cursor_mgmt(self, **kwargs):
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
                log.info(f"No cursor in response for {endpoint}")

            return response

        return cursor_mgmt


    def create_session(self, method=SESSION_METHOD_CREATE):

        try:
            if method == SESSION_METHOD_CREATE:
                log.info(f"Bluesky client session created from API")
                session = self.post(endpoint="xrpc/com.atproto.server.createSession", auth_method=AUTH_METHOD_PASSWORD)
            elif method == SESSION_METHOD_REFRESH:
                log.info(f"Bluesky client session refreshed from API")
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
        log.info(json.dumps(self.__dict__))

        self.set_auth_header()


    def set_auth_header(self):
        self.auth_header = {"Authorization": f"Bearer {self.accessJwt}"}

    def refresh_session(self):
        self.create_session(method=SESSION_METHOD_REFRESH)

    def serialize(self):
        bs = BskySession(**self.__dict__)
        # cause a new record to be saved rather than updating the previous one
        bs.id = None
        bs.save()

    def load_serialized_session(self):
        db_session = BskySession.select().order_by(BskySession.created_at.desc())[0]
        self.__dict__ = db_session.__dict__["__data__"]
        self.set_auth_header()


    def call(self, method=requests.get, hostname=HOSTNAME_ENTRYWAY, endpoint=None, auth_method=AUTH_METHOD_TOKEN, params=None, use_refresh_token=False, data=None, headers=None):

        uri = f"https://{hostname}/{endpoint}"

        args = {}
        args["headers"] = headers or {}
        args["headers"].update(self.auth_header)
        params = params or {}

        if auth_method == AUTH_METHOD_TOKEN and use_refresh_token:
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

        try:
            r = method(uri, **args)
            call_exception = None
        except Exception as e:
            r = None
            call_exception = e

        if Session.is_expired_token_response(r):
            self.refresh_session()

            # need to update auth header in args with new access token
            args["headers"].update(self.auth_header)

            try:
                r = method(uri, **args)
                call_exception = None
            except Exception as e:
                call_exception = e

        if not r or getattr(r, "status_code", 0) != 200 or call_exception:
            response_error = BskyAPIResponseError.create(
                api_host = hostname,
                endpoint = endpoint,
                params = json.dumps(params),
                method = method.__name__,
                headers = json.dumps(args["headers"]),
                auth_method = auth_method,
                exception_class = call_exception.__class__.__name__ if call_exception else None,
                exception_text = str(call_exception) if call_exception else None,
                http_status_code = getattr(r, "status_code", None),
                response_text = getattr(r, "text", None),
            )
            log.error(f"SELECT * FROM bsky_api_response_error WHERE id={response_error.id};")

            if isinstance(call_exception, Exception):
                raise call_exception
            elif not r:
                raise Exception(f"Failed request, no request object")
            elif r.status_code != 200:
                raise Exception(f"Failed request, status code {r.status_code}")

        try:
            if r.text:
                return json.loads(r.text, object_hook=lambda d: SimpleNamespace(**d))
            else:
                return None
        except json.JSONDecodeError as e:
            log.error(f"{r.status_code}")
            log.error(f"{r.text}")
            log.error(f"{e}")
            raise

    def post(self, **kwargs):
        kwargs["method"] = requests.post
        return self.call(**kwargs)

    def get(self, **kwargs):
        kwargs["method"] = requests.get
        return self.call(**kwargs)

    @staticmethod
    def is_expired_token_response(r):
        try:
            return r.status_code == 400 and r.json()["error"] == "ExpiredToken"
        except:
            return False

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
    def get_convo_logs(self, endpoint="xrpc/chat.bsky.convo.getLog", cursor=ZERO_CURSOR):
        # usage notes: https://github.com/bluesky-social/atproto/issues/2760
        return self.get(hostname="api.bsky.chat", endpoint=endpoint, params={"cursor": cursor})


if __name__=="__main__":
    from bsky import session
    # s.get_convo_logs()
    # actor = "did:plc:5euo5vsiaqnxplnyug3k3art"
    actor = "stroma-news.bsky.social"
    user = BskyUserProfile.get_or_create_from_api(actor, s)
    print(user.id)

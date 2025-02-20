import json
import inspect
from types import SimpleNamespace
from datetime import datetime
import requests

from database.models import BskySession, BskyAPICursor, BskyUserProfile, APICallLog
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

class NoCursorException(Exception):
    pass

class ExcessiveIteration(Exception):
    pass

class Session(object):

    def __init__(self):
        try:
            self.load_serialized_session()
        except Exception as e:
            self.create_session()


    def process_cursor(func, **kwargs):
        """Decorator for any api call that returns a cursor, this looks up the previous
        cursor from the database, applies it to the call, and saves the newly returned
        cursor to the database."""

        inspection = inspect.signature(func)
        _endpoint = inspection.parameters["endpoint"].default
        _collection_attr = inspection.parameters["collection_attr"].default
        _paginate = inspection.parameters["paginate"].default

        def cursor_mgmt(self, **kwargs):
            endpoint = kwargs.get("endpoint", _endpoint)
            collection_attr = kwargs.get("collection_attr", _collection_attr)
            paginate = kwargs.get("paginate", _paginate)

            # only provide the database-backed cursor if one was not passed manually
            if not "cursor" in kwargs:
                previous_db_cursor = BskyAPICursor.select().where(BskyAPICursor.endpoint==endpoint).order_by(BskyAPICursor.timestamp.desc()).first()
                kwargs["cursor"] = previous_db_cursor.cursor if previous_db_cursor else ZERO_CURSOR
                if kwargs["cursor"] == ZERO_CURSOR:
                    previous_db_cursor = BskyAPICursor(cursor=ZERO_CURSOR)
            else:
                previous_db_cursor = None

            if paginate:
                responses, final_cursor = self.call_with_pagination(func, **kwargs)
                response = self.combine_paginated_responses(responses, collection_attr)
            else:
                response = func(self, **kwargs)
                final_cursor = response.cursor

            if previous_db_cursor and previous_db_cursor.cursor != final_cursor:
                # only save a new cursor record if it's changed and originally came from the database (or inherited the default value)
                BskyAPICursor.create(endpoint=endpoint, cursor=final_cursor)

            return response

        return cursor_mgmt


    def combine_paginated_responses(self, responses, collection_attr="logs"):

        for page_response in responses[1:]:
            combined_collection = getattr(responses[0], collection_attr) + getattr(page_response, collection_attr)
            setattr(responses[0], collection_attr, combined_collection)

        return responses[0]


    def call_with_pagination(self, func, **kwargs):

        assert "cursor" in kwargs, "called call_with_pagination without a cursor argument"
        responses = []
        iteration_count = 0
        ITERATION_MAX = 100

        while True:

            iteration_count += 1
            if iteration_count > ITERATION_MAX:
                raise ExcessiveIteration(f"tried to paginate through too many pages ({ITERATION_MAX})")

            response = func(self, **kwargs)
            responses.append(response)

            try:
                new_cursor = response.cursor
                if new_cursor == kwargs["cursor"]:
                    break

                kwargs["cursor"] = new_cursor

            except AttributeError:
                log.error(f"no cursor found in api call that was expected to have one: {kwargs['endpoint']} ({iteration_count})")
                raise

        return responses, kwargs["cursor"]

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

    def call_with_session_refresh(self, method, uri, args):
        r = method(uri, **args)

        if Session.is_expired_token_response(r):
            self.refresh_session()
            args["headers"].update(self.auth_header)
            r = method(uri, **args)

        return r


    def call(self, method=requests.get, hostname=HOSTNAME_ENTRYWAY, endpoint=None, auth_method=AUTH_METHOD_TOKEN, params=None, use_refresh_token=False, data=None, headers=None, skip_log=False):

        uri = f"https://{hostname}/{endpoint}"

        apilog = APICallLog(endpoint=endpoint, method=method.__name__, hostname=hostname, cursor_passed=params.get("cursor") if params else None)

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

        params_text = json.dumps(params)
        apilog.params = params_text[:2048]

        try:
            r = self.call_with_session_refresh(method, uri, args)
            response_object = json.loads(r.text, object_hook=lambda d: SimpleNamespace(**d))

            apilog.http_status_code = r.status_code
            if r.status_code != 200:
                apilog.exception_response = r.text
                apilog.exception_class = getattr(response_object, "error", None)
                apilog.exception_text = getattr(response_object, "message", None)

            apilog.response_keys = ",".join(sorted(response_object.__dict__.keys()))
            apilog.cursor_received = getattr(response_object, "cursor", None)
            call_exception = None
        except Exception as e:
            r = None
            apilog.exception_class = __class__.__name__
            apilog.exception_text = str(e)
            response_object = None
            call_exception = e

        if not skip_log:
            apilog.save()

        if apilog.exception_class:
            log.error(f"{apilog.exception_class} - for more details run the query:")
            log.error(f"SELECT * FROM api_call_log WHERE id={apilog.id};")

        if apilog.http_status_code and apilog.http_status_code >= 400:
            log.error(f"Status code: {apilog.http_status_code}")
            raise Exception(f"Failed request, status code {apilog.http_status_code} ({getattr(apilog, 'exception_class', '')})")

        # after logging to the database, exceptions should be raised to the calling code
        if isinstance(call_exception, Exception):
            raise call_exception
        elif not r:
            raise Exception(f"Failed request, no request object ({getattr(apilog, 'exception_class', '')})")
        elif r.status_code != 200:
            raise Exception(f"Failed request, status code {r.status_code} ({getattr(apilog, 'exception_class', '')})")

        return response_object


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


    def create_record(self, collection, post):
        params = {
            "repo": self.did,
            "collection": collection,
            "record": post,
        }
        return self.post(endpoint="xrpc/com.atproto.repo.createRecord", params=params)

    def create_post(self, post):
        return self.create_record("app.bsky.feed.post", post)


    def delete_record(self, collection, rkey):
        params = {
            "repo": self.did,
            "collection": collection,
            "rkey": rkey,
        }
        return self.post(endpoint="xrpc/com.atproto.repo.deleteRecord", params=params)

    def delete_post(self, post_id):
        return self.delete_record("app.bsky.feed.post", post_id)


    def get_profile(self, actor):
        endpoint = "xrpc/app.bsky.actor.getProfile"
        return self.get(endpoint=endpoint, params={"actor": actor})


    @process_cursor
    def get_convo_logs(self, endpoint="xrpc/chat.bsky.convo.getLog", cursor=ZERO_CURSOR, collection_attr="logs", paginate=True):
        # usage notes: https://github.com/bluesky-social/atproto/issues/2760
        return self.get(hostname="api.bsky.chat", endpoint=endpoint, params={"cursor": cursor})


if __name__=="__main__":
    from bsky import session
    # session.get_convo_logs()
    # actor = "did:plc:5euo5vsiaqnxplnyug3k3art"
    actor = "stroma-news.bsky.social"
    user = BskyUserProfile.get_or_create_from_api(actor, session)
    print(user.id)

import base64
import json

# This code was copied from the atproto library. The full atproto library
# can't be included in this project because the import takes four seconds
# and that would cause a lambda error with its default timeout.


def force_bytes(value):
    if isinstance(value, str):
        return value.encode("UTF-8")
    return value


def base64url_decode(input_data):
    input_bytes = force_bytes(input_data)
    rem = len(input_bytes) % 4
    if rem > 0:
        input_bytes += b"=" * (4 - rem)
    return base64.urlsafe_b64decode(input_bytes)


def get_payload(auth_header):
    jwt = auth_header[len("Bearer ") :].strip()
    signing_input, crypto_segment = jwt.rsplit(".", 1)
    header_segment, payload_segment = signing_input.split(".", 1)
    return json.loads(base64url_decode(payload_segment))


def get_user_did(auth_header):
    payload = get_payload(auth_header)
    return payload.get("iss", "")

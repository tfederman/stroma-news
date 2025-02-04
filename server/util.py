import json

def response(body_obj, status_code=200):
    return {'statusCode': status_code, 'body': json.dumps(body_obj)}

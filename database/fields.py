import hashlib

import peewee


class SHA1HashedField(peewee.Field):
    """Hash a string value on its way into the database so as to be able to track distinct values without saving the sensitive raw data."""
    PREFIX_TOKEN = "sha1:"

    field_type = 'text'

    def db_value(self, value):
    
        # don't re-hash an already hashed value
        if value.startswith(SHA1HashedField.PREFIX_TOKEN):
            return value
        
        if isinstance(value, bytes):
            return SHA1HashedField.PREFIX_TOKEN + hashlib.sha1(value).hexdigest()
        elif isinstance(value, str):
            return SHA1HashedField.PREFIX_TOKEN + hashlib.sha1(value.encode("utf-8")).hexdigest()
        else:
            raise Exception(f"wrong data type for a SHA1HashedField column: {type(value)}")
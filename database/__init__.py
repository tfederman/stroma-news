import os

import peewee

db = peewee.SqliteDatabase(f"{os.path.dirname(os.path.abspath(__file__))}/stroma.db")
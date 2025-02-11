import sys
import inspect

from database import db
import database.models


def migrate_pgsql(cls, con):
    """Utility function to migrate data from a sqlite db to a postgres db."""
    rows = list(cls.select().order_by(cls.id).tuples())
    cursor = con.cursor()
    column_count = len(rows[0])
    column_placeholders = ",".join(["%s"] * column_count)
    table = cls._meta.table_name
    cursor.executemany(f'INSERT INTO "{table}" VALUES ({column_placeholders})', rows)
    cursor.execute(f"SELECT setval('{table}_id_seq', (SELECT MAX(id) FROM \"{table}\"));")
    con.commit()


def get_model_classes():
    class_members = inspect.getmembers(sys.modules["database.models"], inspect.isclass)
    return [(n,cls) for n,cls in class_members if cls.__base__ == database.models.BaseModel]


def create_non_existing_tables(db):

    all_model_classes = get_model_classes()
    missing_table_model_classes = [(n,cls) for n,cls in all_model_classes if not cls.table_exists()]

    if not missing_table_model_classes:
        print("All tables already exist.")
    else:
        print(f"Creating missing tables: {', '.join(str(cls._meta.table_name) for n,cls in missing_table_model_classes)}")
        db.create_tables([cls for n,cls in missing_table_model_classes])


if __name__=="__main__":

    # create new tables:
    create_non_existing_tables(db)

    # migrating sqlite data to postgres:
    # import psycopg2
    # con = psycopg2.connect("dbname=stroma ...")
    # for _,cls in get_model_classes():
    #     print(f"migrating {cls._meta.table_name}...")
    #     migrate_pgsql(cls, con)

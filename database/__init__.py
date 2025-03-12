import os

from playhouse.postgres_ext import PostgresqlExtDatabase


def get_db_postgresql():

    try:
        required_pgsql_env_vars = [
            ("PGDATABASE", "database"),
            ("PGUSER", "user"),
            ("PGHOST", "host"),
            ("PGPASSWORD", "password"),
        ]
        optional_pgsql_env_vars = [("PGPORT", "port")]
        pgsql_args = {argname: os.environ[varname] for varname, argname in required_pgsql_env_vars}
        pgsql_args.update(
            {
                argname: os.getenv(varname)
                for varname, argname in optional_pgsql_env_vars
                if os.getenv(varname)
            }
        )
        return PostgresqlExtDatabase(**pgsql_args)
    except KeyError:
        return None

db = get_db_postgresql()

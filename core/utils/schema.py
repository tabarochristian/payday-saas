# utils.py
from django.db import connection

def create_schema_if_not_exists(schema_name):
    with connection.cursor() as cursor:
        cursor.execute("SELECT schema_name FROM information_schema.schemata WHERE schema_name = %s;", [schema_name])
        if cursor.fetchone(): return
        cursor.execute(f'CREATE SCHEMA {schema_name};')

def set_schema(schema_name):
    connection.schema_name = schema_name
    with connection.cursor() as cursor:
        cursor.execute(f"SET search_path TO {schema_name};")
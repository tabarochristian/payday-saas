# core/utils/schema.py
import logging
from django.db import connection
from django.conf import settings

logger = logging.getLogger(__name__)


# ============================================================
# VENDOR CAPABILITIES & STRATEGIES (Extensible, Declarative)
# ============================================================

class VendorStrategy:
    """Base class for schema-capable database vendors."""
    supports_schema = False

    @staticmethod
    def schema_exists(cursor, schema_name: str) -> bool:
        raise NotImplementedError

    @staticmethod
    def create_schema(cursor, schema_name: str) -> None:
        raise NotImplementedError

    @staticmethod
    def set_search_path(cursor, schema_name: str) -> None:
        raise NotImplementedError


class PostgreSQLStrategy(VendorStrategy):
    supports_schema = True

    @staticmethod
    def schema_exists(cursor, schema_name: str) -> bool:
        cursor.execute(
            "SELECT schema_name FROM information_schema.schemata WHERE schema_name = %s;",
            [schema_name],
        )
        return cursor.fetchone() is not None

    @staticmethod
    def create_schema(cursor, schema_name: str) -> None:
        cursor.execute(f"CREATE SCHEMA {schema_name};")

    @staticmethod
    def set_search_path(cursor, schema_name: str) -> None:
        cursor.execute(f"SET search_path TO {schema_name}, public;")


# Add future vendors here (CockroachDB, Oracle, etc.)
VENDOR_STRATEGIES = {
    "postgresql": PostgreSQLStrategy,
    "cockroachdb": PostgreSQLStrategy,  # same SQL semantics
    # "oracle": OracleStrategy,
}


def get_vendor_strategy():
    """Return the strategy class for the current DB vendor."""
    return VENDOR_STRATEGIES.get(connection.vendor, VendorStrategy)


# ============================================================
# PUBLIC API
# ============================================================

def create_schema_if_not_exists(schema_name: str) -> None:
    """
    Create a schema if supported by the vendor and not already present.
    Fully idempotent and vendor-agnostic.
    """
    strategy = get_vendor_strategy()

    if not strategy.supports_schema:
        logger.debug("Schema creation skipped — vendor '%s' has no schema support", connection.vendor)
        return

    try:
        with connection.cursor() as cursor:
            if strategy.schema_exists(cursor, schema_name):
                logger.debug("Schema '%s' already exists", schema_name)
                return

            strategy.create_schema(cursor, schema_name)
            logger.info("Created schema '%s' on vendor '%s'", schema_name, connection.vendor)

    except Exception as e:
        logger.error("Failed to create schema '%s' on %s: %s", schema_name, connection.vendor, e)
        raise


def set_schema(schema_name: str) -> None:
    """
    Switch the active schema for the current DB session.
    Skipped in DEBUG mode or on vendors without schema support.
    """
    if settings.DEBUG:
        logger.debug("DEBUG=True — schema switching disabled")
        return

    strategy = get_vendor_strategy()

    if not strategy.supports_schema:
        logger.debug("Schema switching skipped — vendor '%s' has no schema support", connection.vendor)
        return

    try:
        connection.schema_name = schema_name  # optional introspection hook

        with connection.cursor() as cursor:
            strategy.set_search_path(cursor, schema_name)

        logger.info("Active schema set to '%s' (%s)", schema_name, connection.vendor)

    except Exception as e:
        logger.error("Failed to set schema '%s' on %s: %s", schema_name, connection.vendor, e)
        raise

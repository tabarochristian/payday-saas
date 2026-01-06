"""
Cross-database utilities for Django models.

This module provides database-agnostic functions and classes for common
operations that differ between PostgreSQL, SQLite, MySQL, and other databases.
"""

from datetime import timedelta, date
from typing import Optional

from django.db import connection
from django.db.models import (
    F, Func, ExpressionWrapper, IntegerField, Case, When, Value, BooleanField
)


# =============================================================================
# Custom Database Functions
# =============================================================================

class Epoch(Func):
    function = 'EXTRACT'
    template = '%(function)s(EPOCH FROM %(expressions)s)'
    output_field = IntegerField()


class JulianDay(Func):
    function = "JULIANDAY"
    output_field = IntegerField()


class DateDiff(Func):
    function = "DATEDIFF"
    output_field = IntegerField()


# =============================================================================
# Cross-Database Expression Builders
# =============================================================================

def get_duration_days(start_field='start_date', end_field='end_date', inclusive=False):
    adjustment = 1 if inclusive else 0

    if connection.vendor == 'postgresql':
        return ExpressionWrapper(
            Epoch(F(end_field) - F(start_field)) / 86400 + adjustment,
            output_field=IntegerField()
        )

    elif connection.vendor == 'sqlite':
        return ExpressionWrapper(
            JulianDay(F(end_field)) - JulianDay(F(start_field)) + adjustment,
            output_field=IntegerField()
        )

    elif connection.vendor in ('mysql', 'oracle'):
        return ExpressionWrapper(
            DateDiff(F(end_field), F(start_field)) + adjustment,
            output_field=IntegerField()
        )

    return ExpressionWrapper(
        (F(end_field) - F(start_field)) / timedelta(days=1) + adjustment,
        output_field=IntegerField()
    )


def get_weekday_expression(date_field='date', monday_is_zero=True):
    if connection.vendor == 'postgresql':
        weekday = Func(
            F(date_field),
            function='EXTRACT',
            template='EXTRACT(DOW FROM %(expressions)s)',
            output_field=IntegerField()
        )
        return ExpressionWrapper((weekday + 6) % 7, output_field=IntegerField()) if monday_is_zero else weekday

    elif connection.vendor == 'sqlite':
        weekday = Func(Value('%w'), F(date_field), function='strftime', output_field=IntegerField())
        return ExpressionWrapper((weekday + 6) % 7, output_field=IntegerField()) if monday_is_zero else weekday

    elif connection.vendor == 'mysql':
        weekday = Func(F(date_field), function='DAYOFWEEK', output_field=IntegerField())
        return ExpressionWrapper((weekday + 5) % 7, output_field=IntegerField()) if monday_is_zero else weekday - 1

    weekday = Func(F(date_field), function='DAYOFWEEK', output_field=IntegerField())
    return weekday


# =============================================================================
# FIXED BUSINESS DAYS EXPRESSION (VALID DJANGO ORM)
# =============================================================================

def get_business_days_expression(start_field='start_date', end_field='end_date'):
    """
    Fully valid Django ORM implementation of business day calculation.
    """

    total_days = get_duration_days(start_field, end_field, inclusive=True)

    full_weeks = ExpressionWrapper(total_days / 7, output_field=IntegerField())
    remainder = ExpressionWrapper(total_days % 7, output_field=IntegerField())

    start_weekday = get_weekday_expression(start_field, monday_is_zero=True)

    # Build arithmetic expressions
    end_weekday = ExpressionWrapper(start_weekday + remainder, output_field=IntegerField())

    # Boolean expressions
    starts_on_weekend = ExpressionWrapper(start_weekday >= 5, output_field=BooleanField())
    ends_on_weekend = ExpressionWrapper(end_weekday > 5, output_field=BooleanField())

    # Weekend days in remainder
    weekend_days = Case(
        When(remainder=0, then=Value(0)),

        # Case 1: Start on weekend
        When(
            starts_on_weekend,
            then=Case(
                When(end_weekday <= 6, then=remainder),
                default=ExpressionWrapper(Value(7) - start_weekday, output_field=IntegerField()),
            )
        ),

        # Case 2: Remainder crosses weekend
        When(
            ends_on_weekend,
            then=ExpressionWrapper(end_weekday - 5, output_field=IntegerField())
        ),

        default=Value(0),
        output_field=IntegerField()
    )

    return ExpressionWrapper(
        (full_weeks * 5) + remainder - weekend_days,
        output_field=IntegerField()
    )


# =============================================================================
# Python Helper Functions
# =============================================================================

def calculate_business_days(start_date, end_date, holidays=None):
    if start_date > end_date:
        return 0

    holidays = holidays or []
    holiday_set = set(holidays)

    current = start_date
    business_days = 0

    while current <= end_date:
        if current.weekday() < 5 and current not in holiday_set:
            business_days += 1
        current += timedelta(days=1)

    return business_days


def calculate_duration_days(start_date, end_date, inclusive=False):
    if start_date > end_date:
        return 0
    delta = (end_date - start_date).days
    return delta + 1 if inclusive else delta


# =============================================================================
# Database Vendor Detection
# =============================================================================

def get_database_vendor():
    return connection.vendor


def is_postgresql():
    return connection.vendor == 'postgresql'


def is_sqlite():
    return connection.vendor == 'sqlite'


def is_mysql():
    return connection.vendor == 'mysql'


# =============================================================================
# Testing Utilities
# =============================================================================

def validate_expression_on_database(expression, test_model, expected_result):
    try:
        result = test_model.objects.annotate(test_value=expression).first().test_value
        return result == expected_result
    except Exception:
        return False


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    'Epoch', 'JulianDay', 'DateDiff',
    'get_duration_days', 'get_weekday_expression', 'get_business_days_expression',
    'calculate_business_days', 'calculate_duration_days',
    'get_database_vendor', 'is_postgresql', 'is_sqlite', 'is_mysql',
    'validate_expression_on_database',
]

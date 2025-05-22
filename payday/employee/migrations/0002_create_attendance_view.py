from django.db import migrations

class Migration(migrations.Migration):

    dependencies = [
        ('employee', '0001_initial'),  # Ensure this matches the latest migration
    ]

    operations = [
        migrations.RunSQL(
            """
            DROP TABLE IF EXISTS employee_attendance;
            CREATE VIEW employee_attendance AS
            SELECT
                ROW_NUMBER() OVER () AS id, -- Generates an incremental ID
                l.sn AS device_id,
                l.enroll_id AS employee_id,
                l.timestamp AS checked_at,
                '{}'::jsonb AS _metadata, -- Default empty JSON
                l.enroll_id AS updated_by, -- Assuming employee ID as updater
                l.enroll_id AS created_by, -- Assuming employee ID as creator
                l.timestamp AS updated_at, -- Using timestamp from Log
                l.timestamp AS created_at  -- Using timestamp from Log
            FROM device_log l;
            """,
            reverse_sql="DROP VIEW IF EXISTS attendance_view;"  # Reverse operation
        )
    ]

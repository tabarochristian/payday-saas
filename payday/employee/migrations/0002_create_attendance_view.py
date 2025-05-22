from django.db import migrations

class Migration(migrations.Migration):

    dependencies = [
        ('device', '0001_initial'),  # Replace with the latest migration name
    ]

    operations = [
        migrations.RunSQL(
            """
            -- Create the view with grouped data
            CREATE VIEW employee_attendance AS
            SELECT
                ROW_NUMBER() OVER () AS id, -- Generates an incremental ID
                d.id AS device_id, -- Fetching the actual device_id from device_device
                l.enroll_id AS employee_id,
                DATE(l.timestamp) AS checked_at, -- Extract only the date part
                COUNT(*) AS count, -- Count occurrences per employee per date
                MIN(l.timestamp) AS first_checked_at, -- Earliest log for the day
                MAX(l.timestamp) AS last_checked_at, -- Latest log for the day
                '{}'::jsonb AS _metadata, -- Default empty JSON
                l.enroll_id AS updated_by_id, -- Assuming employee ID as updater
                l.enroll_id AS created_by_id, -- Assuming employee ID as creator
                MIN(l.timestamp) AS updated_at, -- Using timestamp from Log
                MIN(l.timestamp) AS created_at  -- Using timestamp from Log
            FROM device_log l
            LEFT JOIN device_device d ON l.sn = d.sn -- Mapping `sn` to actual `device_id`
            INNER JOIN employee_employee e ON l.enroll_id = e.registration_number::INTEGER -- Ensure enroll_id exists in employee table
            GROUP BY l.enroll_id, d.id, DATE(l.timestamp);
            """,
            reverse_sql="DROP VIEW IF EXISTS employee_attendance;"  # Revert migration by removing the view
        )
    ]

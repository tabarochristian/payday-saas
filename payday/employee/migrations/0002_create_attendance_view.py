from django.db import migrations, connection

class Migration(migrations.Migration):

    dependencies = [
        ('employee', '0001_initial'),  # Adjust as needed
    ]

    def apply_migration(apps, schema_editor):
        if connection.vendor == 'postgresql':
            schema_editor.execute("DROP VIEW IF EXISTS employee_attendance;")
            schema_editor.execute("""
                CREATE VIEW employee_attendance AS
                WITH RankedLogs AS (
                    SELECT
                        l.enroll_id,
                        l.sn,
                        l.timestamp,
                        ROW_NUMBER() OVER (ORDER BY l.timestamp) AS id
                    FROM device_log l
                )
                SELECT
                    r.id,
                    d.id AS device_id,
                    r.enroll_id AS employee_id,
                    e.sub_organization,
                    DATE(r.timestamp) AS checked_at,
                    COUNT(r.enroll_id) AS count,
                    MIN(r.timestamp) AS first_checked_at,
                    MAX(r.timestamp) AS last_checked_at,
                    '{}'::jsonb AS _metadata,
                    r.enroll_id AS updated_by_id,
                    r.enroll_id AS created_by_id,
                    MIN(r.timestamp) AS updated_at,
                    MIN(r.timestamp) AS created_at
                FROM RankedLogs r
                LEFT JOIN device_device d ON r.sn = d.sn
                INNER JOIN employee_employee e ON r.enroll_id = e.registration_number::INTEGER
                GROUP BY r.id, r.enroll_id, e.sub_organization, d.id, DATE(r.timestamp);
            """)
        else:  # SQLite
            schema_editor.execute("DROP VIEW IF EXISTS employee_attendance;")
            schema_editor.execute("""
                CREATE VIEW employee_attendance AS
                SELECT
                    ROW_NUMBER() OVER (ORDER BY l.timestamp) AS id,
                    d.id AS device_id,
                    l.enroll_id AS employee_id,
                    e.sub_organization,
                    DATE(l.timestamp) AS checked_at,
                    COUNT(l.enroll_id) AS count,
                    MIN(l.timestamp) AS first_checked_at,
                    MAX(l.timestamp) AS last_checked_at,
                    json('{}') AS _metadata,
                    l.enroll_id AS updated_by_id,
                    l.enroll_id AS created_by_id,
                    MIN(l.timestamp) AS updated_at,
                    MIN(l.timestamp) AS created_at
                FROM device_log l
                LEFT JOIN device_device d ON l.sn = d.sn
                INNER JOIN employee_employee e ON l.enroll_id = CAST(e.registration_number AS INTEGER)
                GROUP BY l.enroll_id, e.sub_organization, d.id, DATE(l.timestamp);
            """)

    def reverse_migration(apps, schema_editor):
        schema_editor.execute("DROP VIEW IF EXISTS employee_attendance;")

    operations = [
        migrations.RunPython(apply_migration, reverse_migration)
    ]
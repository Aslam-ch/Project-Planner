from django.db import migrations


def flatten_legacy_baseclass(apps, schema_editor):
    connection = schema_editor.connection
    if connection.vendor != 'mysql':
        return

    tables = set(connection.introspection.table_names())
    if 'projects_baseclass' not in tables:
        return

    required_tables = {
        'projects_project',
        'projects_assignedproject',
        'projects_assignedproject_developers',
    }
    if not required_tables.issubset(tables) or 'projects_task' in tables:
        raise RuntimeError(
            'Unexpected legacy projects schema; refusing to alter it automatically.'
        )

    expected_columns = {
        'projects_project': {'baseclass_ptr_id'},
        'projects_assignedproject': {'baseclass_ptr_id', 'start_data'},
    }
    with connection.cursor() as cursor:
        for table, required in expected_columns.items():
            description = connection.introspection.get_table_description(cursor, table)
            columns = {column.name for column in description}
            if not required.issubset(columns) or 'id' in columns:
                raise RuntimeError(
                    f'Unexpected columns in {table}; refusing to alter it automatically.'
                )

        cursor.execute(
            """
            SELECT COUNT(*)
            FROM projects_baseclass AS base
            LEFT JOIN projects_project AS project
                ON project.baseclass_ptr_id = base.id
            LEFT JOIN projects_assignedproject AS assigned
                ON assigned.baseclass_ptr_id = base.id
            WHERE project.baseclass_ptr_id IS NULL
                AND assigned.baseclass_ptr_id IS NULL
            """
        )
        if cursor.fetchone()[0]:
            raise RuntimeError(
                'Orphan projects_baseclass rows exist; refusing to discard them.'
            )

        cursor.execute(
            """
            SELECT TABLE_NAME
            FROM information_schema.KEY_COLUMN_USAGE
            WHERE TABLE_SCHEMA = DATABASE()
                AND REFERENCED_TABLE_NAME IN (
                    'projects_baseclass',
                    'projects_project',
                    'projects_assignedproject'
                )
                AND TABLE_NAME NOT IN (
                    'projects_project',
                    'projects_assignedproject',
                    'projects_assignedproject_developers'
                )
            """
        )
        external_references = [row[0] for row in cursor.fetchall()]
        if external_references:
            raise RuntimeError(
                'Other tables reference legacy project tables: '
                + ', '.join(sorted(set(external_references)))
            )

        cursor.execute(
            """
            SELECT DISTINCT TABLE_NAME, CONSTRAINT_NAME
            FROM information_schema.KEY_COLUMN_USAGE
            WHERE TABLE_SCHEMA = DATABASE()
                AND TABLE_NAME IN (
                    'projects_project',
                    'projects_assignedproject',
                    'projects_assignedproject_developers'
                )
                AND REFERENCED_TABLE_NAME IN (
                    'projects_baseclass',
                    'projects_project',
                    'projects_assignedproject'
                )
            """
        )
        foreign_keys = cursor.fetchall()
        for table, constraint in foreign_keys:
            cursor.execute(
                f'ALTER TABLE `{table}` DROP FOREIGN KEY `{constraint}`'
            )

        cursor.execute(
            """
            ALTER TABLE projects_project
                ADD COLUMN uuid CHAR(32) NULL,
                ADD COLUMN active_status TINYINT(1) NULL,
                ADD COLUMN created_at DATETIME(6) NULL,
                ADD COLUMN updated_at DATETIME(6) NULL,
                CHANGE COLUMN baseclass_ptr_id id BIGINT NOT NULL AUTO_INCREMENT
            """
        )
        cursor.execute(
            """
            UPDATE projects_project AS project
            JOIN projects_baseclass AS base ON base.id = project.id
            SET project.uuid = base.uuid,
                project.active_status = base.active_status,
                project.created_at = base.created_at,
                project.updated_at = base.updated_at
            """
        )
        cursor.execute(
            """
            ALTER TABLE projects_project
                MODIFY COLUMN uuid CHAR(32) NOT NULL,
                MODIFY COLUMN active_status TINYINT(1) NOT NULL,
                MODIFY COLUMN created_at DATETIME(6) NOT NULL,
                MODIFY COLUMN updated_at DATETIME(6) NOT NULL,
                ADD UNIQUE KEY uuid (uuid)
            """
        )

        cursor.execute(
            """
            ALTER TABLE projects_assignedproject
                ADD COLUMN uuid CHAR(32) NULL,
                ADD COLUMN active_status TINYINT(1) NULL,
                ADD COLUMN created_at DATETIME(6) NULL,
                ADD COLUMN updated_at DATETIME(6) NULL,
                CHANGE COLUMN baseclass_ptr_id id BIGINT NOT NULL AUTO_INCREMENT,
                CHANGE COLUMN start_data start_date DATE NOT NULL
            """
        )
        cursor.execute(
            """
            UPDATE projects_assignedproject AS assigned
            JOIN projects_baseclass AS base ON base.id = assigned.id
            SET assigned.uuid = base.uuid,
                assigned.active_status = base.active_status,
                assigned.created_at = base.created_at,
                assigned.updated_at = base.updated_at
            """
        )
        cursor.execute(
            """
            ALTER TABLE projects_assignedproject
                MODIFY COLUMN uuid CHAR(32) NOT NULL,
                MODIFY COLUMN active_status TINYINT(1) NOT NULL,
                MODIFY COLUMN created_at DATETIME(6) NOT NULL,
                MODIFY COLUMN updated_at DATETIME(6) NOT NULL,
                ADD UNIQUE KEY uuid (uuid)
            """
        )
        cursor.execute(
            """
            ALTER TABLE projects_assignedproject
                ADD CONSTRAINT flat_assignedproject_project_fk
                    FOREIGN KEY (project_id) REFERENCES projects_project (id)
            """
        )
        cursor.execute(
            """
            ALTER TABLE projects_assignedproject_developers
                ADD CONSTRAINT flat_assignedproject_developers_fk
                    FOREIGN KEY (assignedproject_id)
                    REFERENCES projects_assignedproject (id)
            """
        )
        cursor.execute('DROP TABLE projects_baseclass')


class Migration(migrations.Migration):

    atomic = False

    dependencies = [
        ('projects', '0002_assignedproject'),
    ]

    operations = [
        migrations.RunPython(flatten_legacy_baseclass),
    ]

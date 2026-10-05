from django.db import migrations


def create_confectioner_group(apps, schema_editor):
    apps.get_model("auth", "Group").objects.using(schema_editor.connection.alias).get_or_create(name="Confeiteiro")


class Migration(migrations.Migration):

    dependencies = [
        ("auth", "0012_alter_user_first_name_max_length"),
        ("catalog", "0007_order"),
    ]

    operations = [
        migrations.RunPython(create_confectioner_group, migrations.RunPython.noop),
    ]

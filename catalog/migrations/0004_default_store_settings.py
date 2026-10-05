from django.db import migrations


def defaults(apps, schema_editor):
    apps.get_model("catalog", "StoreSettings").objects.using(schema_editor.connection.alias).get_or_create(pk=1, defaults={"delivery_fee": 3, "minimum_order": 0})


class Migration(migrations.Migration):
    dependencies = [("catalog", "0003_storesettings")]
    operations = [migrations.RunPython(defaults, migrations.RunPython.noop)]

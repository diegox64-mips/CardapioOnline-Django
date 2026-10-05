from django.db import migrations, models
import django.db.models.deletion


def create_categories(apps, schema_editor):
    Category = apps.get_model("catalog", "Category")
    Product = apps.get_model("catalog", "Product")
    database = schema_editor.connection.alias
    categories = {"1": "Bolo de pote", "2": "Brownie", "3": "Pudim", "4": "Docinho"}
    existing_codes = set(
        Product.objects.using(database).values_list("category", flat=True).distinct()
    )
    if existing_codes - set(categories):
        raise ValueError("Existem produtos com categorias desconhecidas. Revise antes de continuar.")
    for code, name in categories.items():
        Category.objects.using(database).create(id=int(code), name=name)


class Migration(migrations.Migration):
    dependencies = [("catalog", "0001_initial")]

    operations = [
        migrations.CreateModel(
            name="Category",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=80, unique=True, verbose_name="Nome")),
            ],
            options={
                "ordering": ["name"],
                "verbose_name": "Categoria",
                "verbose_name_plural": "Categorias",
            },
        ),
        migrations.RunPython(create_categories),
        migrations.AlterField(
            model_name="product",
            name="category",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="products",
                to="catalog.category",
                verbose_name="Categoria",
            ),
        ),
    ]

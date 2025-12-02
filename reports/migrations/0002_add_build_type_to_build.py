# reports/migrations/0002_add_build_type_to_build.py
from django.db import migrations, models


def populate_build_type(apps, schema_editor):
    Build = apps.get_model('reports', 'Build')
    for build in Build.objects.all():
        name = build.build_number or ""
        if name.startswith('SMK-MOB-'):
            build.build_type = 'Mobile'
        elif name.startswith('SMK-RUN18-'):
            build.build_type = 'Run18'
        elif name.startswith('SMK-RUN17-'):
            build.build_type = 'Run17'
        elif name.startswith('SMK-INIT18-'):
            build.build_type = 'Init18'
        elif name.startswith('SMK-BNCH-'):
            build.build_type = 'Benchmark'
        else:
            build.build_type = 'Other'
        build.save()


def reverse_populate(apps, schema_editor):
    Build = apps.get_model('reports', 'Build')
    Build.objects.update(build_type='Other')


class Migration(migrations.Migration):

    dependencies = [
        ('reports', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='build',
            name='build_type',
            field=models.CharField(max_length=50, default='Other', db_index=True),
        ),
        migrations.RunPython(populate_build_type, reverse_code=reverse_populate),
    ]
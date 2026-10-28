from django.db import migrations


def seed(apps, schema_editor):
    # Imported lazily: the function is idempotent and uses the current models,
    # which are exactly the state created by 0004/0005.
    from growth.playbooks import seed_top8_playbook

    seed_top8_playbook()


class Migration(migrations.Migration):
    dependencies = [
        ("growth", "0005_alter_boost_platform_alter_hashtagset_platform_and_more"),
    ]

    operations = [
        migrations.RunPython(seed, migrations.RunPython.noop),
    ]

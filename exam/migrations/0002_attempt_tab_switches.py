from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("exam", "0001_initial")]

    operations = [
        migrations.AddField(model_name="attempt", name="tab_switches",
                            field=models.PositiveSmallIntegerField(default=0)),
        migrations.AddField(model_name="attempt", name="auto_submitted",
                            field=models.BooleanField(default=False)),
    ]

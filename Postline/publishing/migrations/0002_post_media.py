from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("publishing", "0001_initial")]

    operations = [
        migrations.AddField(
            model_name="post",
            name="media",
            field=models.FileField(blank=True, upload_to="post-media/"),
        ),
    ]

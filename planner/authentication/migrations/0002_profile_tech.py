from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("authentication", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="profile",
            name="tech",
            field=models.CharField(
                blank=True,
                choices=[
                    ("Backend Developer", "Backend Developer"),
                    ("Frontend Developer", "Frontend Developer"),
                    ("Fullstack Developer", "Fullstack Developer"),
                    ("UI/UX Designer", "UI/UX Designer"),
                    ("Software Tester", "Software Tester"),
                ],
                max_length=30,
            ),
        ),
    ]

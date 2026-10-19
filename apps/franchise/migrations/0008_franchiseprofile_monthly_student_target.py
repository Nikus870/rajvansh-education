from django.core.validators import MinValueValidator
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("franchise", "0007_certificaterequest_revoked_at_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="franchiseprofile",
            name="monthly_student_target",
            field=models.PositiveIntegerField(
                default=20,
                help_text="Monthly new-student registration target for this franchise.",
                validators=[MinValueValidator(1)],
            ),
        ),
    ]

# Generated migration to make user FKs non-nullable

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('recordings', '0003_migrate_data_to_consolidated_models'),
    ]

    operations = [
        # Make RecordingFile.user non-nullable
        migrations.AlterField(
            model_name='recordingfile',
            name='user',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='recording_files',
                to='auth.user'
            ),
        ),
        # Make RecordingAnalysis.user non-nullable
        migrations.AlterField(
            model_name='recordinganalysis',
            name='user',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='recording_analyses',
                to='auth.user'
            ),
        ),
    ]

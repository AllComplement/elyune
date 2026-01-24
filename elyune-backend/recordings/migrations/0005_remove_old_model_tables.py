# Generated migration to remove old models

from django.db import migrations


class Migration(migrations.Migration):
    """
    Remove old model tables that have been consolidated into RecordingAnalysis.
    
    This migration drops:
    - processing_processingjob
    - processing_processingstep  
    - analysis_transcription
    - analysis_transcriptionsegment
    - analysis_aianalysis
    
    All data has been migrated to the new consolidated models in migration 0003.
    """

    dependencies = [
        ('recordings', '0004_make_user_fks_required'),
        # Note: Dependencies on 'processing' and 'analysis' removed after cleanup
    ]

    operations = [
        # Drop old processing models
        migrations.RunSQL(
            sql='DROP TABLE IF EXISTS processing_processingstep CASCADE;',
            reverse_sql='-- Cannot reverse: table dropped'
        ),
        migrations.RunSQL(
            sql='DROP TABLE IF EXISTS processing_processingjob CASCADE;',
            reverse_sql='-- Cannot reverse: table dropped'
        ),
        
        # Drop old analysis models
        migrations.RunSQL(
            sql='DROP TABLE IF EXISTS analysis_transcriptionsegment CASCADE;',
            reverse_sql='-- Cannot reverse: table dropped'
        ),
        migrations.RunSQL(
            sql='DROP TABLE IF EXISTS analysis_aianalysis CASCADE;',
            reverse_sql='-- Cannot reverse: table dropped'
        ),
        migrations.RunSQL(
            sql='DROP TABLE IF EXISTS analysis_transcription CASCADE;',
            reverse_sql='-- Cannot reverse: table dropped'
        ),
    ]

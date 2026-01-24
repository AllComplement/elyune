"""
Management command to backfill duration for existing recordings
Extracts duration from MP4 files that were already converted
"""
from django.core.management.base import BaseCommand
from recordings.models import Recording, RecordingFile
from recordings.tasks import get_s3_client, download_from_s3
from django.conf import settings
import subprocess
import os
import tempfile


class Command(BaseCommand):
    help = 'Backfill duration for recordings that have MP4 files but no duration'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be updated without making changes',
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=None,
            help='Limit number of recordings to process',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        limit = options['limit']

        # Find recordings without duration that have MP4 files
        recordings = Recording.objects.filter(
            duration_seconds__isnull=True,
            files__file_type='converted_mp4'
        ).distinct()

        if limit:
            recordings = recordings[:limit]

        total = recordings.count()
        
        if total == 0:
            self.stdout.write(self.style.WARNING('No recordings need duration backfill'))
            return

        self.stdout.write(f'Found {total} recordings to process')
        
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN - No changes will be made'))

        success_count = 0
        error_count = 0

        for i, recording in enumerate(recordings, 1):
            try:
                self.stdout.write(f'\n[{i}/{total}] Processing {recording.id}...')
                
                # Get MP4 file
                mp4_file = recording.files.get(file_type='converted_mp4')
                self.stdout.write(f'  MP4 S3 key: {mp4_file.s3_key}')
                
                # Download MP4 to temp file
                with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as tmp:
                    tmp_path = tmp.name
                
                try:
                    download_from_s3(mp4_file.s3_key, tmp_path)
                    
                    # Extract duration with ffprobe
                    ffprobe_command = [
                        'ffprobe',
                        '-v', 'error',
                        '-show_entries', 'format=duration',
                        '-of', 'default=noprint_wrappers=1:nokey=1',
                        tmp_path
                    ]
                    
                    result = subprocess.run(
                        ffprobe_command,
                        capture_output=True,
                        text=True,
                        timeout=30
                    )
                    
                    if result.returncode != 0:
                        raise Exception(f"ffprobe failed: {result.stderr}")
                    
                    duration_seconds = float(result.stdout.strip())
                    self.stdout.write(f'  Duration extracted: {duration_seconds:.2f} seconds')
                    
                    if not dry_run:
                        recording.duration_seconds = duration_seconds
                        recording.save(update_fields=['duration_seconds'])
                        self.stdout.write(self.style.SUCCESS(f'  ✓ Updated recording'))
                    else:
                        self.stdout.write(self.style.WARNING(f'  [DRY RUN] Would update to {duration_seconds:.2f}'))
                    
                    success_count += 1
                    
                finally:
                    # Cleanup temp file
                    if os.path.exists(tmp_path):
                        os.remove(tmp_path)
                        
            except Exception as e:
                error_count += 1
                self.stdout.write(self.style.ERROR(f'  ✗ Error: {str(e)}'))

        # Summary
        self.stdout.write('\n' + '='*60)
        self.stdout.write(self.style.SUCCESS(f'Successfully processed: {success_count}'))
        if error_count > 0:
            self.stdout.write(self.style.ERROR(f'Errors: {error_count}'))
        
        if dry_run:
            self.stdout.write(self.style.WARNING('\nDRY RUN complete - no changes made'))
            self.stdout.write('Run without --dry-run to apply changes')

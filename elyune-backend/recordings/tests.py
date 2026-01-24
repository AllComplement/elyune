"""
Tests for recordings API endpoints with query optimization verification
"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.db import connection
from django.test.utils import override_settings
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken
from recordings.models import Recording, RecordingFile, RecordingAnalysis


User = get_user_model()


class RecordingAPIQueryOptimizationTests(TestCase):
    """
    Test query optimization in RecordingViewSet
    
    These tests verify that select_related and prefetch_related are working
    to minimize database queries.
    """
    
    def setUp(self):
        """Create test user, recording with files and analysis"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        # Create recording
        self.recording = Recording.objects.create(
            user=self.user,
            title='Test Recording',
            original_filename='test.webm',
            file_size_bytes=10000000,
            quality='1080p',
            fps=30,
            status='completed',
            processing_progress=100
        )
        
        # Create files
        RecordingFile.objects.create(
            recording=self.recording,
            user=self.user,
            file_type='original_webm',
            s3_key='test/original.webm',
            s3_bucket='media',
            file_size_bytes=1000
        )
        RecordingFile.objects.create(
            recording=self.recording,
            user=self.user,
            file_type='converted_mp4',
            s3_key='test/converted.mp4',
            s3_bucket='media',
            file_size_bytes=2000
        )
        
        # Create analysis with all fields
        RecordingAnalysis.objects.create(
            recording=self.recording,
            user=self.user,
            transcription_text='Test transcript',
            transcription_confidence=0.95,
            transcription_language='en',
            transcription_num_speakers=2,
            transcription_audio_duration=60.0,
            transcription_processing_time=5.0,
            transcription_segments=[
                {
                    'start': 0.0,
                    'end': 5.0,
                    'text': 'Test segment',
                    'confidence': 0.95,
                    'speaker_id': 0,
                    'speaker_label': 'Speaker 1'
                }
            ],
            summary_text='Test summary',
            summary_data={'points': ['point 1']},
            summary_tokens=100,
            summary_processing_time=2.0,
            action_items_text='- Task 1',
            action_items_data={'items': [{'task': 'Task 1'}]},
            action_items_tokens=50,
            key_points_text='- Point 1',
            key_points_data={'points': ['Point 1']},
            key_points_tokens=50,
            sentiment_text='Positive',
            sentiment_data={'sentiment': 'positive'},
            sentiment_tokens=30,
            total_tokens_used=230,
            total_processing_time=7.0
        )
        
        # Setup API client with JWT token
        self.client = APIClient()
        refresh = RefreshToken.for_user(self.user)
        self.access_token = str(refresh.access_token)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.access_token}')
    
    @override_settings(DEBUG=True)
    def test_recording_detail_query_count(self):
        """
        Test that recording detail endpoint uses optimized queries
        
        Expected queries (≤4):
        1. SELECT Recording + RecordingAnalysis (JOIN via select_related)
        2. SELECT RecordingFiles (prefetch_related)
        3. SELECT User (if not cached)
        4. Potentially one more for auth/session
        """
        # Reset query log
        connection.queries_log.clear()
        
        # Make API request
        response = self.client.get(f'/api/v1/recordings/{self.recording.id}/')
        
        # Check response
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['id'], str(self.recording.id))
        self.assertIn('analysis', response.data)
        self.assertIn('files', response.data)
        
        # Check query count
        query_count = len(connection.queries)
        print(f"\n✓ Queries executed: {query_count}")
        for i, query in enumerate(connection.queries, 1):
            print(f"  {i}. {query['sql'][:100]}...")
        
        # Should be ≤4 queries (ideally 3, but allow for auth overhead)
        self.assertLessEqual(
            query_count, 
            4,
            f"Expected ≤4 queries, got {query_count}. Queries:\n" +
            "\n".join(f"{i}. {q['sql'][:200]}" for i, q in enumerate(connection.queries, 1))
        )
    
    @override_settings(DEBUG=True)
    def test_recording_list_query_count(self):
        """
        Test that recording list endpoint uses optimized queries
        
        With N recordings, should use ~2-3 queries regardless of N.
        """
        # Create 2 more recordings
        for i in range(2):
            rec = Recording.objects.create(
                user=self.user,
                title=f'Recording {i+2}',
                original_filename=f'test{i+2}.webm',
                file_size_bytes=5000000,
                status='completed',
                processing_progress=100
            )
            RecordingFile.objects.create(
                recording=rec,
                user=self.user,
                file_type='original_webm',
                s3_key=f'test{i+2}/original.webm',
                s3_bucket='media',
                file_size_bytes=1000
            )
        
        # Reset query log
        connection.queries_log.clear()
        
        # Make API request
        response = self.client.get('/api/v1/recordings/')
        
        # Check response
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['count'], 3)
        
        # Check query count
        query_count = len(connection.queries)
        print(f"\n✓ List queries executed: {query_count}")
        for i, query in enumerate(connection.queries, 1):
            print(f"  {i}. {query['sql'][:100]}...")
        
        # Should be ≤4 queries for list (count + pagination + auth)
        self.assertLessEqual(
            query_count,
            4,
            f"Expected ≤4 queries for list, got {query_count}"
        )
    
    def test_recording_detail_response_structure(self):
        """Test that API response includes all expected nested data"""
        response = self.client.get(f'/api/v1/recordings/{self.recording.id}/')
        
        self.assertEqual(response.status_code, 200)
        data = response.data
        
        # Check main recording fields
        self.assertEqual(data['id'], str(self.recording.id))
        self.assertEqual(data['title'], 'Test Recording')
        self.assertEqual(data['status'], 'completed')
        self.assertEqual(data['processing_progress'], 100)
        
        # Check files nested
        self.assertIn('files', data)
        self.assertEqual(len(data['files']), 2)
        self.assertEqual(data['files'][0]['file_type'], 'original_webm')
        
        # Check analysis nested
        self.assertIn('analysis', data)
        analysis = data['analysis']
        self.assertEqual(analysis['transcription_text'], 'Test transcript')
        self.assertEqual(analysis['transcription_confidence'], 0.95)
        self.assertEqual(analysis['summary_text'], 'Test summary')
        self.assertEqual(analysis['action_items_text'], '- Task 1')
        self.assertEqual(analysis['key_points_text'], '- Point 1')
        self.assertEqual(analysis['sentiment_text'], 'Positive')
        self.assertEqual(analysis['total_tokens_used'], 230)
        
        # Check segments as JSON array
        self.assertIn('transcription_segments', analysis)
        self.assertEqual(len(analysis['transcription_segments']), 1)
        self.assertEqual(analysis['transcription_segments'][0]['text'], 'Test segment')
    
    def test_recording_without_analysis(self):
        """Test recording that doesn't have analysis yet"""
        # Create recording without analysis
        recording_no_analysis = Recording.objects.create(
            user=self.user,
            title='Recording Without Analysis',
            original_filename='test2.webm',
            file_size_bytes=3000000,
            status='processing',
            processing_progress=50
        )
        
        response = self.client.get(f'/api/v1/recordings/{recording_no_analysis.id}/')
        
        self.assertEqual(response.status_code, 200)
        # Analysis should be null
        self.assertIsNone(response.data['analysis'])

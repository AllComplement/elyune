from django.test import TestCase
from unittest.mock import patch, MagicMock, call
from django.contrib.auth import get_user_model
from django.utils import timezone
from recordings.models import Recording, RecordingFile, RecordingAnalysis
from recordings.tasks import (
    generate_and_save_summary,
    generate_and_save_action_items,
    generate_and_save_key_points,
    generate_and_save_sentiment,
    finalize_parallel_analysis,
    analyze_transcription,
)
import uuid

User = get_user_model()


class ParallelAnalysisSubTaskTests(TestCase):
    """Test individual parallel AI analysis sub-tasks"""
    
    def setUp(self):
        """Create test user, recording, and analysis"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.recording = Recording.objects.create(
            user=self.user,
            original_filename='test.webm',
            status='uploaded',
            file_size_bytes=1000000,
            quality='1080p',
            fps=30
        )
        
        # Create RecordingAnalysis with transcription data
        self.analysis = RecordingAnalysis.objects.create(
            recording=self.recording,
            user=self.user,
            transcription_text='This is a test transcription.',
            transcription_confidence=0.95,
            transcription_audio_duration=10.0,
            transcription_processing_time=1.5,
            transcription_num_speakers=1,
            transcription_segments=[{
                'start': 0.0,
                'end': 5.0,
                'text': 'This is a test.',
                'confidence': 0.95,
                'speaker_id': 1,
                'speaker_label': 'Speaker 1'
            }]
        )
    
    @patch('google.generativeai.GenerativeModel')
    def test_generate_and_save_summary_success(self, mock_genai_model):
        """Test successful summary generation"""
        # Mock Gemini API response
        mock_model = MagicMock()
        mock_response = MagicMock()
        mock_response.text = 'This is a test summary.'
        mock_response.usage_metadata.total_token_count = 50
        mock_model.generate_content.return_value = mock_response
        mock_genai_model.return_value = mock_model
        
        # Execute task
        result = generate_and_save_summary(
            str(self.recording.id),
            'Test transcript',
            'gemini-2.5-flash'
        )
        
        # Verify result
        self.assertEqual(result['status'], 'success')
        self.assertEqual(result['type'], 'summary')
        self.assertIn('time', result)
        
        # Verify database record updated
        self.analysis.refresh_from_db()
        self.assertEqual(self.analysis.summary_text, 'This is a test summary.')
        self.assertEqual(self.analysis.summary_model_version, 'gemini-2.5-flash')
        self.assertEqual(self.analysis.summary_tokens, 50)
    
    @patch('google.generativeai.GenerativeModel')
    def test_generate_and_save_summary_idempotent(self, mock_genai_model):
        """Test that running summary task twice updates instead of creating duplicate"""
        # Mock Gemini API
        mock_model = MagicMock()
        mock_response = MagicMock()
        mock_response.text = 'First summary.'
        mock_response.usage_metadata.total_token_count = 50
        mock_model.generate_content.return_value = mock_response
        mock_genai_model.return_value = mock_model
        
        # Run first time
        generate_and_save_summary(
            str(self.recording.id),
            'Test transcript',
            'gemini-2.5-flash'
        )
        
        # Verify summary text set
        self.analysis.refresh_from_db()
        self.assertEqual(self.analysis.summary_text, 'First summary.')
        
        # Update mock response
        mock_response.text = 'Updated summary.'
        
        # Run second time
        generate_and_save_summary(
            str(self.recording.id),
            'Test transcript',
            'gemini-2.5-flash'
        )
        
        # Verify record updated (not duplicated)
        self.analysis.refresh_from_db()
        self.assertEqual(self.analysis.summary_text, 'Updated summary.')
        # Verify only one RecordingAnalysis exists
        self.assertEqual(RecordingAnalysis.objects.filter(recording=self.recording).count(), 1)
    
    @patch('random.uniform')
    @patch('time.sleep')
    @patch('google.generativeai.GenerativeModel')
    def test_generate_and_save_summary_rate_limit(self, mock_genai_model, mock_sleep, mock_random):
        """Test rate limit handling with exponential backoff"""
        # Mock rate limit error
        mock_genai_model.side_effect = Exception('429 rate limit exceeded')
        mock_random.return_value = 0.5  # Fixed random value for testing
        
        # Execute task - should raise an exception (either Retry or the original)
        # The Celery retry mechanism will raise, so we catch any exception
        with self.assertRaises(Exception) as context:
            generate_and_save_summary(
                str(self.recording.id),
                'Test transcript',
                'gemini-2.5-flash'
            )
        
        # Verify sleep was called with exponential backoff
        # This confirms the rate limit handling code path was executed
        self.assertTrue(mock_sleep.called)
        sleep_time = mock_sleep.call_args[0][0]
        self.assertGreater(sleep_time, 0)
        self.assertLessEqual(sleep_time, 60)  # Max 60 seconds
    
    @patch('google.generativeai.GenerativeModel')
    def test_generate_and_save_action_items_success(self, mock_genai_model):
        """Test action items extraction"""
        mock_model = MagicMock()
        mock_response = MagicMock()
        mock_response.text = '1. Task one\n2. Task two'
        mock_response.usage_metadata.total_token_count = 40
        mock_model.generate_content.return_value = mock_response
        mock_genai_model.return_value = mock_model
        
        result = generate_and_save_action_items(
            str(self.recording.id),
            'Test transcript',
            'gemini-2.5-flash'
        )
        
        self.assertEqual(result['status'], 'success')
        self.assertEqual(result['type'], 'action_items')
        
        self.analysis.refresh_from_db()
        self.assertIn('Task one', self.analysis.action_items_text)
    
    @patch('google.generativeai.GenerativeModel')
    def test_generate_and_save_key_points_success(self, mock_genai_model):
        """Test key points extraction"""
        mock_model = MagicMock()
        mock_response = MagicMock()
        mock_response.text = '- Point 1\n- Point 2'
        mock_response.usage_metadata.total_token_count = 35
        mock_model.generate_content.return_value = mock_response
        mock_genai_model.return_value = mock_model
        
        result = generate_and_save_key_points(
            str(self.recording.id),
            'Test transcript',
            'gemini-2.5-flash'
        )
        
        self.assertEqual(result['status'], 'success')
        self.assertEqual(result['type'], 'key_points')
        
        self.analysis.refresh_from_db()
        self.assertIn('Point 1', self.analysis.key_points_text)
    
    @patch('google.generativeai.GenerativeModel')
    def test_generate_and_save_sentiment_success(self, mock_genai_model):
        """Test sentiment analysis"""
        mock_model = MagicMock()
        mock_response = MagicMock()
        mock_response.text = 'Overall sentiment: Positive'
        mock_response.usage_metadata.total_token_count = 30
        mock_model.generate_content.return_value = mock_response
        mock_genai_model.return_value = mock_model
        
        result = generate_and_save_sentiment(
            str(self.recording.id),
            'Test transcript',
            'gemini-2.5-flash'
        )
        
        self.assertEqual(result['status'], 'success')
        self.assertEqual(result['type'], 'sentiment')
        
        self.analysis.refresh_from_db()
        self.assertIn('Positive', self.analysis.sentiment_text)


class FinalizeParallelAnalysisTests(TestCase):
    """Test the finalization callback for parallel analysis"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.recording = Recording.objects.create(
            user=self.user,
            original_filename='test.webm',
            status='processing',
            file_size_bytes=1000000,
            quality='1080p',
            fps=30
        )
        
        # Create RecordingAnalysis
        self.analysis = RecordingAnalysis.objects.create(
            recording=self.recording,
            user=self.user,
            transcription_text='Test transcription'
        )
    
    def test_finalize_all_success(self):
        """Test finalization when all 4 analyses succeed"""
        results = [
            {'type': 'summary', 'status': 'success', 'time': 5.0},
            {'type': 'action_items', 'status': 'success', 'time': 7.0},
            {'type': 'key_points', 'status': 'success', 'time': 6.0},
            {'type': 'sentiment', 'status': 'success', 'time': 8.0},
        ]
        
        finalize_parallel_analysis(results, str(self.recording.id))
        
        # Refresh from database
        self.recording.refresh_from_db()
        
        # Verify recording completed
        self.assertEqual(self.recording.status, 'completed')
        self.assertIsNotNone(self.recording.completed_at)
        self.assertEqual(self.recording.processing_progress, 100)
    
    def test_finalize_partial_failure(self):
        """Test finalization when 1-3 analyses fail"""
        results = [
            {'type': 'summary', 'status': 'success', 'time': 5.0},
            {'type': 'action_items', 'status': 'failed', 'error': 'API error'},
            {'type': 'key_points', 'status': 'success', 'time': 6.0},
            {'type': 'sentiment', 'status': 'success', 'time': 8.0},
        ]
        
        finalize_parallel_analysis(results, str(self.recording.id))
        
        self.recording.refresh_from_db()
        
        # Still mark as completed with warning
        self.assertEqual(self.recording.status, 'completed')
        self.assertIn('1/4 analyses failed', self.recording.error_message)
        self.assertIn('action_items', self.recording.error_message)
    
    def test_finalize_all_failed(self):
        """Test finalization when all 4 analyses fail"""
        results = [
            {'type': 'summary', 'status': 'failed', 'error': 'Error 1'},
            {'type': 'action_items', 'status': 'failed', 'error': 'Error 2'},
            {'type': 'key_points', 'status': 'failed', 'error': 'Error 3'},
            {'type': 'sentiment', 'status': 'failed', 'error': 'Error 4'},
        ]
        
        finalize_parallel_analysis(results, str(self.recording.id))
        
        self.recording.refresh_from_db()
        
        # Mark as failed
        self.assertEqual(self.recording.status, 'failed')
        self.assertIn('All AI analyses failed', self.recording.error_message)


class AnalyzeTranscriptionOrchestrationTests(TestCase):
    """Test the main orchestration task"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        self.recording = Recording.objects.create(
            user=self.user,
            original_filename='test.webm',
            status='uploaded',
            file_size_bytes=1000000,
            quality='1080p',
            fps=30
        )
        
        # Create RecordingAnalysis with transcription
        self.analysis = RecordingAnalysis.objects.create(
            recording=self.recording,
            user=self.user,
            transcription_text='Test transcription',
            transcription_confidence=0.95,
            transcription_audio_duration=10.0,
            transcription_processing_time=1.5,
            transcription_num_speakers=1,
            transcription_segments=[{
                'start': 0.0,
                'end': 5.0,
                'text': 'Test.',
                'confidence': 0.95,
                'speaker_id': 1,
                'speaker_label': 'Speaker 1'
            }]
        )
    
    @patch('recordings.tasks.chord')
    @patch('google.generativeai.GenerativeModel')
    def test_analyze_transcription_launches_parallel_tasks(self, mock_genai_model, mock_chord):
        """Test that analyze_transcription launches 4 parallel tasks"""
        # Mock Gemini model test
        mock_model = MagicMock()
        mock_model.generate_content.return_value = MagicMock()
        mock_genai_model.return_value = mock_model
        
        # Mock chord
        mock_workflow = MagicMock()
        mock_chord.return_value = mock_workflow
        
        # Execute orchestration task
        analyze_transcription(str(self.recording.id))
        
        # Verify chord was called (parallel execution)
        self.assertTrue(mock_chord.called)
        
        # Verify recording progress updated
        self.recording.refresh_from_db()
        self.assertEqual(self.recording.processing_progress, 80)
    
    @patch('google.generativeai.GenerativeModel')
    def test_analyze_transcription_missing_api_key(self, mock_genai_model):
        """Test failure when Gemini API key is not configured"""
        with patch('recordings.tasks.settings.GEMINI_API_KEY', None):
            with self.assertRaises(Exception) as context:
                analyze_transcription(str(self.recording.id))
            
            self.assertIn('GEMINI_API_KEY not configured', str(context.exception))

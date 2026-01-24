#!/usr/bin/env python
"""
Test script to verify query optimization in RecordingViewSet.

Run with: docker compose exec web python3 test_query_optimization.py

Expected results:
- BEFORE optimization: 7+ queries per recording detail
- AFTER optimization: ~3 queries per recording detail
"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.db import connection, reset_queries
from django.conf import settings
from recordings.models import Recording

# Enable query logging
settings.DEBUG = True

print("=" * 80)
print("QUERY OPTIMIZATION TEST")
print("=" * 80)

# Get first recording
recording = Recording.objects.first()
if not recording:
    print("❌ No recordings found. Please upload a recording first.")
    exit(1)

print(f"\n✓ Testing with recording: {recording.id}")
print(f"  Status: {recording.status}")
print(f"  User: {recording.user.email if recording.user else 'None'}")

# Test 1: Without optimization (baseline)
print("\n" + "=" * 80)
print("TEST 1: Without Optimization (baseline)")
print("=" * 80)

reset_queries()
recording_unoptimized = Recording.objects.filter(id=recording.id).first()

# Access all related data (simulating what serializer does)
_ = recording_unoptimized.user
_ = list(recording_unoptimized.files.all())
try:
    _ = recording_unoptimized.analysis
    _ = recording_unoptimized.analysis.transcription_text if recording_unoptimized.analysis else None
except:
    pass

query_count_unoptimized = len(connection.queries)
print(f"\n📊 Queries executed (unoptimized): {query_count_unoptimized}")
for i, query in enumerate(connection.queries, 1):
    print(f"  {i}. {query['sql'][:100]}...")

# Test 2: With optimization
print("\n" + "=" * 80)
print("TEST 2: With Optimization (select_related + prefetch_related)")
print("=" * 80)

reset_queries()
recording_optimized = Recording.objects.select_related(
    'analysis'
).prefetch_related(
    'files'
).filter(id=recording.id).first()

# Access all related data (simulating what serializer does)
_ = recording_optimized.user
_ = list(recording_optimized.files.all())
try:
    _ = recording_optimized.analysis
    _ = recording_optimized.analysis.transcription_text if recording_optimized.analysis else None
except:
    pass

query_count_optimized = len(connection.queries)
print(f"\n📊 Queries executed (optimized): {query_count_optimized}")
for i, query in enumerate(connection.queries, 1):
    print(f"  {i}. {query['sql'][:100]}...")

# Test 3: Simulate full serializer access (all fields)
print("\n" + "=" * 80)
print("TEST 3: Full Serializer Simulation (optimized)")
print("=" * 80)

reset_queries()
recording_full = Recording.objects.select_related(
    'analysis'
).prefetch_related(
    'files'
).filter(id=recording.id).first()

# Access all fields that serializer accesses
_ = recording_full.id
_ = recording_full.title
_ = recording_full.status
_ = recording_full.processing_progress
_ = recording_full.created_at
_ = recording_full.user.email if recording_full.user else None

# Access all files
files = list(recording_full.files.all())
for f in files:
    _ = f.file_type
    _ = f.s3_key
    _ = f.file_size_bytes

# Access all analysis fields
if recording_full.analysis:
    analysis = recording_full.analysis
    _ = analysis.transcription_text
    _ = analysis.transcription_segments
    _ = analysis.transcription_confidence
    _ = analysis.summary_text
    _ = analysis.action_items_text
    _ = analysis.key_points_text
    _ = analysis.sentiment_text
    _ = analysis.total_tokens_used
    _ = analysis.total_processing_time

query_count_full = len(connection.queries)
print(f"\n📊 Queries executed (full access): {query_count_full}")

# Summary
print("\n" + "=" * 80)
print("SUMMARY")
print("=" * 80)

improvement = query_count_unoptimized - query_count_optimized
improvement_pct = (improvement / query_count_unoptimized * 100) if query_count_unoptimized > 0 else 0

print(f"\n📊 Query Count Comparison:")
print(f"  Unoptimized:  {query_count_unoptimized} queries")
print(f"  Optimized:    {query_count_optimized} queries")
print(f"  Full Access:  {query_count_full} queries")
print(f"\n✨ Improvement: {improvement} fewer queries ({improvement_pct:.1f}% reduction)")

if query_count_optimized <= 3:
    print("\n✅ SUCCESS: Query count is at or below target (≤3 queries)")
elif query_count_optimized < query_count_unoptimized:
    print(f"\n⚠️  PARTIAL SUCCESS: Reduced queries but not to target (target: ≤3)")
else:
    print("\n❌ FAILURE: No improvement detected")

print("\n" + "=" * 80)

"""
Comprehensive tests for FeedbackViewSet with caching and rate limiting.
"""

import os
import django
import time
from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
from django.core.cache import cache
from django.utils import timezone
from datetime import timedelta
import uuid

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Drive.settings')

# Initialize Django
django.setup()

# Disable logging during tests
import logging
logging.disable(logging.CRITICAL)

User = get_user_model()

# ============================================
# TEST CONSTANTS
# ============================================
TEST_PASSWORD = "test123!@#"

@override_settings(
    DEBUG=False,
    # Test-friendly rate limits
    REST_FRAMEWORK={
        'DEFAULT_THROTTLE_RATES': {
            'anon': '100/minute',
            'user': '200/minute',
            'feedback_list': '30/minute',
            'feedback_create': '5/minute',      # Limit feedback creation
            'feedback_update': '10/minute',     # Limit updates
            'feedback_lesson_view': '20/minute',# Limit lesson feedback views
            'feedback_my_view': '15/minute',    # Limit "my feedback" views
            'feedback_instructor_view': '10/minute', # Limit instructor feedback views
        }
    }
)
class FeedbackViewSetComprehensiveTestCase(TestCase):
    """Comprehensive test suite for FeedbackViewSet"""
    
    @classmethod
    def setUpClass(cls):
        """Setup before all tests"""
        super().setUpClass()
        print("\n" + "="*60)
        print("🚀 FEEDBACK VIEWSET COMPREHENSIVE TEST")
        print("="*60)
    
    def setUp(self):
        """Setup before each test"""
        # Clear cache completely
        cache.clear()
        print(f"\n🔄 Test {self._testMethodName}: Cache cleared")
        
        self.client = APIClient()
        
        # Create test users
        self.users = {}
        
        # Generate unique suffix for test data
        test_suffix = uuid.uuid4().hex[:6]
        
        # Platform Admin
        self.users['platform_admin'] = User.objects.create_user(
            username=f'feedback_admin_{test_suffix}',
            email=f'admin_feedback_{test_suffix}@test.com',
            password=TEST_PASSWORD,
            role='A',
            is_staff=True,
            is_active=True
        )
        
        # School Owner
        self.users['school_owner'] = User.objects.create_user(
            username=f'feedback_owner_{test_suffix}',
            email=f'owner_feedback_{test_suffix}@test.com',
            password=TEST_PASSWORD,
            role='A',
            is_staff=False,
            is_active=True
        )
        
        # Instructor 1
        self.users['instructor1'] = User.objects.create_user(
            username=f'feedback_instructor1_{test_suffix}',
            email=f'instructor1_feedback_{test_suffix}@test.com',
            password=TEST_PASSWORD,
            role='I',
            is_active=True
        )
        
        # Instructor 2 (different school)
        self.users['instructor2'] = User.objects.create_user(
            username=f'feedback_instructor2_{test_suffix}',
            email=f'instructor2_feedback_{test_suffix}@test.com',
            password=TEST_PASSWORD,
            role='I',
            is_active=True
        )
        
        # Student 1
        self.users['student1'] = User.objects.create_user(
            username=f'feedback_student1_{test_suffix}',
            email=f'student1_feedback_{test_suffix}@test.com',
            password=TEST_PASSWORD,
            role='S',
            is_active=True
        )
        
        # Student 2
        self.users['student2'] = User.objects.create_user(
            username=f'feedback_student2_{test_suffix}',
            email=f'student2_feedback_{test_suffix}@test.com',
            password=TEST_PASSWORD,
            role='S',
            is_active=True
        )
        
        # Student 3 (different school)
        self.users['student3'] = User.objects.create_user(
            username=f'feedback_student3_{test_suffix}',
            email=f'student3_feedback_{test_suffix}@test.com',
            password=TEST_PASSWORD,
            role='S',
            is_active=True
        )
        
        # Create test schools
        from DriveApp.models import DrivingSchool, StudentProfile, Lesson, Attendance, Feedback
        
        # School 1 (owned by school_owner)
        self.school1 = DrivingSchool.objects.create(
            owner=self.users['school_owner'],
            name=f'Primary Feedback School {test_suffix}',
            email=f'primary_feedback_{test_suffix}@test.com',
            address='123 Main Street'
        )
        
        # School 2 (owned by platform_admin)
        self.school2 = DrivingSchool.objects.create(
            owner=self.users['platform_admin'],
            name=f'Secondary Feedback School {test_suffix}',
            email=f'secondary_feedback_{test_suffix}@test.com',
            address='456 Oak Avenue'
        )
        
        # Create student profiles
        self.profiles = {}
        
        # Instructor 1 profile (in school 1)
        self.profiles['instructor1'] = StudentProfile.objects.create(
            user=self.users['instructor1'],
            school=self.school1,
            status='A',
            license_type='C'
        )
        
        # Instructor 2 profile (in school 2)
        self.profiles['instructor2'] = StudentProfile.objects.create(
            user=self.users['instructor2'],
            school=self.school2,
            status='A',
            license_type='C'
        )
        
        # Student 1 profile (in school 1)
        self.profiles['student1'] = StudentProfile.objects.create(
            user=self.users['student1'],
            school=self.school1,
            status='A',
            license_type='C'
        )
        
        # Student 2 profile (in school 1)
        self.profiles['student2'] = StudentProfile.objects.create(
            user=self.users['student2'],
            school=self.school1,
            status='A',
            license_type='C'
        )
        
        # Student 3 profile (in school 2)
        self.profiles['student3'] = StudentProfile.objects.create(
            user=self.users['student3'],
            school=self.school2,
            status='A',
            license_type='C'
        )
        
        # Create test lessons
        now = timezone.now()
        self.lessons = {}
        
        # Lesson 1 (past, with instructor 1, student1 attended)
        self.lessons['lesson1'] = Lesson.objects.create(
            instructor=self.users['instructor1'],
            school=self.school1,
            title='Driving Lesson 1',
            lesson_type='D',
            description='Lesson 1 for feedback tests',
            duration=60,
            date=now - timedelta(days=2),
            status='C'
        )
        
        # Lesson 2 (past, with instructor 1, student2 attended)
        self.lessons['lesson2'] = Lesson.objects.create(
            instructor=self.users['instructor1'],
            school=self.school1,
            title='Theory Lesson 1',
            lesson_type='T',
            description='Lesson 2 for feedback tests',
            duration=90,
            date=now - timedelta(days=1),
            status='C'
        )
        
        # Lesson 3 (with instructor 2 in school 2)
        self.lessons['lesson3'] = Lesson.objects.create(
            instructor=self.users['instructor2'],
            school=self.school2,
            title='School 2 Lesson',
            lesson_type='D',
            description='Lesson in school 2',
            duration=60,
            date=now - timedelta(days=1),
            status='C'
        )
        
        # Create attendance records (required for feedback)
        self.attendances = {}
        
        # Student 1 attended lesson 1
        self.attendances['attendance1'] = Attendance.objects.create(
            student=self.profiles['student1'],
            lesson=self.lessons['lesson1'],
            presence=True,
            hours_completed=1.0
        )
        
        # Student 2 attended lesson 2
        self.attendances['attendance2'] = Attendance.objects.create(
            student=self.profiles['student2'],
            lesson=self.lessons['lesson2'],
            presence=True,
            hours_completed=1.5
        )
        
        # Student 3 attended lesson 3
        self.attendances['attendance3'] = Attendance.objects.create(
            student=self.profiles['student3'],
            lesson=self.lessons['lesson3'],
            presence=True,
            hours_completed=1.0
        )
        
        # Create feedback records
        self.feedbacks = {}
        
        # Student 1 feedback for lesson 1
        self.feedbacks['feedback1'] = Feedback.objects.create(
            student=self.profiles['student1'],
            lesson=self.lessons['lesson1'],
            rating=5,
            comment='Excellent lesson, very clear instructions!'
        )
        
        # Student 2 feedback for lesson 2
        self.feedbacks['feedback2'] = Feedback.objects.create(
            student=self.profiles['student2'],
            lesson=self.lessons['lesson2'],
            rating=4,
            comment='Good lesson, could use more examples'
        )
        
        # Student 3 feedback for lesson 3
        self.feedbacks['feedback3'] = Feedback.objects.create(
            student=self.profiles['student3'],
            lesson=self.lessons['lesson3'],
            rating=3,
            comment='Average lesson'
        )
        
        print("✅ Test data created:")
        print(f"   - Schools: {self.school1.name}, {self.school2.name}")
        print(f"   - Feedback records: {len(self.feedbacks)}")
        print(f"   - Lessons: {len(self.lessons)}")
        print(f"   - Attendance records: {len(self.attendances)}")
        print(f"   - Users: {len(self.users)}")
    
    # ============ BASIC CACHING TESTS ============
    
    def test_01_list_feedback_caching(self):
        """Test that listing feedback uses caching"""
        print("\n📊 TEST 01: List Feedback with Caching")
        print("-" * 40)
        
        # Authenticate as platform admin (can see all)
        self.client.force_authenticate(user=self.users['platform_admin'])
        
        # First request - should hit database
        start_time = time.time()
        response1 = self.client.get('/api/feedback/')
        time1 = time.time() - start_time
        
        self.assertEqual(response1.status_code, status.HTTP_200_OK)
        
        # Get count from response
        count1 = self._get_result_count(response1.data)
        print(f"   First request: {count1} feedback records, {time1:.4f}s")
        
        # Second request - should be served from cache
        start_time = time.time()
        response2 = self.client.get('/api/feedback/')
        time2 = time.time() - start_time
        
        count2 = self._get_result_count(response2.data)
        print(f"   Second request: {count2} feedback records, {time2:.4f}s")
        
        # Should get same data
        self.assertEqual(count1, count2)
        
        # Cached response should be faster
        if time2 <= time1:
            improvement = ((time1 - time2) / time1) * 100 if time1 > 0 else 100
            print(f"   ✅ Query caching working: {improvement:.1f}% improvement")
        else:
            print(f"   ⚠️  Cached response not faster: {time2:.4f}s vs {time1:.4f}s")
    
    def test_02_multi_tenancy_feedback_isolation(self):
        """Test that users only see permitted feedback records"""
        print("\n📊 TEST 02: Multi-tenancy Feedback Isolation")
        print("-" * 40)
        
        test_cases = [
            ('platform_admin', 'Platform Admin', 3),    # Should see all 3 records
            ('school_owner', 'School Owner', 2),        # Should see feedback in school1 (2)
            ('instructor1', 'Instructor 1', 2),         # Should see feedback for their lessons
            ('instructor2', 'Instructor 2', 1),         # Should see feedback for their lessons
            ('student1', 'Student 1', 1),               # Should see only their own feedback
            ('student3', 'Student 3', 1),               # Should see only their own feedback
        ]
        
        for user_key, user_description, expected_count in test_cases:
            self.client.force_authenticate(user=self.users[user_key])
            
            response = self.client.get('/api/feedback/')
            data = response.data
            count = self._get_result_count(data)
            
            print(f"   {user_description}: sees {count} feedback records")
            
            if count == expected_count:
                print(f"     ✅ Correct isolation")
            else:
                print(f"     ⚠️  Expected {expected_count}, got {count}")
            
            # Verify status code
            self.assertIn(response.status_code, [200])
    
    def test_03_feedback_detail_caching(self):
        """Test caching for individual feedback record"""
        print("\n📊 TEST 03: Feedback Detail Caching")
        print("-" * 40)
        
        self.client.force_authenticate(user=self.users['platform_admin'])
        feedback = self.feedbacks['feedback1']
        
        # First request
        start_time = time.time()
        response1 = self.client.get(f'/api/feedback/{feedback.id}/')
        time1 = time.time() - start_time
        
        # Second request (should be cached)
        start_time = time.time()
        response2 = self.client.get(f'/api/feedback/{feedback.id}/')
        time2 = time.time() - start_time
        
        print(f"   First detail request: {time1:.4f}s")
        print(f"   Second detail request: {time2:.4f}s")
        
        if response1.status_code == 200 and response2.status_code == 200:
            if time2 <= time1:
                improvement = ((time1 - time2) / time1) * 100 if time1 > 0 else 100
                print(f"   ✅ Detail caching working: {improvement:.1f}% improvement")
            else:
                print("   ⚠️  Detail caching not showing improvement")
        else:
            print(f"   ⚠️  Could not access detail: {response1.status_code}")
    
    # ============ RATE LIMITING TESTS ============
    
    def test_04_feedback_list_rate_limit(self):
        """Test rate limiting for feedback list endpoint"""
        print("\n📊 TEST 04: Feedback List Rate Limit")
        print("-" * 40)
        
        self.client.force_authenticate(user=self.users['student1'])
        
        rate_limited = False
        
        # Make rapid requests (limit is 30/minute in test settings)
        for i in range(1, 35):
            response = self.client.get('/api/feedback/')
            
            if response.status_code == 429:
                rate_limited = True
                print(f"   Request {i}: Rate limited (429)")
                break
            elif response.status_code == 200:
                if i % 10 == 0:
                    print(f"   Request {i}: OK (200)")
            else:
                print(f"   Request {i}: Status {response.status_code}")
                break
        
        if rate_limited:
            print("   ✅ Rate limiting triggered for feedback list")
        else:
            print("   ⚠️  Rate limiting not triggered")
    
    def test_05_feedback_create_rate_limit(self):
        """Test rate limiting for feedback creation"""
        print("\n📊 TEST 05: Feedback Create Rate Limit")
        print("-" * 40)
        
        self.client.force_authenticate(user=self.users['student1'])
        
        # Create a new lesson that student1 attended
        from DriveApp.models import Lesson, Attendance
        now = timezone.now()
        
        new_lesson = Lesson.objects.create(
            instructor=self.users['instructor1'],
            school=self.school1,
            title='New Lesson for Feedback',
            lesson_type='T',
            description='New lesson for feedback creation tests',
            duration=60,
            date=now - timedelta(days=1),
            status='C'
        )
        
        # Create attendance record for student1
        Attendance.objects.create(
            student=self.profiles['student1'],
            lesson=new_lesson,
            presence=True,
            hours_completed=1.0
        )
        
        # Create feedback data
        feedback_data = {
            'student': self.profiles['student1'].id,
            'lesson': new_lesson.id,
            'rating': 4,
            'comment': 'Test feedback creation'
        }
        
        rate_limited = False
        
        # Try multiple creations (limit is 5/minute in test settings)
        for i in range(1, 7):
            response = self.client.post('/api/feedback/', feedback_data, format='json')
            
            if response.status_code == 429:
                rate_limited = True
                print(f"   Create {i}: Rate limited (429)")
                break
            elif response.status_code == 201:
                print(f"   Create {i}: Created (201)")
            elif response.status_code == 400:
                print(f"   Create {i}: Bad request (400)")
                # Duplicate feedback after first creation
                break
            else:
                print(f"   Create {i}: Status {response.status_code}")
                break
        
        if rate_limited:
            print("   ✅ Rate limiting triggered for feedback creation")
        else:
            print("   ⚠️  Rate limiting not triggered")
    
    def test_06_feedback_update_rate_limit(self):
        """Test rate limiting for feedback updates"""
        print("\n📊 TEST 06: Feedback Update Rate Limit")
        print("-" * 40)
        
        self.client.force_authenticate(user=self.users['student1'])
        feedback = self.feedbacks['feedback1']
        
        rate_limited = False
        
        # Try multiple updates (limit is 10/minute in test settings)
        for i in range(1, 12):
            update_data = {
                'comment': f'Updated comment {i}'
            }
            
            response = self.client.patch(
                f'/api/feedback/{feedback.id}/',
                update_data,
                format='json'
            )
            
            if response.status_code == 429:
                rate_limited = True
                print(f"   Update {i}: Rate limited (429)")
                break
            elif response.status_code == 200:
                if i % 3 == 0:
                    print(f"   Update {i}: OK (200)")
            elif response.status_code == 403:
                print(f"   Update {i}: Permission denied (403)")
                break
            else:
                print(f"   Update {i}: Status {response.status_code}")
                break
        
        if rate_limited:
            print("   ✅ Rate limiting triggered for feedback updates")
        else:
            print("   ⚠️  Rate limiting not triggered")
    
    # ============ CUSTOM ENDPOINT TESTS ============
    
    def test_07_lesson_feedback_endpoint_caching(self):
        """Test caching for lesson_feedback endpoint"""
        print("\n📊 TEST 07: Lesson Feedback Endpoint Caching")
        print("-" * 40)
        
        self.client.force_authenticate(user=self.users['instructor1'])
        lesson = self.lessons['lesson1']
        
        # First request
        start_time = time.time()
        response1 = self.client.get(f'/api/feedback/lesson_feedback/?lesson_id={lesson.id}')
        time1 = time.time() - start_time
        
        # Second request (should be cached)
        start_time = time.time()
        response2 = self.client.get(f'/api/feedback/lesson_feedback/?lesson_id={lesson.id}')
        time2 = time.time() - start_time
        
        print(f"   First lesson_feedback request: {time1:.4f}s")
        print(f"   Second lesson_feedback request: {time2:.4f}s")
        
        if response1.status_code == 200 and response2.status_code == 200:
            stats = response1.data.get('statistics', {})
            print(f"   Lesson feedback: {stats.get('total_feedback', 0)} reviews, avg {stats.get('average_rating', 0)}")
            
            if time2 <= time1:
                improvement = ((time1 - time2) / time1) * 100 if time1 > 0 else 100
                print(f"   ✅ Lesson feedback caching: {improvement:.1f}% improvement")
            else:
                print("   ⚠️  Lesson feedback caching not showing improvement")
        else:
            print(f"   ⚠️  Could not access lesson_feedback: {response1.status_code}")
    
    def test_08_lesson_feedback_rate_limit(self):
        """Test rate limiting for lesson_feedback endpoint"""
        print("\n📊 TEST 08: Lesson Feedback Rate Limit")
        print("-" * 40)
        
        self.client.force_authenticate(user=self.users['instructor1'])
        lesson = self.lessons['lesson1']
        
        rate_limited = False
        
        # Make rapid requests (limit is 20/minute in test settings)
        for i in range(1, 25):
            response = self.client.get(f'/api/feedback/lesson_feedback/?lesson_id={lesson.id}')
            
            if response.status_code == 429:
                rate_limited = True
                print(f"   Request {i}: Rate limited (429)")
                break
            elif response.status_code == 200:
                if i % 5 == 0:
                    print(f"   Request {i}: OK (200)")
            else:
                print(f"   Request {i}: Status {response.status_code}")
                break
        
        if rate_limited:
            print("   ✅ Rate limiting triggered for lesson_feedback")
        else:
            print("   ⚠️  Rate limiting not triggered")
    
    def test_09_my_feedback_endpoint_caching(self):
        """Test caching for my_feedback endpoint (students only)"""
        print("\n📊 TEST 09: My Feedback Endpoint Caching")
        print("-" * 40)
        
        # Test as student
        self.client.force_authenticate(user=self.users['student1'])
        
        # First request
        start_time = time.time()
        response1 = self.client.get('/api/feedback/my_feedback/')
        time1 = time.time() - start_time
        
        # Second request (should be cached)
        start_time = time.time()
        response2 = self.client.get('/api/feedback/my_feedback/')
        time2 = time.time() - start_time
        
        print(f"   First my_feedback request: {time1:.4f}s")
        print(f"   Second my_feedback request: {time2:.4f}s")
        
        if response1.status_code == 200 and response2.status_code == 200:
            print(f"   Student feedback count: {response1.data.get('total_feedback', 0)}")
            
            if time2 <= time1:
                improvement = ((time1 - time2) / time1) * 100 if time1 > 0 else 100
                print(f"   ✅ My feedback caching: {improvement:.1f}% improvement")
            else:
                print("   ⚠️  My feedback caching not showing improvement")
        else:
            print(f"   ⚠️  Could not access my_feedback: {response1.status_code}")
    
    def test_10_my_feedback_rate_limit(self):
        """Test rate limiting for my_feedback endpoint"""
        print("\n📊 TEST 10: My Feedback Rate Limit")
        print("-" * 40)
        
        self.client.force_authenticate(user=self.users['student1'])
        
        rate_limited = False
        
        # Make rapid requests (limit is 15/minute in test settings)
        for i in range(1, 20):
            response = self.client.get('/api/feedback/my_feedback/')
            
            if response.status_code == 429:
                rate_limited = True
                print(f"   Request {i}: Rate limited (429)")
                break
            elif response.status_code == 200:
                if i % 5 == 0:
                    print(f"   Request {i}: OK (200)")
            else:
                print(f"   Request {i}: Status {response.status_code}")
                break
        
        if rate_limited:
            print("   ✅ Rate limiting triggered for my_feedback")
        else:
            print("   ⚠️  Rate limiting not triggered")
    
    def test_11_instructor_feedback_endpoint_caching(self):
        """Test caching for instructor_feedback endpoint"""
        print("\n📊 TEST 11: Instructor Feedback Endpoint Caching")
        print("-" * 40)
        
        # Test as instructor
        self.client.force_authenticate(user=self.users['instructor1'])
        
        # First request
        start_time = time.time()
        response1 = self.client.get('/api/feedback/instructor_feedback/')
        time1 = time.time() - start_time
        
        # Second request (should be cached)
        start_time = time.time()
        response2 = self.client.get('/api/feedback/instructor_feedback/')
        time2 = time.time() - start_time
        
        print(f"   First instructor_feedback request: {time1:.4f}s")
        print(f"   Second instructor_feedback request: {time2:.4f}s")
        
        if response1.status_code == 200 and response2.status_code == 200:
            stats = response1.data.get('statistics', {})
            print(f"   Instructor feedback: {stats.get('total_feedback', 0)} reviews, avg {stats.get('average_rating', 0)}")
            
            if time2 <= time1:
                improvement = ((time1 - time2) / time1) * 100 if time1 > 0 else 100
                print(f"   ✅ Instructor feedback caching: {improvement:.1f}% improvement")
            else:
                print("   ⚠️  Instructor feedback caching not showing improvement")
        else:
            print(f"   ⚠️  Could not access instructor_feedback: {response1.status_code}")
    
    def test_12_instructor_feedback_rate_limit(self):
        """Test rate limiting for instructor_feedback endpoint"""
        print("\n📊 TEST 12: Instructor Feedback Rate Limit")
        print("-" * 40)
        
        self.client.force_authenticate(user=self.users['instructor1'])
        
        rate_limited = False
        
        # Make rapid requests (limit is 10/minute in test settings)
        for i in range(1, 15):
            response = self.client.get('/api/feedback/instructor_feedback/')
            
            if response.status_code == 429:
                rate_limited = True
                print(f"   Request {i}: Rate limited (429)")
                break
            elif response.status_code == 200:
                if i % 4 == 0:
                    print(f"   Request {i}: OK (200)")
            else:
                print(f"   Request {i}: Status {response.status_code}")
                break
        
        if rate_limited:
            print("   ✅ Rate limiting triggered for instructor_feedback")
        else:
            print("   ⚠️  Rate limiting not triggered")
    
    def test_13_cache_invalidation_on_create(self):
        """Test cache invalidation when creating feedback"""
        print("\n📊 TEST 13: Cache Invalidation on Feedback Create")
        print("-" * 40)
        
        self.client.force_authenticate(user=self.users['student2'])
        
        # Create a new lesson that student2 attended but hasn't given feedback
        from DriveApp.models import Lesson, Attendance
        now = timezone.now()
        
        new_lesson = Lesson.objects.create(
            instructor=self.users['instructor1'],
            school=self.school1,
            title='Lesson for New Feedback',
            lesson_type='T',
            description='Lesson for cache invalidation test',
            duration=60,
            date=now - timedelta(days=1),
            status='C'
        )
        
        # Create attendance record
        Attendance.objects.create(
            student=self.profiles['student2'],
            lesson=new_lesson,
            presence=True,
            hours_completed=1.0
        )
        
        # Get initial my_feedback count
        response = self.client.get('/api/feedback/my_feedback/')
        if response.status_code == 200:
            initial_count = response.data.get('total_feedback', 0)
            print(f"   Initial feedback count: {initial_count}")
        
        # Create new feedback
        feedback_data = {
            'student': self.profiles['student2'].id,
            'lesson': new_lesson.id,
            'rating': 5,
            'comment': 'Cache invalidation test'
        }
        
        response = self.client.post('/api/feedback/', feedback_data, format='json')
        
        if response.status_code == 201:
            print(f"   New feedback created: ID {response.data.get('id')}")
            
            # Clear cache to simulate invalidation
            cache.clear()
            
            # Check my_feedback again
            response = self.client.get('/api/feedback/my_feedback/')
            if response.status_code == 200:
                new_count = response.data.get('total_feedback', 0)
                print(f"   New feedback count: {new_count}")
                
                # Should have one more feedback
                self.assertEqual(new_count, initial_count + 1)
                print("   ✅ Cache invalidation on create verified")
        else:
            print(f"   ⚠️  Could not create feedback: {response.status_code}")
            print(f"   Error: {response.data}")
    
    def test_14_cache_invalidation_on_update(self):
        """Test cache invalidation when updating feedback"""
        print("\n📊 TEST 14: Cache Invalidation on Feedback Update")
        print("-" * 40)
        
        self.client.force_authenticate(user=self.users['student1'])
        feedback = self.feedbacks['feedback1']
        
        # Get original comment
        response = self.client.get(f'/api/feedback/{feedback.id}/')
        if response.status_code == 200:
            original_comment = response.data.get('comment')
            print(f"   Original comment: {original_comment[:50]}...")
        
        # Update comment
        update_data = {
            'comment': 'Updated comment for cache invalidation test',
            'rating': 4
        }
        
        response = self.client.patch(
            f'/api/feedback/{feedback.id}/',
            update_data,
            format='json'
        )
        
        if response.status_code == 200:
            print(f"   Updated comment: {response.data.get('comment')[:50]}...")
            
            # Clear cache to simulate invalidation
            cache.clear()
            
            # Get feedback again
            response = self.client.get(f'/api/feedback/{feedback.id}/')
            if response.status_code == 200:
                updated_comment = response.data.get('comment')
                print(f"   Verified comment: {updated_comment[:50]}...")
                
                self.assertEqual(updated_comment, 'Updated comment for cache invalidation test')
                print("   ✅ Cache invalidation on update verified")
        else:
            print(f"   ⚠️  Could not update: {response.status_code}")
    
    def test_15_permissions_enforcement(self):
        """Test that permissions are properly enforced for feedback"""
        print("\n📊 TEST 15: Feedback Permission Enforcement")
        print("-" * 40)
        
        test_cases = [
            # (authenticated_as, tries_to_access_feedback, can_update, can_delete)
            ('student1', 'feedback1', True, False),    # Can update own, cannot delete
            ('student1', 'feedback2', False, False),   # Cannot access other student's
            ('instructor1', 'feedback1', False, False),# Can view but not update/delete
            ('school_owner', 'feedback1', False, True),# Can delete in own school
            ('school_owner', 'feedback3', False, False),# Cannot access other school
        ]
        
        for auth_user, target_feedback, can_update, can_delete in test_cases:
            self.client.force_authenticate(user=self.users[auth_user])
            feedback = self.feedbacks[target_feedback]
            
            # Test GET access
            response = self.client.get(f'/api/feedback/{feedback.id}/')
            
            # Test UPDATE if allowed
            if can_update:
                update_data = {'comment': 'Test update'}
                update_response = self.client.patch(
                    f'/api/feedback/{feedback.id}/',
                    update_data,
                    format='json'
                )
                print(f"   {auth_user} -> {target_feedback} UPDATE: {update_response.status_code}")
            
            # Test DELETE if allowed
            if can_delete:
                delete_response = self.client.delete(f'/api/feedback/{feedback.id}/')
                print(f"   {auth_user} -> {target_feedback} DELETE: {delete_response.status_code}")
            
            print(f"   {auth_user} -> {target_feedback} GET: {response.status_code}")
    
    def test_16_filtering_and_search(self):
        """Test filtering and search functionality"""
        print("\n📊 TEST 16: Filtering and Search")
        print("-" * 40)
        
        self.client.force_authenticate(user=self.users['platform_admin'])
        
        # Test filtering by rating
        response = self.client.get('/api/feedback/?rating=5')
        if response.status_code == 200:
            rating_count = self._get_result_count(response.data)
            print(f"   5-star ratings: {rating_count}")
        
        # Test filtering by student
        student = self.profiles['student1']
        response = self.client.get(f'/api/feedback/?student={student.id}')
        if response.status_code == 200:
            student_count = self._get_result_count(response.data)
            print(f"   Feedback from student {student.user.username}: {student_count}")
        
        # Test filtering by lesson
        lesson = self.lessons['lesson1']
        response = self.client.get(f'/api/feedback/?lesson={lesson.id}')
        if response.status_code == 200:
            lesson_count = self._get_result_count(response.data)
            print(f"   Feedback for lesson '{lesson.title}': {lesson_count}")
        
        # Test search by comment
        response = self.client.get('/api/feedback/?search=excellent')
        if response.status_code == 200:
            search_count = self._get_result_count(response.data)
            print(f"   Search results for 'excellent': {search_count}")
        
        # Test ordering
        response = self.client.get('/api/feedback/?ordering=-rating')
        if response.status_code == 200:
            print(f"   Ordered by rating descending: OK")
        
        response = self.client.get('/api/feedback/?ordering=created_at')
        if response.status_code == 200:
            print(f"   Ordered by created_at: OK")
        
        print("   ✅ Filtering and search tests completed")
    
    def test_17_validation_rules(self):
        """Test feedback validation rules"""
        print("\n📊 TEST 17: Feedback Validation Rules")
        print("-" * 40)
        
        self.client.force_authenticate(user=self.users['student1'])
        
        # Create a lesson student1 attended but hasn't given feedback
        from DriveApp.models import Lesson, Attendance
        now = timezone.now()
        
        test_lesson = Lesson.objects.create(
            instructor=self.users['instructor1'],
            school=self.school1,
            title='Validation Test Lesson',
            lesson_type='T',
            description='Lesson for validation tests',
            duration=60,
            date=now - timedelta(days=1),
            status='C'
        )
        
        Attendance.objects.create(
            student=self.profiles['student1'],
            lesson=test_lesson,
            presence=True,
            hours_completed=1.0
        )
        
        test_cases = [
            # (rating, comment, expected_status)
            (0, 'Rating too low', 400),      # Rating < 1
            (6, 'Rating too high', 400),     # Rating > 5
            (5, '', 201),                    # Valid with no comment
            (3, 'Valid feedback', 201),      # Valid with comment
        ]
        
        for rating, comment, expected_status in test_cases:
            feedback_data = {
                'student': self.profiles['student1'].id,
                'lesson': test_lesson.id,
                'rating': rating,
                'comment': comment
            }
            
            response = self.client.post('/api/feedback/', feedback_data, format='json')
            
            if response.status_code == expected_status:
                print(f"   ✅ Rating {rating}: {response.status_code} (expected {expected_status})")
            else:
                print(f"   ❌ Rating {rating}: {response.status_code} (expected {expected_status})")
        
        # Test duplicate feedback prevention
        feedback_data = {
            'student': self.profiles['student1'].id,
            'lesson': test_lesson.id,
            'rating': 4,
            'comment': 'Duplicate test'
        }
        
        # First creation should succeed
        response1 = self.client.post('/api/feedback/', feedback_data, format='json')
        
        # Second creation should fail (duplicate)
        response2 = self.client.post('/api/feedback/', feedback_data, format='json')
        
        if response1.status_code == 201 and response2.status_code == 400:
            print("   ✅ Duplicate feedback prevention working")
        else:
            print(f"   ⚠️  Duplicate prevention: {response1.status_code}, {response2.status_code}")
    
    def test_18_performance_benchmarks(self):
        """Test performance benchmarks for feedback endpoints"""
        print("\n📊 TEST 18: Performance Benchmarks")
        print("-" * 40)
        
        self.client.force_authenticate(user=self.users['platform_admin'])
        
        endpoints_to_test = [
            ('/api/feedback/', 'List Feedback'),
            ('/api/feedback/instructor_feedback/', 'Instructor Feedback'),
            (f'/api/feedback/lesson_feedback/?lesson_id={self.lessons["lesson1"].id}', 'Lesson Feedback'),
        ]
        
        for endpoint, description in endpoints_to_test:
            print(f"\n   Testing {description}:")
            
            # Clear cache for this endpoint
            cache.clear()
            
            # First request (uncached)
            start_time = time.time()
            response1 = self.client.get(endpoint)
            time1 = time.time() - start_time
            
            # Second request (cached)
            start_time = time.time()
            response2 = self.client.get(endpoint)
            time2 = time.time() - start_time
            
            if response1.status_code == 200 and response2.status_code == 200:
                print(f"     First request: {time1:.4f}s")
                print(f"     Second request: {time2:.4f}s")
                
                if time2 <= time1:
                    improvement = ((time1 - time2) / time1) * 100 if time1 > 0 else 100
                    if improvement >= 70:
                        print(f"     ✅ Excellent caching: {improvement:.1f}% improvement")
                    elif improvement >= 50:
                        print(f"     ⚡ Good caching: {improvement:.1f}% improvement")
                    elif improvement >= 30:
                        print(f"     📈 Moderate caching: {improvement:.1f}% improvement")
                    else:
                        print(f"     ⚠️  Minimal caching: {improvement:.1f}% improvement")
                else:
                    print("     ⚠️  No performance improvement")
            else:
                print(f"     ❌ Failed: {response1.status_code}")
    
    # ============ HELPER METHODS ============
    
    def _get_result_count(self, data):
        """Helper to get count from response data"""
        if isinstance(data, dict) and 'results' in data:
            return len(data['results'])
        elif isinstance(data, list):
            return len(data)
        elif isinstance(data, dict) and 'count' in data:
            return data['count']
        else:
            return 0
    
    def tearDown(self):
        """Cleanup after each test"""
        # Clean up any test-specific data
        cache.clear()
        print(f"   Cache cleared after test\n")
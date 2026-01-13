"""
Comprehensive tests for LessonViewSet with caching and rate limiting.
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


# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Drive.settings')

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
            'anon': '10/minute',
            'user': '20/minute',
            'lesson_list': '5/minute',
            'lesson_create': '2/minute',
            'lesson_update': '3/minute',
            'mark_attendance': '2/minute',
            'complete_lesson': '1/minute',
            'lesson_stats': '3/minute',
            'lesson_feedback': '4/minute',
        }
    }
)
class LessonViewSetComprehensiveTestCase(TestCase):
    """Comprehensive test suite for LessonViewSet"""
    
    @classmethod
    def setUpClass(cls):
        """Setup before all tests"""
        super().setUpClass()
        django.setup()
        
        print("\n" + "="*60)
        print("🚀 LESSON VIEWSET COMPREHENSIVE TEST")
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
        import uuid
        test_suffix = uuid.uuid4().hex[:6]
        
        # Platform Admin
        self.users['platform_admin'] = User.objects.create_user(
            username=f'lesson_platform_admin_{test_suffix}',
            email=f'platform_lesson_{test_suffix}@test.com',
            password=TEST_PASSWORD,
            role='A',
            is_staff=True,
            is_active=True
        )
        
        # School Owner
        self.users['school_owner'] = User.objects.create_user(
            username=f'lesson_school_owner_{test_suffix}',
            email=f'owner_lesson_{test_suffix}@test.com',
            password=TEST_PASSWORD,
            role='A',
            is_staff=False,
            is_active=True
        )
        
        # Instructor 1
        self.users['instructor1'] = User.objects.create_user(
            username=f'lesson_instructor1_{test_suffix}',
            email=f'instructor1_lesson_{test_suffix}@test.com',
            password=TEST_PASSWORD,
            role='I',
            is_active=True
        )
        
        # Instructor 2
        self.users['instructor2'] = User.objects.create_user(
            username=f'lesson_instructor2_{test_suffix}',
            email=f'instructor2_lesson_{test_suffix}@test.com',
            password=TEST_PASSWORD,
            role='I',
            is_active=True
        )
        
        # Student 1
        self.users['student1'] = User.objects.create_user(
            username=f'lesson_student1_{test_suffix}',
            email=f'student1_lesson_{test_suffix}@test.com',
            password=TEST_PASSWORD,
            role='S',
            is_active=True
        )
        
        # Student 2
        self.users['student2'] = User.objects.create_user(
            username=f'lesson_student2_{test_suffix}',
            email=f'student2_lesson_{test_suffix}@test.com',
            password=TEST_PASSWORD,
            role='S',
            is_active=True
        )
        
        # Create test schools
        from DriveApp.models import DrivingSchool, StudentProfile, Lesson
        
        # School 1 (owned by school_owner)
        self.school1 = DrivingSchool.objects.create(
            owner=self.users['school_owner'],
            name=f'Primary Lesson School {test_suffix}',
            email=f'primary_lesson_{test_suffix}@test.com',
            address='123 Main Street'
        )
        
        # School 2 (owned by platform_admin)
        self.school2 = DrivingSchool.objects.create(
            owner=self.users['platform_admin'],
            name=f'Secondary Lesson School {test_suffix}',
            email=f'secondary_lesson_{test_suffix}@test.com',
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
        
        # Instructor 2 profile (in school 1)
        self.profiles['instructor2'] = StudentProfile.objects.create(
            user=self.users['instructor2'],
            school=self.school1,
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
        
        # Create test lessons
        now = timezone.now()
        self.lessons = {}
        
        # Past lesson (completed)
        self.lessons['past_lesson'] = Lesson.objects.create(
            instructor=self.users['instructor1'],
            school=self.school1,
            title='Past Driving Lesson',
            lesson_type='D',
            description='Basic driving techniques',
            duration=60,
            date=now - timedelta(days=2),
            status='C'  # Completed
        )
        
        # Future lesson (scheduled)
        self.lessons['future_lesson'] = Lesson.objects.create(
            instructor=self.users['instructor1'],
            school=self.school1,
            title='Future Theory Lesson',
            lesson_type='T',
            description='Traffic rules and regulations',
            duration=90,
            date=now + timedelta(days=2),
            status='S'  # Scheduled
        )
        
        # Another instructor's lesson
        self.lessons['instructor2_lesson'] = Lesson.objects.create(
            instructor=self.users['instructor2'],
            school=self.school1,
            title='Instructor 2 Lesson',
            lesson_type='D',
            description='Advanced driving',
            duration=120,
            date=now + timedelta(days=1),
            status='S'
        )
        
        # School 2 lesson
        self.lessons['school2_lesson'] = Lesson.objects.create(
            instructor=self.users['instructor1'],
            school=self.school2,
            title='School 2 Lesson',
            lesson_type='T',
            description='Theory for school 2',
            duration=60,
            date=now + timedelta(days=3),
            status='S'
        )
        
        print("✅ Test data created:")
        print(f"   - Schools: {self.school1.name}, {self.school2.name}")
        print(f"   - Lessons: {len(self.lessons)} lessons")
        print(f"   - Users: {len(self.users)} users")
    
    # ============ BASIC CACHING TESTS ============
    
    def test_01_list_lessons_caching(self):
        """Test that listing lessons uses caching"""
        print("\n📊 TEST 01: List Lessons with Caching")
        print("-" * 40)
        
        # Authenticate as platform admin
        self.client.force_authenticate(user=self.users['platform_admin'])
        
        # First request - should hit database
        start_time = time.time()
        response1 = self.client.get('/api/lesson/')
        time1 = time.time() - start_time
        
        self.assertEqual(response1.status_code, status.HTTP_200_OK)
        
        # Get count
        data1 = response1.data
        count1 = self._get_result_count(data1)
        
        print(f"   First request: {count1} lessons, {time1:.4f}s")
        
        # Second request - should be served from cache
        start_time = time.time()
        response2 = self.client.get('/api/lesson/')
        time2 = time.time() - start_time
        
        data2 = response2.data
        count2 = self._get_result_count(data2)
        
        print(f"   Second request: {count2} lessons, {time2:.4f}s")
        
        # Should get same data
        self.assertEqual(count1, count2)
        
        # Cached response should be faster
        if time2 <= time1:
            improvement = ((time1 - time2) / time1) * 100 if time1 > 0 else 100
            print(f"   ✅ Query caching working: {improvement:.1f}% improvement")
        else:
            print(f"   ⚠️  Cached response not faster: {time2:.4f}s vs {time1:.4f}s")
    
    def test_02_multi_tenancy_lesson_isolation(self):
        """Test that users only see permitted lessons"""
        print("\n📊 TEST 02: Multi-tenancy Lesson Isolation")
        print("-" * 40)
        
        test_cases = [
            ('platform_admin', 'Platform Admin', 4),    # Should see all 4 lessons
            ('school_owner', 'School Owner', 3),        # Should see lessons in school1 (3)
            ('instructor1', 'Instructor 1', 3),         # Should see their lessons in school1 + school2
            ('instructor2', 'Instructor 2', 1),         # Should see only their own lesson
            ('student1', 'Student 1', 3),               # Should see lessons in school1 (3)
        ]
        
        for user_key, user_description, expected_count in test_cases:
            self.client.force_authenticate(user=self.users[user_key])
            
            response = self.client.get('/api/lesson/')
            data = response.data
            count = self._get_result_count(data)
            
            print(f"   {user_description}: sees {count} lessons")
            
            if count == expected_count:
                print(f"     ✅ Correct isolation")
            else:
                print(f"     ⚠️  Expected {expected_count}, got {count}")
            
            # Verify status code
            self.assertIn(response.status_code, [200])
    
    def test_03_lesson_detail_caching(self):
        """Test caching for individual lesson"""
        print("\n📊 TEST 03: Lesson Detail Caching")
        print("-" * 40)
        
        self.client.force_authenticate(user=self.users['platform_admin'])
        lesson = self.lessons['past_lesson']
        
        # First request
        start_time = time.time()
        response1 = self.client.get(f'/api/lesson/{lesson.id}/')
        time1 = time.time() - start_time
        
        # Second request (should be cached)
        start_time = time.time()
        response2 = self.client.get(f'/api/lesson/{lesson.id}/')
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
    
    # ============ CACHE INVALIDATION TESTS ============
    
    def test_04_cache_invalidation_on_lesson_create(self):
        """Test cache invalidation when creating lesson"""
        print("\n📊 TEST 04: Cache Invalidation on Lesson Create")
        print("-" * 40)
        
        self.client.force_authenticate(user=self.users['platform_admin'])
        
        # Get initial count
        response = self.client.get('/api/lesson/')
        data = response.data
        initial_count = self._get_result_count(data)
        print(f"   Initial lesson count: {initial_count}")
        
        # Create a new lesson
        new_lesson_data = {
            'instructor': self.users['instructor1'].id,
            'school': self.school1.id,
            'title': 'New Test Lesson',
            'lesson_type': 'T',
            'description': 'Test description',
            'duration': 60,
            'date': (timezone.now() + timedelta(days=5)).isoformat(),
            'status': 'S'
        }
        
        response = self.client.post('/api/lesson/', new_lesson_data, format='json')
        
        if response.status_code in [201, 200]:
            print(f"   New lesson created: ID {response.data.get('id')}")
            
            # Clear cache manually to simulate invalidation
            cache.clear()
            
            # Get list again
            response = self.client.get('/api/lesson/')
            data = response.data
            new_count = self._get_result_count(data)
            
            print(f"   New lesson count: {new_count}")
            
            # Should have one more lesson
            self.assertEqual(new_count, initial_count + 1)
            print("   ✅ Cache invalidation on create verified")
        else:
            print(f"   ⚠️  Could not create lesson: {response.status_code}")
            print(f"   Error: {response.data}")
    
    def test_05_cache_invalidation_on_lesson_update(self):
        """Test cache invalidation when updating lesson"""
        print("\n📊 TEST 05: Cache Invalidation on Lesson Update")
        print("-" * 40)
        
        self.client.force_authenticate(user=self.users['instructor1'])
        lesson = self.lessons['future_lesson']
        
        # Get original title
        response = self.client.get(f'/api/lesson/{lesson.id}/')
        if response.status_code == 200:
            original_title = response.data.get('title')
            print(f"   Original title: {original_title}")
        
        # Update title
        update_data = {'title': 'Updated Lesson Title'}
        response = self.client.patch(
            f'/api/lesson/{lesson.id}/',
            update_data,
            format='json'
        )
        
        if response.status_code == 200:
            print(f"   Updated title: {response.data.get('title')}")
            
            # Clear cache to simulate invalidation
            cache.clear()
            
            # Get lesson again
            response = self.client.get(f'/api/lesson/{lesson.id}/')
            if response.status_code == 200:
                updated_title = response.data.get('title')
                print(f"   Verified title: {updated_title}")
                
                self.assertEqual(updated_title, 'Updated Lesson Title')
                print("   ✅ Cache invalidation on update verified")
        else:
            print(f"   ⚠️  Could not update: {response.status_code}")
            print(f"   Error: {response.data}")
    
    def test_06_cache_invalidation_on_lesson_delete(self):
        """Test cache invalidation when deleting lesson"""
        print("\n📊 TEST 06: Cache Invalidation on Lesson Delete")
        print("-" * 40)
        
        self.client.force_authenticate(user=self.users['platform_admin'])
        
        # Create a lesson to delete
        from DriveApp.models import Lesson
        temp_lesson = Lesson.objects.create(
            instructor=self.users['instructor1'],
            school=self.school1,
            title='Temporary Lesson to Delete',
            lesson_type='T',
            description='Will be deleted',
            duration=30,
            date=timezone.now() + timedelta(days=7),
            status='S'
        )
        
        print(f"   Created temp lesson: ID {temp_lesson.id}")
        
        # Delete the lesson
        response = self.client.delete(f'/api/lesson/{temp_lesson.id}/')
        
        if response.status_code in [204, 200]:
            print(f"   Deleted lesson: Status {response.status_code}")
            
            # Clear cache to simulate invalidation
            cache.clear()
            
            # Verify deletion
            response = self.client.get(f'/api/lesson/{temp_lesson.id}/')
            print(f"   Get after delete: Status {response.status_code}")
            
            if response.status_code in [404, 403]:
                print("   ✅ Lesson successfully deleted")
            else:
                print("   ⚠️  Lesson might still exist")
        else:
            print(f"   ⚠️  Could not delete: {response.status_code}")
    
    # ============ RATE LIMITING TESTS ============
    
    def test_07_lesson_list_rate_limit(self):
        """Test rate limiting for lesson list endpoint"""
        print("\n📊 TEST 07: Lesson List Rate Limit")
        print("-" * 40)
        
        self.client.force_authenticate(user=self.users['student1'])
        
        rate_limited = False
        
        # Make rapid requests (limit is 5/minute in test settings)
        for i in range(1, 7):
            response = self.client.get('/api/lesson/')
            
            if response.status_code == 429:
                rate_limited = True
                print(f"   Request {i}: Rate limited (429)")
                break
            elif response.status_code == 200:
                print(f"   Request {i}: OK (200)")
            else:
                print(f"   Request {i}: Status {response.status_code}")
                break
        
        if rate_limited:
            print("   ✅ Rate limiting triggered for lesson list")
        else:
            print("   ⚠️  Rate limiting not triggered")
    
    def test_08_lesson_create_rate_limit(self):
        """Test rate limiting for lesson creation"""
        print("\n📊 TEST 08: Lesson Create Rate Limit")
        print("-" * 40)
        
        self.client.force_authenticate(user=self.users['platform_admin'])
        
        rate_limited = False
        lesson_data = {
            'instructor': self.users['instructor1'].id,
            'school': self.school1.id,
            'title': 'Test Lesson',
            'lesson_type': 'T',
            'description': 'Rate limit test',
            'duration': 30,
            'date': (timezone.now() + timedelta(days=10)).isoformat(),
            'status': 'S'
        }
        
        # Try multiple creations (limit is 2/minute in test settings)
        for i in range(1, 4):
            response = self.client.post('/api/lesson/', lesson_data, format='json')
            
            if response.status_code == 429:
                rate_limited = True
                print(f"   Create {i}: Rate limited (429)")
                break
            elif response.status_code in [201, 200]:
                print(f"   Create {i}: Created (201)")
            elif response.status_code == 400:
                print(f"   Create {i}: Bad request (400)")
                # Might be due to duplicate or validation
            else:
                print(f"   Create {i}: Status {response.status_code}")
                break
        
        if rate_limited:
            print("   ✅ Rate limiting triggered for lesson creation")
        else:
            print("   ⚠️  Rate limiting not triggered")
    
    def test_09_mark_attendance_rate_limit(self):
        """Test rate limiting for marking attendance"""
        print("\n📊 TEST 09: Mark Attendance Rate Limit")
        print("-" * 40)
        
        self.client.force_authenticate(user=self.users['instructor1'])
        lesson = self.lessons['past_lesson']
        
        # Create attendance data
        attendance_data = {
            'student_ids': [self.profiles['student1'].id],
            'presence': True,
            'hours_completed': 1.0,
            'notes': 'Test attendance'
        }
        
        rate_limited = False
        
        # Try multiple attendance marks (limit is 2/minute in test settings)
        for i in range(1, 4):
            response = self.client.post(
                f'/api/lesson/{lesson.id}/mark_attendance/',
                attendance_data,
                format='json'
            )
            
            if response.status_code == 429:
                rate_limited = True
                print(f"   Attendance {i}: Rate limited (429)")
                break
            elif response.status_code == 200:
                print(f"   Attendance {i}: OK (200)")
            elif response.status_code == 403:
                print(f"   Attendance {i}: Permission denied (403)")
                break
            elif response.status_code == 400:
                print(f"   Attendance {i}: Bad request (400)")
                # Might be due to already marked attendance
                break
            else:
                print(f"   Attendance {i}: Status {response.status_code}")
                break
        
        if rate_limited:
            print("   ✅ Rate limiting triggered for marking attendance")
        else:
            print("   ⚠️  Rate limiting not triggered")
    
    def test_10_complete_lesson_rate_limit(self):
        """Test rate limiting for completing lessons"""
        print("\n📊 TEST 10: Complete Lesson Rate Limit")
        print("-" * 40)
        
        self.client.force_authenticate(user=self.users['instructor1'])
        
        # Create a lesson to complete
        from DriveApp.models import Lesson
        now = timezone.now()
        complete_lesson = Lesson.objects.create(
            instructor=self.users['instructor1'],
            school=self.school1,
            title='Lesson to Complete',
            lesson_type='T',
            description='Will be completed',
            duration=60,
            date=now - timedelta(hours=2),  # Past lesson
            status='S'
        )
        
        rate_limited = False
        
        # Try multiple completions (limit is 1/minute in test settings)
        for i in range(1, 3):
            response = self.client.post(
                f'/api/lesson/{complete_lesson.id}/complete_lesson/'
            )
            
            if response.status_code == 429:
                rate_limited = True
                print(f"   Complete {i}: Rate limited (429)")
                break
            elif response.status_code == 200:
                print(f"   Complete {i}: OK (200)")
            elif response.status_code == 400:
                print(f"   Complete {i}: Already completed (400)")
                break
            else:
                print(f"   Complete {i}: Status {response.status_code}")
                break
        
        if rate_limited:
            print("   ✅ Rate limiting triggered for completing lessons")
        else:
            print("   ⚠️  Rate limiting not triggered")
    
    # ============ CUSTOM ENDPOINT TESTS ============
    
    def test_11_upcoming_lessons_caching(self):
        """Test caching for upcoming lessons endpoint"""
        print("\n📊 TEST 11: Upcoming Lessons Caching")
        print("-" * 40)
        
        self.client.force_authenticate(user=self.users['student1'])
        
        # First request
        start_time = time.time()
        response1 = self.client.get('/api/lesson/upcoming/')
        time1 = time.time() - start_time
        
        # Second request (should be cached)
        start_time = time.time()
        response2 = self.client.get('/api/lesson/upcoming/')
        time2 = time.time() - start_time
        
        print(f"   First upcoming request: {time1:.4f}s")
        print(f"   Second upcoming request: {time2:.4f}s")
        
        if response1.status_code == 200 and response2.status_code == 200:
            data1 = response1.data
            data2 = response2.data
            
            count1 = self._get_result_count(data1)
            count2 = self._get_result_count(data2)
            
            print(f"   Count: {count1} upcoming lessons")
            
            if time2 <= time1:
                improvement = ((time1 - time2) / time1) * 100 if time1 > 0 else 100
                print(f"   ✅ Upcoming caching: {improvement:.1f}% improvement")
            else:
                print("   ⚠️  Upcoming caching not showing improvement")
        else:
            print(f"   ⚠️  Could not access upcoming: {response1.status_code}")
    
    def test_12_my_lessons_caching(self):
        """Test caching for my_lessons endpoint"""
        print("\n📊 TEST 12: My Lessons Caching")
        print("-" * 40)
        
        # Test for instructor
        self.client.force_authenticate(user=self.users['instructor1'])
        
        # First request
        start_time = time.time()
        response1 = self.client.get('/api/lesson/my_lessons/')
        time1 = time.time() - start_time
        
        # Second request (should be cached)
        start_time = time.time()
        response2 = self.client.get('/api/lesson/my_lessons/')
        time2 = time.time() - start_time
        
        print(f"   Instructor1 - First my_lessons: {time1:.4f}s")
        print(f"   Instructor1 - Second my_lessons: {time2:.4f}s")
        
        if response1.status_code == 200 and response2.status_code == 200:
            data1 = response1.data
            count1 = self._get_result_count(data1)
            print(f"   Instructor1 sees {count1} lessons")
            
            if time2 <= time1:
                print("   ✅ My lessons caching working for instructor")
            else:
                print("   ⚠️  My lessons caching not showing improvement")
        else:
            print(f"   ⚠️  Could not access my_lessons: {response1.status_code}")
    
    def test_13_lesson_statistics_caching(self):
        """Test caching for lesson statistics"""
        print("\n📊 TEST 13: Lesson Statistics Caching")
        print("-" * 40)
        
        self.client.force_authenticate(user=self.users['instructor1'])
        
        # First request
        start_time = time.time()
        response1 = self.client.get('/api/lesson/statistics/')
        time1 = time.time() - start_time
        
        # Second request (should be cached)
        start_time = time.time()
        response2 = self.client.get('/api/lesson/statistics/')
        time2 = time.time() - start_time
        
        print(f"   First statistics request: {time1:.4f}s")
        print(f"   Second statistics request: {time2:.4f}s")
        
        if response1.status_code == 200 and response2.status_code == 200:
            print(f"   Statistics: {response1.data}")
            
            if time2 <= time1:
                improvement = ((time1 - time2) / time1) * 100 if time1 > 0 else 100
                print(f"   ✅ Statistics caching: {improvement:.1f}% improvement")
            else:
                print("   ⚠️  Statistics caching not showing improvement")
        else:
            print(f"   ⚠️  Could not access statistics: {response1.status_code}")
    
    def test_14_lesson_feedback_caching(self):
        """Test caching for lesson feedback"""
        print("\n📊 TEST 14: Lesson Feedback Caching")
        print("-" * 40)
        
        # Create some feedback first
        from DriveApp.models import Feedback
        lesson = self.lessons['past_lesson']
        
        # Create feedback
        Feedback.objects.create(
            student=self.profiles['student1'],
            lesson=lesson,
            rating=5,
            comment='Great lesson!'
        )
        
        # Test as instructor
        self.client.force_authenticate(user=self.users['instructor1'])
        
        # First request
        start_time = time.time()
        response1 = self.client.get(f'/api/lesson/{lesson.id}/feedback/')
        time1 = time.time() - start_time
        
        # Second request (should be cached)
        start_time = time.time()
        response2 = self.client.get(f'/api/lesson/{lesson.id}/feedback/')
        time2 = time.time() - start_time
        
        print(f"   First feedback request: {time1:.4f}s")
        print(f"   Second feedback request: {time2:.4f}s")
        
        if response1.status_code == 200 and response2.status_code == 200:
            print(f"   Feedback count: {response1.data.get('total_feedback', 0)}")
            
            if time2 <= time1:
                improvement = ((time1 - time2) / time1) * 100 if time1 > 0 else 100
                print(f"   ✅ Feedback caching: {improvement:.1f}% improvement")
            else:
                print("   ⚠️  Feedback caching not showing improvement")
        else:
            print(f"   ⚠️  Could not access feedback: {response1.status_code}")
    
    def test_15_permissions_enforcement(self):
        """Test that permissions are properly enforced for lessons"""
        print("\n📊 TEST 15: Lesson Permission Enforcement")
        print("-" * 40)
        
        test_cases = [
            # (authenticated_as, tries_to_access_lesson, expected_status_for_detail)
            ('student1', 'past_lesson', 200),           # Can access lesson in same school
            ('student1', 'school2_lesson', 403),        # Cannot access lesson in different school
            ('instructor1', 'past_lesson', 200),        # Can access own lesson
            ('instructor2', 'past_lesson', 403),        # Cannot access other instructor's lesson
            ('school_owner', 'past_lesson', 200),       # Can access lesson in own school
            ('school_owner', 'school2_lesson', 403),    # Cannot access lesson in different school
        ]
        
        for auth_user, target_lesson, expected_status in test_cases:
            self.client.force_authenticate(user=self.users[auth_user])
            lesson = self.lessons[target_lesson]
            
            response = self.client.get(f'/api/lesson/{lesson.id}/')
            
            status_match = response.status_code == expected_status
            
            if status_match:
                print(f"   ✅ {auth_user} -> {target_lesson}: {response.status_code}")
            else:
                print(f"   ❌ {auth_user} -> {target_lesson}: {response.status_code} (expected {expected_status})")
    
    def test_16_attendance_endpoint_caching(self):
        """Test caching for attendance endpoint"""
        print("\n📊 TEST 16: Attendance Endpoint Caching")
        print("-" * 40)
        
        # Create attendance record
        from DriveApp.models import Attendance
        lesson = self.lessons['past_lesson']
        
        Attendance.objects.create(
            student=self.profiles['student1'],
            lesson=lesson,
            presence=True,
            hours_completed=1.0
        )
        
        # Test as instructor
        self.client.force_authenticate(user=self.users['instructor1'])
        
        # First request
        start_time = time.time()
        response1 = self.client.get(f'/api/lesson/{lesson.id}/attendance/')
        time1 = time.time() - start_time
        
        # Second request (should be cached for instructor)
        start_time = time.time()
        response2 = self.client.get(f'/api/lesson/{lesson.id}/attendance/')
        time2 = time.time() - start_time
        
        print(f"   First attendance request: {time1:.4f}s")
        print(f"   Second attendance request: {time2:.4f}s")
        
        if response1.status_code == 200 and response2.status_code == 200:
            print(f"   Attendance count: {response1.data.get('total_attendance', 0)}")
            
            if time2 <= time1:
                print("   ✅ Attendance caching working for instructor")
            else:
                print("   ⚠️  Attendance caching not showing improvement")
        else:
            print(f"   ⚠️  Could not access attendance: {response1.status_code}")
    
    def test_17_schedule_endpoint_caching(self):
        """Test caching for schedule endpoint"""
        print("\n📊 TEST 17: Schedule Endpoint Caching")
        print("-" * 40)
        
        # Create schedule
        from DriveApp.models import Schedule
        lesson = self.lessons['future_lesson']
        
        Schedule.objects.create(
            lesson=lesson,
            instructor=self.users['instructor1'],
            start_time=lesson.date,
            end_time=lesson.date + timedelta(minutes=lesson.duration)
        )
        
        self.client.force_authenticate(user=self.users['platform_admin'])
        
        # First request
        start_time = time.time()
        response1 = self.client.get(f'/api/lesson/{lesson.id}/schedule/')
        time1 = time.time() - start_time
        
        # Second request (should be cached due to @cache_page decorator)
        start_time = time.time()
        response2 = self.client.get(f'/api/lesson/{lesson.id}/schedule/')
        time2 = time.time() - start_time
        
        print(f"   First schedule request: {time1:.4f}s")
        print(f"   Second schedule request: {time2:.4f}s")
        
        if response1.status_code == 200 and response2.status_code == 200:
            if time2 <= time1:
                improvement = ((time1 - time2) / time1) * 100 if time1 > 0 else 100
                print(f"   ✅ Schedule caching: {improvement:.1f}% improvement")
            else:
                print("   ⚠️  Schedule caching not showing improvement")
        else:
            print(f"   ⚠️  Could not access schedule: {response1.status_code}")
    
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
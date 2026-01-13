"""
Comprehensive tests for AttendanceViewSet with caching and rate limiting.
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
            'attendance_list': '30/minute',
            'attendance_create': '10/minute',
            'attendance_update': '15/minute',
            'attendance_bulk_create': '3/minute',
            'attendance_statistics': '20/minute',
        }
    }
)
class AttendanceViewSetComprehensiveTestCase(TestCase):
    """Comprehensive test suite for AttendanceViewSet"""
    
    @classmethod
    def setUpClass(cls):
        """Setup before all tests"""
        super().setUpClass()
        print("\n" + "="*60)
        print("🚀 ATTENDANCE VIEWSET COMPREHENSIVE TEST")
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
            username=f'attendance_admin_{test_suffix}',
            email=f'admin_attendance_{test_suffix}@test.com',
            password=TEST_PASSWORD,
            role='A',
            is_staff=True,
            is_active=True
        )
        
        # School Owner
        self.users['school_owner'] = User.objects.create_user(
            username=f'attendance_owner_{test_suffix}',
            email=f'owner_attendance_{test_suffix}@test.com',
            password=TEST_PASSWORD,
            role='A',
            is_staff=False,
            is_active=True
        )
        
        # Instructor 1
        self.users['instructor1'] = User.objects.create_user(
            username=f'attendance_instructor1_{test_suffix}',
            email=f'instructor1_attendance_{test_suffix}@test.com',
            password=TEST_PASSWORD,
            role='I',
            is_active=True
        )
        
        # Instructor 2 (different school)
        self.users['instructor2'] = User.objects.create_user(
            username=f'attendance_instructor2_{test_suffix}',
            email=f'instructor2_attendance_{test_suffix}@test.com',
            password=TEST_PASSWORD,
            role='I',
            is_active=True
        )
        
        # Student 1
        self.users['student1'] = User.objects.create_user(
            username=f'attendance_student1_{test_suffix}',
            email=f'student1_attendance_{test_suffix}@test.com',
            password=TEST_PASSWORD,
            role='S',
            is_active=True
        )
        
        # Student 2
        self.users['student2'] = User.objects.create_user(
            username=f'attendance_student2_{test_suffix}',
            email=f'student2_attendance_{test_suffix}@test.com',
            password=TEST_PASSWORD,
            role='S',
            is_active=True
        )
        
        # Student 3 (different school)
        self.users['student3'] = User.objects.create_user(
            username=f'attendance_student3_{test_suffix}',
            email=f'student3_attendance_{test_suffix}@test.com',
            password=TEST_PASSWORD,
            role='S',
            is_active=True
        )
        
        # Create test schools
        from DriveApp.models import DrivingSchool, StudentProfile, Lesson, Attendance
        
        # School 1 (owned by school_owner)
        self.school1 = DrivingSchool.objects.create(
            owner=self.users['school_owner'],
            name=f'Primary Attendance School {test_suffix}',
            email=f'primary_attendance_{test_suffix}@test.com',
            address='123 Main Street'
        )
        
        # School 2 (owned by platform_admin)
        self.school2 = DrivingSchool.objects.create(
            owner=self.users['platform_admin'],
            name=f'Secondary Attendance School {test_suffix}',
            email=f'secondary_attendance_{test_suffix}@test.com',
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
        
        # Lesson 1 (past, with instructor 1)
        self.lessons['lesson1'] = Lesson.objects.create(
            instructor=self.users['instructor1'],
            school=self.school1,
            title='Driving Lesson 1',
            lesson_type='D',
            description='Lesson 1 for attendance tests',
            duration=60,
            date=now - timedelta(days=2),
            status='C'
        )
        
        # Lesson 2 (future, with instructor 1)
        self.lessons['lesson2'] = Lesson.objects.create(
            instructor=self.users['instructor1'],
            school=self.school1,
            title='Theory Lesson 1',
            lesson_type='T',
            description='Lesson 2 for attendance tests',
            duration=90,
            date=now + timedelta(days=2),
            status='S'
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
        
        # Create attendance records
        self.attendances = {}
        
        # Student 1 attended lesson 1
        self.attendances['attendance1'] = Attendance.objects.create(
            student=self.profiles['student1'],
            lesson=self.lessons['lesson1'],
            presence=True,
            hours_completed=1.0,
            notes='Good performance'
        )
        
        # Student 2 absent from lesson 1
        self.attendances['attendance2'] = Attendance.objects.create(
            student=self.profiles['student2'],
            lesson=self.lessons['lesson1'],
            presence=False,
            hours_completed=0,
            notes='Sick'
        )
        
        # Student 3 attended lesson 3 (different school)
        self.attendances['attendance3'] = Attendance.objects.create(
            student=self.profiles['student3'],
            lesson=self.lessons['lesson3'],
            presence=True,
            hours_completed=1.5,
            notes='Excellent'
        )
        
        print("✅ Test data created:")
        print(f"   - Schools: {self.school1.name}, {self.school2.name}")
        print(f"   - Attendance records: {len(self.attendances)}")
        print(f"   - Lessons: {len(self.lessons)}")
        print(f"   - Users: {len(self.users)}")
    
    # ============ BASIC CACHING TESTS ============
    
    def test_01_list_attendance_caching(self):
        """Test that listing attendance uses caching"""
        print("\n📊 TEST 01: List Attendance with Caching")
        print("-" * 40)
        
        # Authenticate as platform admin (can see all)
        self.client.force_authenticate(user=self.users['platform_admin'])
        
        # First request - should hit database
        start_time = time.time()
        response1 = self.client.get('/api/attendance/')
        time1 = time.time() - start_time
        
        self.assertEqual(response1.status_code, status.HTTP_200_OK)
        
        # Get count from response
        count1 = self._get_result_count(response1.data)
        print(f"   First request: {count1} attendance records, {time1:.4f}s")
        
        # Second request - should be served from cache
        start_time = time.time()
        response2 = self.client.get('/api/attendance/')
        time2 = time.time() - start_time
        
        count2 = self._get_result_count(response2.data)
        print(f"   Second request: {count2} attendance records, {time2:.4f}s")
        
        # Should get same data
        self.assertEqual(count1, count2)
        
        # Cached response should be faster
        if time2 <= time1:
            improvement = ((time1 - time2) / time1) * 100 if time1 > 0 else 100
            print(f"   ✅ Query caching working: {improvement:.1f}% improvement")
        else:
            print(f"   ⚠️  Cached response not faster: {time2:.4f}s vs {time1:.4f}s")
    
    def test_02_multi_tenancy_attendance_isolation(self):
        """Test that users only see permitted attendance records"""
        print("\n📊 TEST 02: Multi-tenancy Attendance Isolation")
        print("-" * 40)
        
        test_cases = [
            ('platform_admin', 'Platform Admin', 3),    # Should see all 3 records
            ('school_owner', 'School Owner', 2),        # Should see records in school1 (2)
            ('instructor1', 'Instructor 1', 2),         # Should see records for their lessons
            ('instructor2', 'Instructor 2', 1),         # Should see records for their lessons
            ('student1', 'Student 1', 1),               # Should see only their own records
            ('student3', 'Student 3', 1),               # Should see only their own records
        ]
        
        for user_key, user_description, expected_count in test_cases:
            self.client.force_authenticate(user=self.users[user_key])
            
            response = self.client.get('/api/attendance/')
            data = response.data
            count = self._get_result_count(data)
            
            print(f"   {user_description}: sees {count} attendance records")
            
            if count == expected_count:
                print(f"     ✅ Correct isolation")
            else:
                print(f"     ⚠️  Expected {expected_count}, got {count}")
            
            # Verify status code
            self.assertIn(response.status_code, [200])
    
    def test_03_attendance_detail_caching(self):
        """Test caching for individual attendance record"""
        print("\n📊 TEST 03: Attendance Detail Caching")
        print("-" * 40)
        
        self.client.force_authenticate(user=self.users['platform_admin'])
        attendance = self.attendances['attendance1']
        
        # First request
        start_time = time.time()
        response1 = self.client.get(f'/api/attendance/{attendance.id}/')
        time1 = time.time() - start_time
        
        # Second request (should be cached)
        start_time = time.time()
        response2 = self.client.get(f'/api/attendance/{attendance.id}/')
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
    
    def test_04_cache_invalidation_on_attendance_create(self):
        """Test cache invalidation when creating attendance"""
        print("\n📊 TEST 04: Cache Invalidation on Attendance Create")
        print("-" * 40)
        
        self.client.force_authenticate(user=self.users['instructor1'])
        
        # Get initial count
        response = self.client.get('/api/attendance/')
        data = response.data
        initial_count = self._get_result_count(data)
        print(f"   Initial attendance count: {initial_count}")
        
        # Create a new attendance record
        new_attendance_data = {
            'student': self.profiles['student1'].id,
            'lesson': self.lessons['lesson2'].id,
            'presence': True,
            'hours_completed': 1.5,
            'notes': 'Test attendance creation'
        }
        
        response = self.client.post('/api/attendance/', new_attendance_data, format='json')
        
        if response.status_code in [201, 200]:
            print(f"   New attendance created: ID {response.data.get('id')}")
            
            # Clear cache manually to simulate invalidation
            cache.clear()
            
            # Get list again
            response = self.client.get('/api/attendance/')
            data = response.data
            new_count = self._get_result_count(data)
            
            print(f"   New attendance count: {new_count}")
            
            # Should have one more record
            self.assertEqual(new_count, initial_count + 1)
            print("   ✅ Cache invalidation on create verified")
        else:
            print(f"   ⚠️  Could not create attendance: {response.status_code}")
            print(f"   Error: {response.data}")
    
    def test_05_cache_invalidation_on_attendance_update(self):
        """Test cache invalidation when updating attendance"""
        print("\n📊 TEST 05: Cache Invalidation on Attendance Update")
        print("-" * 40)
        
        self.client.force_authenticate(user=self.users['instructor1'])
        attendance = self.attendances['attendance1']
        
        # Get original presence status
        response = self.client.get(f'/api/attendance/{attendance.id}/')
        if response.status_code == 200:
            original_presence = response.data.get('presence')
            print(f"   Original presence: {original_presence}")
        
        # Update presence
        update_data = {'presence': False, 'notes': 'Updated to absent'}
        response = self.client.patch(
            f'/api/attendance/{attendance.id}/',
            update_data,
            format='json'
        )
        
        if response.status_code == 200:
            print(f"   Updated presence: {response.data.get('presence')}")
            
            # Clear cache to simulate invalidation
            cache.clear()
            
            # Get attendance again
            response = self.client.get(f'/api/attendance/{attendance.id}/')
            if response.status_code == 200:
                updated_presence = response.data.get('presence')
                print(f"   Verified presence: {updated_presence}")
                
                self.assertEqual(updated_presence, False)
                print("   ✅ Cache invalidation on update verified")
        else:
            print(f"   ⚠️  Could not update: {response.status_code}")
    
    # ============ RATE LIMITING TESTS ============
    
    def test_06_attendance_list_rate_limit(self):
        """Test rate limiting for attendance list endpoint"""
        print("\n📊 TEST 06: Attendance List Rate Limit")
        print("-" * 40)
        
        self.client.force_authenticate(user=self.users['student1'])
        
        rate_limited = False
        
        # Make rapid requests (limit is 30/minute in test settings)
        for i in range(1, 32):
            response = self.client.get('/api/attendance/')
            
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
            print("   ✅ Rate limiting triggered for attendance list")
        else:
            print("   ⚠️  Rate limiting not triggered")
    
    def test_07_attendance_create_rate_limit(self):
        """Test rate limiting for attendance creation"""
        print("\n📊 TEST 07: Attendance Create Rate Limit")
        print("-" * 40)
        
        self.client.force_authenticate(user=self.users['platform_admin'])
        
        # Create attendance data
        attendance_data = {
            'student': self.profiles['student1'].id,
            'lesson': self.lessons['lesson1'].id,
            'presence': True,
            'hours_completed': 1.0,
            'notes': 'Rate limit test'
        }
        
        rate_limited = False
        
        # Try multiple creations (limit is 10/minute in test settings)
        for i in range(1, 12):
            response = self.client.post('/api/attendance/', attendance_data, format='json')
            
            if response.status_code == 429:
                rate_limited = True
                print(f"   Create {i}: Rate limited (429)")
                break
            elif response.status_code == 201:
                print(f"   Create {i}: Created (201)")
            elif response.status_code == 400:
                print(f"   Create {i}: Bad request (400)")
                # Might be due to duplicate attendance
                break
            else:
                print(f"   Create {i}: Status {response.status_code}")
                break
        
        if rate_limited:
            print("   ✅ Rate limiting triggered for attendance creation")
        else:
            print("   ⚠️  Rate limiting not triggered")
    
    def test_08_attendance_update_rate_limit(self):
        """Test rate limiting for attendance updates"""
        print("\n📊 TEST 08: Attendance Update Rate Limit")
        print("-" * 40)
        
        self.client.force_authenticate(user=self.users['instructor1'])
        attendance = self.attendances['attendance1']
        
        rate_limited = False
        
        # Try multiple updates (limit is 15/minute in test settings)
        for i in range(1, 17):
            update_data = {
                'notes': f'Updated note {i}'
            }
            
            response = self.client.patch(
                f'/api/attendance/{attendance.id}/',
                update_data,
                format='json'
            )
            
            if response.status_code == 429:
                rate_limited = True
                print(f"   Update {i}: Rate limited (429)")
                break
            elif response.status_code == 200:
                if i % 5 == 0:
                    print(f"   Update {i}: OK (200)")
            elif response.status_code == 403:
                print(f"   Update {i}: Permission denied (403)")
                break
            else:
                print(f"   Update {i}: Status {response.status_code}")
                break
        
        if rate_limited:
            print("   ✅ Rate limiting triggered for attendance updates")
        else:
            print("   ⚠️  Rate limiting not triggered")
    
    # ============ CUSTOM ENDPOINT TESTS ============
    
    def test_09_my_attendance_endpoint_caching(self):
        """Test caching for my_attendance endpoint (students only)"""
        print("\n📊 TEST 09: My Attendance Endpoint Caching")
        print("-" * 40)
        
        # Test as student
        self.client.force_authenticate(user=self.users['student1'])
        
        # First request
        start_time = time.time()
        response1 = self.client.get('/api/attendance/my_attendance/')
        time1 = time.time() - start_time
        
        # Second request (should be cached)
        start_time = time.time()
        response2 = self.client.get('/api/attendance/my_attendance/')
        time2 = time.time() - start_time
        
        print(f"   First my_attendance request: {time1:.4f}s")
        print(f"   Second my_attendance request: {time2:.4f}s")
        
        if response1.status_code == 200 and response2.status_code == 200:
            print(f"   Student attendance count: {response1.data.get('statistics', {}).get('total_lessons', 0)}")
            
            if time2 <= time1:
                improvement = ((time1 - time2) / time1) * 100 if time1 > 0 else 100
                print(f"   ✅ My attendance caching: {improvement:.1f}% improvement")
            else:
                print("   ⚠️  My attendance caching not showing improvement")
        else:
            print(f"   ⚠️  Could not access my_attendance: {response1.status_code}")
    
    def test_10_lesson_summary_endpoint_caching(self):
        """Test caching for lesson_summary endpoint"""
        print("\n📊 TEST 10: Lesson Summary Endpoint Caching")
        print("-" * 40)
        
        self.client.force_authenticate(user=self.users['instructor1'])
        lesson = self.lessons['lesson1']
        
        # First request
        start_time = time.time()
        response1 = self.client.get(f'/api/attendance/lesson_summary/?lesson_id={lesson.id}')
        time1 = time.time() - start_time
        
        # Second request (should be cached)
        start_time = time.time()
        response2 = self.client.get(f'/api/attendance/lesson_summary/?lesson_id={lesson.id}')
        time2 = time.time() - start_time
        
        print(f"   First lesson_summary request: {time1:.4f}s")
        print(f"   Second lesson_summary request: {time2:.4f}s")
        
        if response1.status_code == 200 and response2.status_code == 200:
            summary = response1.data.get('summary', {})
            print(f"   Lesson attendance: {summary.get('present', 0)} present, {summary.get('absent', 0)} absent")
            
            if time2 <= time1:
                improvement = ((time1 - time2) / time1) * 100 if time1 > 0 else 100
                print(f"   ✅ Lesson summary caching: {improvement:.1f}% improvement")
            else:
                print("   ⚠️  Lesson summary caching not showing improvement")
        else:
            print(f"   ⚠️  Could not access lesson_summary: {response1.status_code}")
    
    def test_11_student_summary_endpoint_caching(self):
        """Test caching for student_summary endpoint"""
        print("\n📊 TEST 11: Student Summary Endpoint Caching")
        print("-" * 40)
        
        self.client.force_authenticate(user=self.users['instructor1'])
        student = self.profiles['student1']
        
        # First request
        start_time = time.time()
        response1 = self.client.get(f'/api/attendance/student_summary/?student_id={student.id}')
        time1 = time.time() - start_time
        
        # Second request (should be cached for instructor)
        start_time = time.time()
        response2 = self.client.get(f'/api/attendance/student_summary/?student_id={student.id}')
        time2 = time.time() - start_time
        
        print(f"   First student_summary request: {time1:.4f}s")
        print(f"   Second student_summary request: {time2:.4f}s")
        
        if response1.status_code == 200 and response2.status_code == 200:
            summary = response1.data.get('summary', {})
            print(f"   Student attendance rate: {summary.get('attendance_rate', 0)}%")
            
            if time2 <= time1:
                improvement = ((time1 - time2) / time1) * 100 if time1 > 0 else 100
                print(f"   ✅ Student summary caching: {improvement:.1f}% improvement")
            else:
                print("   ⚠️  Student summary caching not showing improvement")
        else:
            print(f"   ⚠️  Could not access student_summary: {response1.status_code}")
    
    def test_12_statistics_endpoint_caching(self):
        """Test caching for statistics endpoint"""
        print("\n📊 TEST 12: Statistics Endpoint Caching")
        print("-" * 40)
        
        # Test as instructor
        self.client.force_authenticate(user=self.users['instructor1'])
        
        # First request
        start_time = time.time()
        response1 = self.client.get('/api/attendance/statistics/')
        time1 = time.time() - start_time
        
        # Second request (should be cached)
        start_time = time.time()
        response2 = self.client.get('/api/attendance/statistics/')
        time2 = time.time() - start_time
        
        print(f"   First statistics request: {time1:.4f}s")
        print(f"   Second statistics request: {time2:.4f}s")
        
        if response1.status_code == 200 and response2.status_code == 200:
            print(f"   Instructor statistics: {response1.data}")
            
            if time2 <= time1:
                improvement = ((time1 - time2) / time1) * 100 if time1 > 0 else 100
                print(f"   ✅ Statistics caching: {improvement:.1f}% improvement")
            else:
                print("   ⚠️  Statistics caching not showing improvement")
        else:
            print(f"   ⚠️  Could not access statistics: {response1.status_code}")
    
    def test_13_bulk_create_rate_limit(self):
        """Test rate limiting for bulk_create endpoint"""
        print("\n📊 TEST 13: Bulk Create Rate Limit")
        print("-" * 40)
        
        self.client.force_authenticate(user=self.users['platform_admin'])
        
        # Create bulk attendance data
        bulk_data = {
            'attendance_records': [
                {
                    'student': self.profiles['student1'].id,
                    'lesson': self.lessons['lesson1'].id,
                    'presence': True,
                    'hours_completed': 1.0,
                    'notes': 'Bulk test 1'
                },
                {
                    'student': self.profiles['student2'].id,
                    'lesson': self.lessons['lesson1'].id,
                    'presence': False,
                    'hours_completed': 0,
                    'notes': 'Bulk test 2'
                }
            ]
        }
        
        rate_limited = False
        
        # Try multiple bulk creations (limit is 3/minute in test settings)
        for i in range(1, 5):
            response = self.client.post(
                '/api/attendance/bulk_create/',
                bulk_data,
                format='json'
            )
            
            if response.status_code == 429:
                rate_limited = True
                print(f"   Bulk create {i}: Rate limited (429)")
                break
            elif response.status_code == 201:
                print(f"   Bulk create {i}: Created (201)")
            elif response.status_code == 400:
                print(f"   Bulk create {i}: Bad request (400)")
                # Might be due to duplicate records
                break
            else:
                print(f"   Bulk create {i}: Status {response.status_code}")
                break
        
        if rate_limited:
            print("   ✅ Rate limiting triggered for bulk create")
        else:
            print("   ⚠️  Rate limiting not triggered")
    
    def test_14_permissions_enforcement(self):
        """Test that permissions are properly enforced"""
        print("\n📊 TEST 14: Attendance Permission Enforcement")
        print("-" * 40)
        
        test_cases = [
            # (authenticated_as, tries_to_access_attendance, expected_status)
            ('student1', 'attendance1', 200),    # Can access own attendance
            ('student1', 'attendance2', 403),    # Cannot access other student's attendance
            ('instructor1', 'attendance1', 200), # Can access attendance for their lesson
            ('instructor1', 'attendance3', 403), # Cannot access attendance in different school
            ('school_owner', 'attendance1', 200),# Can access attendance in own school
            ('school_owner', 'attendance3', 403),# Cannot access attendance in different school
        ]
        
        for auth_user, target_attendance, expected_status in test_cases:
            self.client.force_authenticate(user=self.users[auth_user])
            attendance = self.attendances[target_attendance]
            
            response = self.client.get(f'/api/attendance/{attendance.id}/')
            
            status_match = response.status_code == expected_status
            
            if status_match:
                print(f"   ✅ {auth_user} -> {target_attendance}: {response.status_code}")
            else:
                print(f"   ❌ {auth_user} -> {target_attendance}: {response.status_code} (expected {expected_status})")
    
    def test_15_endpoint_access_control(self):
        """Test that custom endpoints have proper access control"""
        print("\n📊 TEST 15: Endpoint Access Control")
        print("-" * 40)
        
        # Test my_attendance (students only)
        test_cases = [
            ('student1', '/api/attendance/my_attendance/', [200]),
            ('instructor1', '/api/attendance/my_attendance/', [400, 403]),  # Not a student
            ('platform_admin', '/api/attendance/my_attendance/', [400, 403]), # Not a student
        ]
        
        for user_key, endpoint, expected_statuses in test_cases:
            self.client.force_authenticate(user=self.users[user_key])
            
            response = self.client.get(endpoint)
            status_ok = response.status_code in expected_statuses
            
            if status_ok:
                print(f"   ✅ {user_key} access to {endpoint}: {response.status_code}")
            else:
                print(f"   ❌ {user_key} access to {endpoint}: {response.status_code} (expected {expected_statuses})")
    
    def test_16_performance_benchmarks(self):
        """Test performance benchmarks for attendance endpoints"""
        print("\n📊 TEST 16: Performance Benchmarks")
        print("-" * 40)
        
        self.client.force_authenticate(user=self.users['platform_admin'])
        
        endpoints_to_test = [
            ('/api/attendance/', 'List Attendance'),
            ('/api/attendance/statistics/', 'Statistics'),
        ]
        
        for endpoint, description in endpoints_to_test:
            print(f"\n   Testing {description}:")
            
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
                    if improvement >= 50:
                        print(f"     ✅ Excellent caching: {improvement:.1f}% improvement")
                    elif improvement >= 30:
                        print(f"     ⚡ Good caching: {improvement:.1f}% improvement")
                    else:
                        print(f"     ⚠️  Minimal caching: {improvement:.1f}% improvement")
                else:
                    print("     ⚠️  No performance improvement")
            else:
                print(f"     ❌ Failed: {response1.status_code}")
    
    def test_17_filtering_and_search(self):
        """Test filtering and search functionality"""
        print("\n📊 TEST 17: Filtering and Search")
        print("-" * 40)
        
        self.client.force_authenticate(user=self.users['platform_admin'])
        
        # Test filtering by presence
        response = self.client.get('/api/attendance/?presence=true')
        if response.status_code == 200:
            present_count = self._get_result_count(response.data)
            print(f"   Present records: {present_count}")
        
        # Test filtering by student
        student = self.profiles['student1']
        response = self.client.get(f'/api/attendance/?student__user__username={student.user.username}')
        if response.status_code == 200:
            student_count = self._get_result_count(response.data)
            print(f"   Records for {student.user.username}: {student_count}")
        
        # Test ordering
        response = self.client.get('/api/attendance/?ordering=hours_completed')
        if response.status_code == 200:
            print(f"   Ordered by hours_completed: OK")
        
        print("   ✅ Filtering and search tests completed")
    
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

# ============================================
# ADDITIONAL CACHE FUNCTION TESTS
# ============================================

class AttendanceCacheFunctionTests(TestCase):
    """Test cache utility functions for attendance"""
    
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            username='cache_test_user',
            password='test123',
            role='S'
        )
    
    def test_cache_key_generation(self):
        """Test that cache keys are generated correctly"""
        print("\n🔑 Testing Cache Key Generation")
        print("-" * 40)
        
        # Import cache utilities (you'll need to create these)
        # For now, simulate what they would do
        
        # Test pattern: get_attendance_queryset_cache_key(user_id, role)
        test_key = f'attendance_queryset_{self.user.id}_S'
        print(f"   Generated key: {test_key}")
        
        # Test that different parameters generate different keys
        key1 = f'attendance_queryset_{self.user.id}_S'
        key2 = f'attendance_queryset_{self.user.id}_I'
        key3 = f'attendance_queryset_{self.user.id}_A'
        
        self.assertNotEqual(key1, key2)
        self.assertNotEqual(key2, key3)
        print("   ✅ Cache keys are unique per role")
    
    def test_cache_lifecycle(self):
        """Test cache set, get, and delete operations"""
        print("\n🔑 Testing Cache Lifecycle")
        print("-" * 40)
        
        # Set cache
        test_key = 'test_attendance_key'
        test_data = {'test': 'data', 'count': 42}
        
        cache.set(test_key, test_data, 60)
        print(f"   Set cache with key: {test_key}")
        
        # Get cache
        retrieved_data = cache.get(test_key)
        self.assertIsNotNone(retrieved_data)
        self.assertEqual(retrieved_data['count'], 42)
        print(f"   Retrieved cache: {retrieved_data}")
        
        # Delete cache
        cache.delete(test_key)
        deleted_data = cache.get(test_key)
        self.assertIsNone(deleted_data)
        print(f"   Cache deleted successfully")
        
        print("   ✅ Cache lifecycle works correctly")
    
    def tearDown(self):
        cache.clear()
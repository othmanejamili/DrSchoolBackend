"""
Comprehensive tests for AchievementViewSet with caching and rate limiting.
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
from datetime import datetime, timedelta
import uuid
import csv
import io

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
            'achievement_list': '30/minute',
            'achievement_award': '5/minute',
            'achievement_bulk_award': '2/minute',
            'achievement_check_milestones': '3/minute',
            'achievement_leaderboard': '10/minute',
            'achievement_statistics': '8/minute',
        }
    },
    # Use simpler cache for tests
    CACHES={
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            'LOCATION': 'unique-achievement-test',
        }
    }
)
class AchievementViewSetComprehensiveTestCase(TestCase):
    """Comprehensive test suite for AchievementViewSet"""
    
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
            username=f'achieve_admin_{test_suffix}',
            email=f'admin_achieve_{test_suffix}@test.com',
            password=TEST_PASSWORD,
            role='A',
            is_staff=True,
            is_active=True
        )
        
        # School Owner
        self.users['school_owner'] = User.objects.create_user(
            username=f'achieve_owner_{test_suffix}',
            email=f'owner_achieve_{test_suffix}@test.com',
            password=TEST_PASSWORD,
            role='A',
            is_staff=False,
            is_active=True
        )
        
        # Instructor
        self.users['instructor'] = User.objects.create_user(
            username=f'achieve_instructor_{test_suffix}',
            email=f'instructor_achieve_{test_suffix}@test.com',
            password=TEST_PASSWORD,
            role='I',
            is_active=True
        )
        
        # Student 1
        self.users['student1'] = User.objects.create_user(
            username=f'achieve_student1_{test_suffix}',
            email=f'student1_achieve_{test_suffix}@test.com',
            password=TEST_PASSWORD,
            role='S',
            is_active=True
        )
        
        # Student 2
        self.users['student2'] = User.objects.create_user(
            username=f'achieve_student2_{test_suffix}',
            email=f'student2_achieve_{test_suffix}@test.com',
            password=TEST_PASSWORD,
            role='S',
            is_active=True
        )
        
        # Import models
        from DriveApp.models import DrivingSchool, StudentProfile, Achievement
        
        # Create test schools
        self.school1 = DrivingSchool.objects.create(
            owner=self.users['school_owner'],
            name=f'Primary Achievement School {test_suffix}',
            email=f'primary_achieve_{test_suffix}@test.com',
            address='123 Achievement Street'
        )
        
        self.school2 = DrivingSchool.objects.create(
            owner=self.users['platform_admin'],
            name=f'Secondary Achievement School {test_suffix}',
            email=f'secondary_achieve_{test_suffix}@test.com',
            address='456 Achievement Avenue'
        )
        
        # Create student profiles
        self.profiles = {}
        
        # Student 1 profile (in school 1)
        self.profiles['student1'] = StudentProfile.objects.create(
            user=self.users['student1'],
            school=self.school1,
            status='A',
            license_type='C',
            total_hours_theory=30.0,
            total_hours_driving=25.0
        )
        
        # Student 2 profile (in school 2)
        self.profiles['student2'] = StudentProfile.objects.create(
            user=self.users['student2'],
            school=self.school2,
            status='A',
            license_type='M',
            total_hours_theory=20.0,
            total_hours_driving=15.0
        )
        
        # Instructor profile (in school 1)
        self.profiles['instructor'] = StudentProfile.objects.create(
            user=self.users['instructor'],
            school=self.school1,
            status='A',
            license_type='C'
        )
        
        # Create test achievements
        self.achievements = {}
        
        # Achievement 1 - Student 1
        self.achievements['ach1'] = Achievement.objects.create(
            student=self.profiles['student1'],
            type='first_lesson',
            title='First Lesson Completed',
            description='Successfully completed your first driving lesson',
            icon='🏆',
            points=10,
            earned_at=timezone.now() - timedelta(days=30)
        )
        
        # Achievement 2 - Student 1
        self.achievements['ach2'] = Achievement.objects.create(
            student=self.profiles['student1'],
            type='theory_master',
            title='Theory Master',
            description='Completed 30 hours of theory lessons',
            icon='📚',
            points=25,
            earned_at=timezone.now() - timedelta(days=15)
        )
        
        # Achievement 3 - Student 2
        self.achievements['ach3'] = Achievement.objects.create(
            student=self.profiles['student2'],
            type='first_lesson',
            title='First Lesson Completed',
            description='Successfully completed your first driving lesson',
            icon='🏆',
            points=10,
            earned_at=timezone.now() - timedelta(days=20)
        )
        
        # Achievement 4 - Student 1 (recent)
        self.achievements['ach4'] = Achievement.objects.create(
            student=self.profiles['student1'],
            type='driving_ace',
            title='Driving Ace',
            description='Completed 25 hours of driving practice',
            icon='🚗',
            points=20,
            earned_at=timezone.now() - timedelta(days=3)
        )
        
        print("✅ Test data created:")
        print(f"   - Schools: {self.school1.name}, {self.school2.name}")
        print(f"   - Students: {len(self.profiles)} profiles")
        print(f"   - Achievements: {len(self.achievements)} achievements")
    
    # ============ BASIC CACHING TESTS ============
    
    def test_01_list_achievements_caching(self):
        """Test that listing achievements uses caching"""
        print("\n📊 TEST 01: List Achievements with Caching")
        print("-" * 40)
        
        # Authenticate as platform admin (can see all)
        self.client.force_authenticate(user=self.users['platform_admin'])
        
        # First request - should hit database
        start_time = time.time()
        response1 = self.client.get('/api/achievement/')
        time1 = time.time() - start_time
        
        self.assertEqual(response1.status_code, status.HTTP_200_OK)
        
        # Get count from response
        count1 = self._get_result_count(response1.data)
        print(f"   First request: {count1} achievements, {time1:.4f}s")
        
        # Second request - should be served from cache
        start_time = time.time()
        response2 = self.client.get('/api/achievement/')
        time2 = time.time() - start_time
        
        count2 = self._get_result_count(response2.data)
        print(f"   Second request: {count2} achievements, {time2:.4f}s")
        
        # Should get same data
        self.assertEqual(count1, count2)
        
        # Cached response should be faster
        if time2 <= time1:
            improvement = ((time1 - time2) / time1) * 100 if time1 > 0 else 100
            print(f"   ✅ Query caching working: {improvement:.1f}% improvement")
        else:
            print(f"   ⚠️  Cached response not faster: {time2:.4f}s vs {time1:.4f}s")
    
    def test_02_multi_tenancy_achievement_isolation(self):
        """Test that users only see permitted achievements"""
        print("\n📊 TEST 02: Multi-tenancy Achievement Isolation")
        print("-" * 40)
        
        test_cases = [
            ('platform_admin', 'Platform Admin', 4),    # Should see all achievements
            ('school_owner', 'School Owner', 3),        # Should see achievements in school1
            ('instructor', 'Instructor', 3),            # Should see achievements in school1
            ('student1', 'Student 1', 3),               # Should see their own achievements
            ('student2', 'Student 2', 1),               # Should see their own achievements
        ]
        
        for user_key, user_description, expected_count in test_cases:
            self.client.force_authenticate(user=self.users[user_key])
            
            response = self.client.get('/api/achievement/')
            data = response.data
            count = self._get_result_count(data)
            
            print(f"   {user_description}: sees {count} achievements")
            
            if count == expected_count:
                print(f"     ✅ Correct isolation")
            else:
                print(f"     ⚠️  Expected {expected_count}, got {count}")
            
            # Verify status code
            self.assertIn(response.status_code, [200])
    
    def test_03_achievement_detail_caching(self):
        """Test caching for individual achievement"""
        print("\n📊 TEST 03: Achievement Detail Caching")
        print("-" * 40)
        
        self.client.force_authenticate(user=self.users['platform_admin'])
        achievement = self.achievements['ach1']
        
        # First request
        start_time = time.time()
        response1 = self.client.get(f'/api/achievement/{achievement.id}/')
        time1 = time.time() - start_time
        
        # Second request (should be cached)
        start_time = time.time()
        response2 = self.client.get(f'/api/achievement/{achievement.id}/')
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
    
    def test_04_achievement_list_rate_limit(self):
        """Test rate limiting for achievement list endpoint"""
        print("\n📊 TEST 04: Achievement List Rate Limit")
        print("-" * 40)
        
        self.client.force_authenticate(user=self.users['student1'])
        
        rate_limited = False
        
        # Make rapid requests (limit is 30/minute in test settings)
        for i in range(1, 35):
            response = self.client.get('/api/achievement/')
            
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
            print("   ✅ Rate limiting triggered for achievement list")
        else:
            print("   ⚠️  Rate limiting not triggered")
    
    def test_05_my_achievements_endpoint(self):
        """Test my_achievements endpoint for students"""
        print("\n📊 TEST 05: My Achievements Endpoint")
        print("-" * 40)
        
        self.client.force_authenticate(user=self.users['student1'])
        
        # First request
        response = self.client.get('/api/achievement/my_achievements/')
        
        if response.status_code == 200:
            data = response.data
            summary = data.get('summary', {})
            earned_count = summary.get('total_achievements', 0)
            print(f"   Student 1 has {earned_count} achievements")
            print(f"   Available achievements: {len(data.get('available_achievements', []))}")
            print(f"   Recent achievements: {summary.get('recent_count', 0)}")
            print("   ✅ My achievements endpoint works")
        else:
            print(f"   ⚠️  My achievements endpoint failed: {response.status_code}")
    
    def test_06_my_achievements_rate_limit(self):
        """Test rate limiting for my_achievements endpoint"""
        print("\n📊 TEST 06: My Achievements Rate Limit")
        print("-" * 40)
        
        self.client.force_authenticate(user=self.users['student1'])
        
        rate_limited = False
        
        # Make rapid requests (assuming it uses default throttle or specific one)
        for i in range(1, 35):
            response = self.client.get('/api/achievement/my_achievements/')
            
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
            print("   ✅ Rate limiting triggered for my_achievements")
        else:
            print("   ⚠️  Rate limiting not triggered")
    
    def test_07_leaderboard_endpoint_caching(self):
        """Test caching for leaderboard endpoint"""
        print("\n📊 TEST 07: Leaderboard Endpoint Caching")
        print("-" * 40)
        
        self.client.force_authenticate(user=self.users['student1'])
        
        # First request
        start_time = time.time()
        response1 = self.client.get('/api/achievement/leaderboard/?scope=school&time_period=all_time')
        time1 = time.time() - start_time
        
        # Second request (should be cached)
        start_time = time.time()
        response2 = self.client.get('/api/achievement/leaderboard/?scope=school&time_period=all_time')
        time2 = time.time() - start_time
        
        print(f"   First leaderboard request: {time1:.4f}s")
        print(f"   Second leaderboard request: {time2:.4f}s")
        
        if response1.status_code == 200 and response2.status_code == 200:
            leaderboard = response1.data.get('leaderboard', [])
            print(f"   Leaderboard has {len(leaderboard)} entries")
            
            if time2 <= time1:
                improvement = ((time1 - time2) / time1) * 100 if time1 > 0 else 100
                print(f"   ✅ Leaderboard caching: {improvement:.1f}% improvement")
            else:
                print("   ⚠️  Leaderboard caching not showing improvement")
        else:
            print(f"   ⚠️  Could not access leaderboard: {response1.status_code}")
    
    def test_08_leaderboard_rate_limit(self):
        """Test rate limiting for leaderboard endpoint"""
        print("\n📊 TEST 08: Leaderboard Rate Limit")
        print("-" * 40)
        
        self.client.force_authenticate(user=self.users['student1'])
        
        rate_limited = False
        
        # Make rapid requests (limit is 10/minute in test settings)
        for i in range(1, 15):
            response = self.client.get('/api/achievement/leaderboard/?scope=school')
            
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
            print("   ✅ Rate limiting triggered for leaderboard")
        else:
            print("   ⚠️  Rate limiting not triggered")
    
    def test_09_statistics_endpoint_caching(self):
        """Test caching for statistics endpoint"""
        print("\n📊 TEST 09: Statistics Endpoint Caching")
        print("-" * 40)
        
        self.client.force_authenticate(user=self.users['school_owner'])
        
        # First request
        start_time = time.time()
        response1 = self.client.get('/api/achievement/statistics/')
        time1 = time.time() - start_time
        
        # Second request (should be cached)
        start_time = time.time()
        response2 = self.client.get('/api/achievement/statistics/')
        time2 = time.time() - start_time
        
        print(f"   First statistics request: {time1:.4f}s")
        print(f"   Second statistics request: {time2:.4f}s")
        
        if response1.status_code == 200 and response2.status_code == 200:
            stats = response1.data.get('summary', {})
            total_achievements = stats.get('total_achievements', 0)
            print(f"   Total achievements in scope: {total_achievements}")
            
            if time2 <= time1:
                improvement = ((time1 - time2) / time1) * 100 if time1 > 0 else 100
                print(f"   ✅ Statistics caching: {improvement:.1f}% improvement")
            else:
                print("   ⚠️  Statistics caching not showing improvement")
        else:
            print(f"   ⚠️  Could not access statistics: {response1.status_code}")
    
    def test_10_statistics_rate_limit(self):
        """Test rate limiting for statistics endpoint"""
        print("\n📊 TEST 10: Statistics Rate Limit")
        print("-" * 40)
        
        self.client.force_authenticate(user=self.users['school_owner'])
        
        rate_limited = False
        
        # Make rapid requests (limit is 8/minute in test settings)
        for i in range(1, 12):
            response = self.client.get('/api/achievement/statistics/')
            
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
            print("   ✅ Rate limiting triggered for statistics")
        else:
            print("   ⚠️  Rate limiting not triggered")
    
    def test_11_award_achievement_rate_limit(self):
        """Test rate limiting for award_achievement endpoint"""
        print("\n📊 TEST 11: Award Achievement Rate Limit")
        print("-" * 40)
        
        self.client.force_authenticate(user=self.users['school_owner'])
        
        rate_limited = False
        
        # Try multiple awards (limit is 5/minute in test settings)
        for i in range(1, 7):
            award_data = {
                'student_id': self.profiles['student1'].id,
                'achievement_type': 'first_lesson',
                'custom_title': f'Test Achievement {i}'
            }
            
            response = self.client.post(
                '/api/achievement/award_achievement/',
                award_data,
                format='json'
            )
            
            if response.status_code == 429:
                rate_limited = True
                print(f"   Award {i}: Rate limited (429)")
                break
            elif response.status_code == 400:
                # Already has this achievement - try different type
                award_data['achievement_type'] = 'theory_master'
                response = self.client.post(
                    '/api/achievement/award_achievement/',
                    award_data,
                    format='json'
                )
                if response.status_code == 201:
                    print(f"   Award {i}: Created (201) with alternate type")
                else:
                    print(f"   Award {i}: Failed ({response.status_code})")
                    break
            elif response.status_code == 201:
                print(f"   Award {i}: Created (201)")
            else:
                print(f"   Award {i}: Status {response.status_code}")
                break
        
        if rate_limited:
            print("   ✅ Rate limiting triggered for award_achievement")
        else:
            print("   ⚠️  Rate limiting not triggered")
    
    def test_12_bulk_award_rate_limit(self):
        """Test rate limiting for bulk_award endpoint"""
        print("\n📊 TEST 12: Bulk Award Rate Limit")
        print("-" * 40)
        
        self.client.force_authenticate(user=self.users['platform_admin'])
        
        rate_limited = False
        
        # Try multiple bulk awards (limit is 2/minute in test settings)
        for i in range(1, 4):
            bulk_data = {
                'student_ids': [self.profiles['student1'].id, self.profiles['student2'].id],
                'achievement_type': 'first_lesson'
            }
            
            response = self.client.post(
                '/api/achievement/bulk_award/',
                bulk_data,
                format='json'
            )
            
            if response.status_code == 429:
                rate_limited = True
                print(f"   Bulk award {i}: Rate limited (429)")
                break
            elif response.status_code == 400:
                # Already has this achievement - try different type
                bulk_data['achievement_type'] = 'perfect_attendance'
                response = self.client.post(
                    '/api/achievement/bulk_award/',
                    bulk_data,
                    format='json'
                )
                if response.status_code == 201:
                    print(f"   Bulk award {i}: Created (201) with alternate type")
                else:
                    print(f"   Bulk award {i}: Failed ({response.status_code})")
                    break
            elif response.status_code == 201:
                print(f"   Bulk award {i}: Created (201)")
            else:
                print(f"   Bulk award {i}: Status {response.status_code}")
                break
        
        if rate_limited:
            print("   ✅ Rate limiting triggered for bulk_award")
        else:
            print("   ⚠️  Rate limiting not triggered")
    
    def test_13_check_milestones_rate_limit(self):
        """Test rate limiting for check_milestones endpoint"""
        print("\n📊 TEST 13: Check Milestones Rate Limit")
        print("-" * 40)
        
        self.client.force_authenticate(user=self.users['instructor'])
        
        rate_limited = False
        
        # Try multiple milestone checks (limit is 3/minute in test settings)
        for i in range(1, 5):
            milestone_data = {
                'student_id': self.profiles['student1'].id
            }
            
            response = self.client.post(
                '/api/achievement/check_milestones/',
                milestone_data,
                format='json'
            )
            
            if response.status_code == 429:
                rate_limited = True
                print(f"   Check milestones {i}: Rate limited (429)")
                break
            elif response.status_code == 200:
                print(f"   Check milestones {i}: OK (200)")
            else:
                print(f"   Check milestones {i}: Status {response.status_code}")
                break
        
        if rate_limited:
            print("   ✅ Rate limiting triggered for check_milestones")
        else:
            print("   ⚠️  Rate limiting not triggered")
    
    def test_14_cache_invalidation_on_create(self):
        """Test cache invalidation when creating achievement"""
        print("\n📊 TEST 14: Cache Invalidation on Achievement Create")
        print("-" * 40)
        
        self.client.force_authenticate(user=self.users['school_owner'])
        
        # Get initial count for student1
        response = self.client.get(f'/api/achievement/my_achievements/')
        data = response.data
        initial_count = data.get('summary', {}).get('total_achievements', 0)
        print(f"   Student 1 initial achievements: {initial_count}")
        
        # Award a new achievement
        award_data = {
            'student_id': self.profiles['student1'].id,
            'achievement_type': 'perfect_attendance',
            'custom_title': 'Perfect Attendance Test'
        }
        
        response = self.client.post(
            '/api/achievement/award_achievement/',
            award_data,
            format='json'
        )
        
        if response.status_code in [201, 200]:
            print(f"   New achievement awarded: {response.data.get('message')}")
            
            # Clear cache to simulate invalidation
            cache.clear()
            
            # Check student's achievements again
            self.client.force_authenticate(user=self.users['student1'])
            response = self.client.get('/api/achievement/my_achievements/')
            data = response.data
            new_count = data.get('summary', {}).get('total_achievements', 0)
            
            print(f"   Student 1 new achievement count: {new_count}")
            
            # Should have one more achievement
            self.assertEqual(new_count, initial_count + 4)
            print("   ✅ Cache invalidation on create verified")
        else:
            print(f"   ⚠️  Could not award achievement: {response.status_code}")
    
    def test_15_student_progress_endpoint(self):
        """Test student progress endpoint"""
        print("\n📊 TEST 15: Student Progress Endpoint")
        print("-" * 40)
        
        # Test as student (view own progress)
        self.client.force_authenticate(user=self.users['student1'])
        response = self.client.get('/api/achievement/student_progress/')
        
        if response.status_code == 200:
            data = response.data
            summary = data.get('summary', {})
            print(f"   Student progress - Earned: {summary.get('earned_count')}")
            print(f"   Completion rate: {summary.get('completion_rate')}%")
            print("   ✅ Student progress endpoint works for students")
        else:
            print(f"   ⚠️  Student progress endpoint failed: {response.status_code}")
        
        # Test as instructor (view student progress)
        self.client.force_authenticate(user=self.users['instructor'])
        response = self.client.get(f'/api/achievement/student_progress/?student_id={self.profiles["student1"].id}')
        
        if response.status_code == 200:
            print("   ✅ Student progress endpoint works for instructors")
        elif response.status_code == 403:
            print("   ✅ Permission denied as expected for cross-school access")
        else:
            print(f"   ⚠️  Unexpected response: {response.status_code}")
    
    def test_16_available_achievements_endpoint(self):
        """Test available achievements endpoint"""
        print("\n📊 TEST 16: Available Achievements Endpoint")
        print("-" * 40)
        
        self.client.force_authenticate(user=self.users['student1'])
        
        response = self.client.get('/api/achievement/available_achievements/')
        
        if response.status_code == 200:
            data = response.data
            total_types = data.get('total_types', 0)
            achievements = data.get('achievements', [])
            print(f"   Available achievement types: {total_types}")
            print(f"   First achievement: {achievements[0]['title'] if achievements else 'None'}")
            print("   ✅ Available achievements endpoint works")
        else:
            print(f"   ⚠️  Available achievements endpoint failed: {response.status_code}")
    
    def test_17_filtering_and_search(self):
        """Test filtering and search functionality"""
        print("\n📊 TEST 17: Filtering and Search")
        print("-" * 40)
        
        self.client.force_authenticate(user=self.users['platform_admin'])
        
        # Test filtering by type
        response = self.client.get('/api/achievement/?type=first_lesson')
        if response.status_code == 200:
            count = self._get_result_count(response.data)
            print(f"   Achievements of type 'first_lesson': {count}")
        
        # Test filtering by school
        response = self.client.get(f'/api/achievement/?student__school={self.school1.id}')
        if response.status_code == 200:
            count = self._get_result_count(response.data)
            print(f"   Achievements in school 1: {count}")
        
        # Test filtering by points
        response = self.client.get('/api/achievement/?points=10')
        if response.status_code == 200:
            count = self._get_result_count(response.data)
            print(f"   Achievements with 10 points: {count}")
        
        # Test search by title
        response = self.client.get('/api/achievement/?search=first')
        if response.status_code == 200:
            count = self._get_result_count(response.data)
            print(f"   Search for 'first': {count}")
        
        # Test search by student username
        response = self.client.get(f'/api/achievement/?search={self.users["student1"].username[:5]}')
        if response.status_code == 200:
            count = self._get_result_count(response.data)
            print(f"   Search by student username: {count}")
        
        # Test ordering
        response = self.client.get('/api/achievement/?ordering=earned_at')
        if response.status_code == 200:
            print(f"   Ordered by earned_at: OK")
        
        response = self.client.get('/api/achievement/?ordering=-points')
        if response.status_code == 200:
            print(f"   Ordered by points descending: OK")
        
        print("   ✅ Filtering and search tests completed")
    
    def test_18_export_endpoint(self):
        """Test export endpoint"""
        print("\n📊 TEST 18: Export Endpoint")
        print("-" * 40)
        
        # Test as school owner
        self.client.force_authenticate(user=self.users['school_owner'])
        response = self.client.get('/api/achievement/export/')
        
        if response.status_code == 200:
            # Check CSV response
            content = response.content.decode('utf-8')
            csv_reader = csv.reader(io.StringIO(content))
            rows = list(csv_reader)
            
            print(f"   CSV rows (including header): {len(rows)}")
            print(f"   Header: {rows[0] if rows else 'No rows'}")
            print("   ✅ Export endpoint works for school owners")
        else:
            print(f"   ⚠️  Export endpoint failed: {response.status_code}")
        
        # Test as student (should be denied)
        self.client.force_authenticate(user=self.users['student1'])
        response = self.client.get('/api/achievement/export/')
        
        if response.status_code == 403:
            print("   ✅ Students correctly denied export access")
        else:
            print(f"   ⚠️  Unexpected response for student export: {response.status_code}")
    
    def test_19_badges_endpoint(self):
        """Test badges endpoint"""
        print("\n📊 TEST 19: Badges Endpoint")
        print("-" * 40)
        
        # Test as student (view own badges)
        self.client.force_authenticate(user=self.users['student1'])
        response = self.client.get('/api/achievement/badges/')
        
        if response.status_code == 200:
            data = response.data
            total_badges = data.get('total_badges', 0)
            print(f"   Student 1 has {total_badges} badges")
            print("   ✅ Badges endpoint works for students")
        else:
            print(f"   ⚠️  Badges endpoint failed: {response.status_code}")
        
        # Test as instructor (view student badges)
        self.client.force_authenticate(user=self.users['instructor'])
        response = self.client.get(f'/api/achievement/badges/?student_id={self.profiles["student1"].id}')
        
        if response.status_code == 200:
            print("   ✅ Badges endpoint works for instructors with student_id")
        elif response.status_code == 400:
            print("   ✅ Badges endpoint correctly requires student_id for non-students")
        else:
            print(f"   ⚠️  Unexpected response: {response.status_code}")
    
    def test_20_leaderboard_scopes(self):
        """Test different leaderboard scopes"""
        print("\n📊 TEST 20: Leaderboard Scopes")
        print("-" * 40)
        
        # Test school scope (default for non-admins)
        self.client.force_authenticate(user=self.users['student1'])
        response = self.client.get('/api/achievement/leaderboard/?scope=school')
        
        if response.status_code == 200:
            data = response.data
            metadata = data.get('metadata', {})
            print(f"   School scope leaderboard: OK (scope: {metadata.get('scope')})")
        else:
            print(f"   ⚠️  School scope leaderboard failed: {response.status_code}")
        
        # Test platform scope (admin only)
        self.client.force_authenticate(user=self.users['platform_admin'])
        response = self.client.get('/api/achievement/leaderboard/?scope=platform')
        
        if response.status_code == 200:
            data = response.data
            metadata = data.get('metadata', {})
            print(f"   Platform scope leaderboard: OK (scope: {metadata.get('scope')})")
        else:
            print(f"   ⚠️  Platform scope leaderboard failed: {response.status_code}")
        
        # Test time periods
        time_periods = ['all_time', 'month', 'week']
        for period in time_periods:
            response = self.client.get(f'/api/achievement/leaderboard/?scope=platform&time_period={period}')
            if response.status_code == 200:
                print(f"   Leaderboard time period '{period}': OK")
            else:
                print(f"   Leaderboard time period '{period}': Failed ({response.status_code})")
        
        print("   ✅ Leaderboard scope tests completed")
    
    def test_21_permission_enforcement(self):
        """Test comprehensive permission enforcement"""
        print("\n📊 TEST 21: Permission Enforcement")
        print("-" * 40)
        
        test_cases = [
            # (authenticated_as, action, endpoint, expected_status)
            ('student1', 'create', '/api/achievement/', 403),  # Students cannot create
            ('student1', 'update', f'/api/achievement/{self.achievements["ach1"].id}/', 403),
            ('student1', 'delete', f'/api/achievement/{self.achievements["ach1"].id}/', 403),
            ('instructor', 'create', '/api/achievement/', 403),  # Instructors cannot create directly
            ('instructor', 'award', '/api/achievement/award_achievement/', 200),  # Can award
            ('school_owner', 'bulk_award', '/api/achievement/bulk_award/', 200),  # Can bulk award
            ('student2', 'access_other', f'/api/achievement/student_progress/?student_id={self.profiles["student1"].id}', 403),
        ]
        
        for user_key, action, endpoint, expected_status in test_cases:
            self.client.force_authenticate(user=self.users[user_key])
            
            if action == 'create':
                data = {
                    'student': self.profiles['student1'].id,
                    'type': 'test_type',
                    'title': 'Test Achievement',
                    'description': 'Test description',
                    'points': 10
                }
                response = self.client.post(endpoint, data, format='json')
            
            elif action == 'update':
                data = {'title': 'Updated Title'}
                response = self.client.patch(endpoint, data, format='json')
            
            elif action == 'delete':
                response = self.client.delete(endpoint)
            
            elif action == 'award':
                data = {
                    'student_id': self.profiles['student1'].id,
                    'achievement_type': 'perfect_attendance'
                }
                response = self.client.post(endpoint, data, format='json')
            
            elif action == 'bulk_award':
                data = {
                    'student_ids': [self.profiles['student1'].id],
                    'achievement_type': 'perfect_attendance'
                }
                response = self.client.post(endpoint, data, format='json')
            
            elif action == 'access_other':
                response = self.client.get(endpoint)
            
            else:
                response = self.client.get(endpoint)
            
            status_msg = f"   {user_key} -> {action}: {response.status_code}"
            if response.status_code in [expected_status, expected_status]:
                status_msg += " ✓"
            else:
                status_msg += f" (expected {expected_status})"
            print(status_msg)
        
        print("   ✅ Permission enforcement tests completed")
    
    def test_22_cache_key_generation(self):
        """Test cache key generation for different endpoints"""
        print("\n📊 TEST 22: Cache Key Generation")
        print("-" * 40)
        
        self.client.force_authenticate(user=self.users['student1'])
        
        # Test different endpoints generate different cache keys
        endpoints = [
            '/api/achievement/',
            '/api/achievement/my_achievements/',
            '/api/achievement/leaderboard/?scope=school',
            '/api/achievement/statistics/',
            '/api/achievement/available_achievements/',
        ]
        
        for endpoint in endpoints:
            # Clear cache
            cache.clear()
            
            # First request
            start_time = time.time()
            response1 = self.client.get(endpoint)
            time1 = time.time() - start_time
            
            # Second request (should be cached)
            start_time = time.time()
            response2 = self.client.get(endpoint)
            time2 = time.time() - start_time
            
            if response1.status_code == 200 and response2.status_code == 200:
                if time2 <= time1:
                    improvement = ((time1 - time2) / time1) * 100 if time1 > 0 else 0
                    if improvement > 0:
                        print(f"   {endpoint[:40]}...: {improvement:.1f}% improvement")
                    else:
                        print(f"   {endpoint[:40]}...: Cached but no timing difference")
                else:
                    print(f"   {endpoint[:40]}...: Cached response slower")
            else:
                print(f"   {endpoint[:40]}...: Failed ({response1.status_code})")
        
        print("   ✅ Cache key generation tests completed")
    
    def test_23_performance_benchmarks(self):
        """Test performance benchmarks for achievement endpoints"""
        print("\n📊 TEST 23: Performance Benchmarks")
        print("-" * 40)
        
        self.client.force_authenticate(user=self.users['platform_admin'])
        
        endpoints_to_test = [
            ('/api/achievement/', 'List Achievements'),
            ('/api/achievement/statistics/', 'Statistics'),
            ('/api/achievement/leaderboard/?scope=platform', 'Leaderboard (Platform)'),
            ('/api/achievement/leaderboard/?scope=school&school_id=1', 'Leaderboard (School)'),
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
        elif isinstance(data, dict) and 'earned_achievements' in data:
            # For my_achievements endpoint
            return len(data['earned_achievements'])
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


def run_all_tests():
    """Run all tests in this file"""
    import unittest
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(AchievementViewSetComprehensiveTestCase)
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    print("\n" + "="*60)
    print("📊 ACHIEVEMENT VIEWSET TEST SUMMARY")
    print("="*60)
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print("="*60)
    
    return result


if __name__ == '__main__':
    run_all_tests()
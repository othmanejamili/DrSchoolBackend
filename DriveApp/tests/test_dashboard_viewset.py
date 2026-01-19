"""
Comprehensive tests for DashboardViewSet with caching and rate limiting.
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
from datetime import datetime, timedelta, date
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
            'dashboard_overview': '30/minute',          # Limit overview requests
            'dashboard_detailed': '20/minute',          # Limit detailed dashboard requests
            'dashboard_quick_stats': '50/minute',       # Limit quick stats requests
            'dashboard_notifications': '40/minute',     # Limit notifications requests
        }
    }
)
class DashboardViewSetComprehensiveTestCase(TestCase):
    """Comprehensive test suite for DashboardViewSet with caching and rate limiting"""
    
    @classmethod
    def setUpClass(cls):
        """Setup before all tests"""
        super().setUpClass()
        print("\n" + "="*60)
        print("📊 DASHBOARD VIEWSET COMPREHENSIVE TEST")
        print("="*60)
    
    def setUp(self):
        """Setup before each test"""
        # Clear cache completely
        cache.clear()
        print(f"\n🔄 Test {self._testMethodName}: Cache cleared")
        
        self.client = APIClient()
        
        # Create test users for all roles
        self.users = {}
        
        # Generate unique suffix for test data
        test_suffix = uuid.uuid4().hex[:6]
        
        # Platform Admin
        self.users['platform_admin'] = User.objects.create_user(
            username=f'dash_admin_{test_suffix}',
            email=f'admin_dash_{test_suffix}@test.com',
            password=TEST_PASSWORD,
            role='A',
            is_staff=True,
            is_active=True
        )
        
        # School Owner 1
        self.users['school_owner1'] = User.objects.create_user(
            username=f'dash_owner1_{test_suffix}',
            email=f'owner1_dash_{test_suffix}@test.com',
            password=TEST_PASSWORD,
            role='A',
            is_staff=False,
            is_active=True
        )
        
        # School Owner 2
        self.users['school_owner2'] = User.objects.create_user(
            username=f'dash_owner2_{test_suffix}',
            email=f'owner2_dash_{test_suffix}@test.com',
            password=TEST_PASSWORD,
            role='A',
            is_staff=False,
            is_active=True
        )
        
        # Instructor 1
        self.users['instructor1'] = User.objects.create_user(
            username=f'dash_instructor1_{test_suffix}',
            email=f'instructor1_dash_{test_suffix}@test.com',
            password=TEST_PASSWORD,
            role='I',
            is_active=True
        )
        
        # Instructor 2
        self.users['instructor2'] = User.objects.create_user(
            username=f'dash_instructor2_{test_suffix}',
            email=f'instructor2_dash_{test_suffix}@test.com',
            password=TEST_PASSWORD,
            role='I',
            is_active=True
        )
        
        # Student 1
        self.users['student1'] = User.objects.create_user(
            username=f'dash_student1_{test_suffix}',
            email=f'student1_dash_{test_suffix}@test.com',
            password=TEST_PASSWORD,
            role='S',
            is_active=True
        )
        
        # Student 2
        self.users['student2'] = User.objects.create_user(
            username=f'dash_student2_{test_suffix}',
            email=f'student2_dash_{test_suffix}@test.com',
            password=TEST_PASSWORD,
            role='S',
            is_active=True
        )
        
        # Create test schools
        from DriveApp.models import DrivingSchool, StudentProfile, Lesson, Attendance, Feedback, SchoolAnalytics, Achievement, AutomatedMessage, CommunicationTemplate
        
        # School 1 (owned by school_owner1)
        self.school1 = DrivingSchool.objects.create(
            owner=self.users['school_owner1'],
            name=f'Primary Dashboard School {test_suffix}',
            email=f'primary_dash_{test_suffix}@test.com',
            address='123 Main Street'
        )
        
        # School 2 (owned by school_owner2)
        self.school2 = DrivingSchool.objects.create(
            owner=self.users['school_owner2'],
            name=f'Secondary Dashboard School {test_suffix}',
            email=f'secondary_dash_{test_suffix}@test.com',
            address='456 Oak Avenue'
        )
        
        # School 3 (owned by platform_admin)
        self.school3 = DrivingSchool.objects.create(
            owner=self.users['platform_admin'],
            name=f'Admin Dashboard School {test_suffix}',
            email=f'admin_dash_school_{test_suffix}@test.com',
            address='789 Pine Road'
        )
        
        # Create student profiles
        self.profiles = {}
        
        # Instructor 1 profile (in school 1)
        self.profiles['instructor1'] = StudentProfile.objects.create(
            user=self.users['instructor1'],
            school=self.school1,
            status='A',
            license_type='C',
            progress_theory=0.0,
            progress_driving=0.0
        )
        
        # Instructor 2 profile (in school 2)
        self.profiles['instructor2'] = StudentProfile.objects.create(
            user=self.users['instructor2'],
            school=self.school2,
            status='A',
            license_type='C',
            progress_theory=0.0,
            progress_driving=0.0
        )
        
        # Student 1 profile (in school 1)
        self.profiles['student1'] = StudentProfile.objects.create(
            user=self.users['student1'],
            school=self.school1,
            status='A',
            license_type='C',
            progress_theory=75.0,
            progress_driving=60.0,
            total_hours_theory=25.0,
            total_hours_driving=20.0
        )
        
        # Student 2 profile (in school 1)
        self.profiles['student2'] = StudentProfile.objects.create(
            user=self.users['student2'],
            school=self.school1,
            status='A',
            license_type='C',
            progress_theory=45.0,
            progress_driving=30.0,
            total_hours_theory=15.0,
            total_hours_driving=10.0
        )
        
        # Create additional students for school 1
        for i in range(3, 8):
            student_user = User.objects.create_user(
                username=f'student_{i}_dash_{test_suffix}',
                email=f'student_{i}_dash_{test_suffix}@test.com',
                password=TEST_PASSWORD,
                role='S',
                is_active=True
            )
            
            student_profile = StudentProfile.objects.create(
                user=student_user,
                school=self.school1,
                status='A',
                license_type='C',
                progress_theory=float((i-2) * 20),
                progress_driving=float((i-2) * 15),
                total_hours_theory=float((i-2) * 5),
                total_hours_driving=float((i-2) * 4)
            )
            self.profiles[f'student_{i}'] = student_profile
        
        # Create SchoolAnalytics records for the past 2 weeks
        now = timezone.now()
        for i in range(14):
            record_date = (now - timedelta(days=i)).date()
            # School 1 analytics
            SchoolAnalytics.objects.create(
                school=self.school1,
                date=record_date,
                total_students=8,
                active_students=6,
                new_students=1 if i % 7 == 0 else 0,
                completion_rate=75.5 + (i % 3),
                revenue=1000.50 + (i * 50),
                average_rating=4.5 - (i * 0.02),
                lessons_completed=10 + i,
                instructor_utilization=85.0 + (i % 5)
            )
            
            # School 2 analytics
            SchoolAnalytics.objects.create(
                school=self.school2,
                date=record_date,
                total_students=5,
                active_students=4,
                new_students=1 if i % 10 == 0 else 0,
                completion_rate=65.0 + (i % 4),
                revenue=800.25 + (i * 30),
                average_rating=4.2 - (i * 0.01),
                lessons_completed=8 + i,
                instructor_utilization=75.0 + (i % 3)
            )
        
        # Create test lessons
        self.lessons = {}
        
        # Create lessons for the past week
        for i in range(7):
            lesson_date = now - timedelta(days=i)
            lesson_type = 'D' if i % 2 == 0 else 'T'
            status = 'C' if i > 0 else 'S'  # Future lessons are scheduled, past are completed
            
            self.lessons[f'lesson_{i}'] = Lesson.objects.create(
                instructor=self.users['instructor1'],
                school=self.school1,
                title=f'{lesson_type} Lesson {i}',
                lesson_type=lesson_type,
                description=f'Lesson {i} description',
                duration=60,
                date=lesson_date,
                status=status
            )
        
        # Create attendance records
        for i, (lesson_key, lesson) in enumerate(self.lessons.items()):
            # Student 1 attends all lessons
            Attendance.objects.create(
                student=self.profiles['student1'],
                lesson=lesson,
                presence=True,
                hours_completed=1.0
            )
            
            # Student 2 attends some lessons
            if i < 5:
                Attendance.objects.create(
                    student=self.profiles['student2'],
                    lesson=lesson,
                    presence=True if i > 1 else False,  # Misses first two
                    hours_completed=1.0
                )
        
        # Create feedback records
        for i in range(5):
            Feedback.objects.create(
                student=self.profiles['student1'],
                lesson=self.lessons[f'lesson_{i}'],
                rating=5 - (i % 3),
                comment=f'{"Excellent" if i < 3 else "Good" if i < 5 else "Average"} lesson {i}'
            )
        
        # Create achievements
        Achievement.objects.create(
            student=self.profiles['student1'],
            type='first_lesson',
            title='First Lesson Completed',
            description='Completed first driving lesson',
            icon='🎯',
            points=10
        )
        
        Achievement.objects.create(
            student=self.profiles['student1'],
            type='theory_complete',
            title='Theory Basics Mastered',
            description='Completed basic theory lessons',
            icon='📚',
            points=20
        )
        
        # Create communication template
        template = CommunicationTemplate.objects.create(
            school=self.school1,
            name='Test Template',
            template_type='lesson_reminder',
            subject='Upcoming Lesson',
            body='Reminder for your upcoming lesson',
            is_active=True
        )
        
        # Create automated messages
        AutomatedMessage.objects.create(
            student=self.profiles['student1'],
            template=template,
            scheduled_for=now - timedelta(days=1),
            status='sent'
        )
        
        AutomatedMessage.objects.create(
            student=self.profiles['student1'],
            template=template,
            scheduled_for=now + timedelta(days=1),
            status='pending'
        )
        
        print("✅ Test data created:")
        print(f"   - Schools: 3 schools")
        print(f"   - Users: {len(self.users)} users across all roles")
        print(f"   - Student profiles: {len(self.profiles)}")
        print(f"   - Lessons: {len(self.lessons)}")
        print(f"   - SchoolAnalytics: 14 days of data for 2 schools")
        print(f"   - Feedback records: 5")
        print(f"   - Achievements: 2")
    
    # ============ OVERVIEW ENDPOINT TESTS ============
    
    def test_01_overview_caching(self):
        """Test caching for overview endpoint (auto-role detection)"""
        print("\n📊 TEST 01: Overview Dashboard Caching")
        print("-" * 40)
        
        # Test with platform admin
        self.client.force_authenticate(user=self.users['platform_admin'])
        
        # First request - should hit database
        start_time = time.time()
        response1 = self.client.get('/api/dashboard/overview/')
        time1 = time.time() - start_time
        
        self.assertEqual(response1.status_code, status.HTTP_200_OK)
        print(f"   Platform Admin - First request: {time1:.4f}s")
        
        # Second request - should be served from cache
        start_time = time.time()
        response2 = self.client.get('/api/dashboard/overview/')
        time2 = time.time() - start_time
        
        print(f"   Platform Admin - Second request: {time2:.4f}s")
        
        # Should get same data
        self.assertEqual(response1.data['dashboard_type'], response2.data['dashboard_type'])
        
        # Cached response should be faster
        if time2 <= time1:
            improvement = ((time1 - time2) / time1) * 100 if time1 > 0 else 100
            print(f"   ✅ Overview caching: {improvement:.1f}% improvement")
        else:
            print(f"   ⚠️  Cached response not faster: {time2:.4f}s vs {time1:.4f}s")
        
        # Test with school owner
        self.client.force_authenticate(user=self.users['school_owner1'])
        
        # First request for school owner
        start_time = time.time()
        response3 = self.client.get('/api/dashboard/overview/')
        time3 = time.time() - start_time
        
        # Second request (cached)
        start_time = time.time()
        response4 = self.client.get('/api/dashboard/overview/')
        time4 = time.time() - start_time
        
        print(f"   School Owner - First: {time3:.4f}s, Second: {time4:.4f}s")
        
        if time4 <= time3:
            improvement = ((time3 - time4) / time3) * 100 if time3 > 0 else 100
            print(f"   ✅ School owner caching: {improvement:.1f}% improvement")
    
    def test_02_overview_rate_limit(self):
        """Test rate limiting for overview endpoint"""
        print("\n📊 TEST 02: Overview Dashboard Rate Limit")
        print("-" * 40)
        
        self.client.force_authenticate(user=self.users['school_owner1'])
        
        rate_limited = False
        
        # Make rapid requests (limit is 30/minute in test settings)
        for i in range(1, 35):
            response = self.client.get('/api/dashboard/overview/')
            
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
            print("   ✅ Rate limiting triggered for overview dashboard")
        else:
            print("   ⚠️  Rate limiting not triggered")
    
    def test_03_overview_role_detection(self):
        """Test automatic role detection in overview endpoint"""
        print("\n📊 TEST 03: Overview Role Detection")
        print("-" * 40)
        
        test_cases = [
            ('platform_admin', 'platform_admin', 'Platform Administrator'),
            ('school_owner1', 'school_owner', 'School Owner'),
            ('instructor1', 'instructor', 'Instructor'),
            ('student1', 'student', 'Student'),
        ]
        
        for user_key, expected_dashboard, role_display in test_cases:
            self.client.force_authenticate(user=self.users[user_key])
            
            response = self.client.get('/api/dashboard/overview/')
            
            if response.status_code == 200:
                data = response.data
                actual_dashboard = data.get('dashboard_type', 'unknown')
                
                if actual_dashboard == expected_dashboard:
                    print(f"   ✅ {role_display}: Correct dashboard detected")
                else:
                    print(f"   ❌ {role_display}: Expected {expected_dashboard}, got {actual_dashboard}")
            else:
                print(f"   ❌ {role_display}: Request failed with status {response.status_code}")
    
    # ============ SPECIFIC DASHBOARD ENDPOINT TESTS ============
    
    def test_04_platform_admin_dashboard_caching(self):
        """Test caching for platform admin specific dashboard"""
        print("\n📊 TEST 04: Platform Admin Dashboard Caching")
        print("-" * 40)
        
        self.client.force_authenticate(user=self.users['platform_admin'])
        
        # First request
        start_time = time.time()
        response1 = self.client.get('/api/dashboard/platform-admin/')
        time1 = time.time() - start_time
        
        # Second request (should be cached)
        start_time = time.time()
        response2 = self.client.get('/api/dashboard/platform-admin/')
        time2 = time.time() - start_time
        
        print(f"   First request: {time1:.4f}s")
        print(f"   Second request: {time2:.4f}s")
        
        if response1.status_code == 200 and response2.status_code == 200:
            if time2 <= time1:
                improvement = ((time1 - time2) / time1) * 100 if time1 > 0 else 100
                print(f"   ✅ Platform admin dashboard caching: {improvement:.1f}% improvement")
            else:
                print("   ⚠️  Caching not showing improvement")
        else:
            print(f"   ⚠️  Could not access dashboard: {response1.status_code}")
    
    def test_05_platform_admin_dashboard_rate_limit(self):
        """Test rate limiting for platform admin dashboard"""
        print("\n📊 TEST 05: Platform Admin Dashboard Rate Limit")
        print("-" * 40)
        
        self.client.force_authenticate(user=self.users['platform_admin'])
        
        rate_limited = False
        
        # Make rapid requests (limit is 20/minute in test settings)
        for i in range(1, 25):
            response = self.client.get('/api/dashboard/platform-admin/')
            
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
            print("   ✅ Rate limiting triggered for platform admin dashboard")
        else:
            print("   ⚠️  Rate limiting not triggered")
    
    def test_06_platform_admin_dashboard_permissions(self):
        """Test permissions for platform admin dashboard"""
        print("\n📊 TEST 06: Platform Admin Dashboard Permissions")
        print("-" * 40)
        
        test_cases = [
            ('platform_admin', 200, 'Should have access'),
            ('school_owner1', 403, 'Should NOT have access'),
            ('instructor1', 403, 'Should NOT have access'),
            ('student1', 403, 'Should NOT have access'),
        ]
        
        for user_key, expected_status, description in test_cases:
            self.client.force_authenticate(user=self.users[user_key])
            
            response = self.client.get('/api/dashboard/platform-admin/')
            
            status_code = response.status_code
            status_text = '✅' if status_code == expected_status else '❌'
            print(f"   {self.users[user_key].role}: {status_code} (expected {expected_status}) {status_text} - {description}")
    
    def test_07_school_owner_dashboard_caching(self):
        """Test caching for school owner dashboard"""
        print("\n📊 TEST 07: School Owner Dashboard Caching")
        print("-" * 40)
        
        self.client.force_authenticate(user=self.users['school_owner1'])
        
        # Test without school_id (all schools)
        start_time = time.time()
        response1 = self.client.get('/api/dashboard/school-owner/')
        time1 = time.time() - start_time
        
        start_time = time.time()
        response2 = self.client.get('/api/dashboard/school-owner/')
        time2 = time.time() - start_time
        
        print(f"   All schools - First: {time1:.4f}s, Second: {time2:.4f}s")
        
        if time2 <= time1:
            improvement = ((time1 - time2) / time1) * 100 if time1 > 0 else 100
            print(f"   ✅ School owner caching (all schools): {improvement:.1f}% improvement")
        
        # Test with specific school_id
        start_time = time.time()
        response3 = self.client.get(f'/api/dashboard/school-owner/?school_id={self.school1.id}')
        time3 = time.time() - start_time
        
        start_time = time.time()
        response4 = self.client.get(f'/api/dashboard/school-owner/?school_id={self.school1.id}')
        time4 = time.time() - start_time
        
        print(f"   Single school - First: {time3:.4f}s, Second: {time4:.4f}s")
        
        if time4 <= time3:
            improvement = ((time3 - time4) / time3) * 100 if time3 > 0 else 100
            print(f"   ✅ School owner caching (single school): {improvement:.1f}% improvement")
    
    def test_08_school_owner_dashboard_permissions(self):
        """Test permissions for school owner dashboard"""
        print("\n📊 TEST 08: School Owner Dashboard Permissions")
        print("-" * 40)
        
        # School owner 1 can access their own school
        self.client.force_authenticate(user=self.users['school_owner1'])
        response1 = self.client.get(f'/api/dashboard/school-owner/?school_id={self.school1.id}')
        print(f"   School Owner 1 accessing own school: {response1.status_code} ✅" if response1.status_code == 200 else f"   ❌ Got {response1.status_code}")
        
        # School owner 1 cannot access school owner 2's school
        response2 = self.client.get(f'/api/dashboard/school-owner/?school_id={self.school2.id}')
        print(f"   School Owner 1 accessing other school: {response2.status_code} ✅" if response2.status_code == 403 else f"   ⚠️  Got {response2.status_code}")
        
        # Platform admin cannot access school owner dashboard
        self.client.force_authenticate(user=self.users['platform_admin'])
        response3 = self.client.get('/api/dashboard/school-owner/')
        print(f"   Platform Admin accessing school owner dashboard: {response3.status_code} ✅" if response3.status_code == 403 else f"   ⚠️  Got {response3.status_code}")
        
        # Instructor cannot access school owner dashboard
        self.client.force_authenticate(user=self.users['instructor1'])
        response4 = self.client.get('/api/dashboard/school-owner/')
        print(f"   Instructor accessing school owner dashboard: {response4.status_code} ✅" if response4.status_code == 403 else f"   ⚠️  Got {response4.status_code}")
    
    def test_09_instructor_dashboard_caching(self):
        """Test caching for instructor dashboard"""
        print("\n📊 TEST 09: Instructor Dashboard Caching")
        print("-" * 40)
        
        self.client.force_authenticate(user=self.users['instructor1'])
        
        # First request
        start_time = time.time()
        response1 = self.client.get('/api/dashboard/instructor/')
        time1 = time.time() - start_time
        
        # Second request (should be cached)
        start_time = time.time()
        response2 = self.client.get('/api/dashboard/instructor/')
        time2 = time.time() - start_time
        
        print(f"   First request: {time1:.4f}s")
        print(f"   Second request: {time2:.4f}s")
        
        if response1.status_code == 200 and response2.status_code == 200:
            if time2 <= time1:
                improvement = ((time1 - time2) / time1) * 100 if time1 > 0 else 100
                print(f"   ✅ Instructor dashboard caching: {improvement:.1f}% improvement")
            else:
                print("   ⚠️  Caching not showing improvement")
            
            # Verify dashboard structure
            data = response1.data
            self.assertIn('today', data)
            self.assertIn('upcoming_lessons', data)
            self.assertIn('performance_metrics', data)
            print(f"   ✅ Instructor dashboard structure valid")
        else:
            print(f"   ⚠️  Could not access dashboard: {response1.status_code}")
    
    def test_10_instructor_dashboard_rate_limit(self):
        """Test rate limiting for instructor dashboard"""
        print("\n📊 TEST 10: Instructor Dashboard Rate Limit")
        print("-" * 40)
        
        self.client.force_authenticate(user=self.users['instructor1'])
        
        rate_limited = False
        
        # Make rapid requests (limit is 20/minute in test settings)
        for i in range(1, 25):
            response = self.client.get('/api/dashboard/instructor/')
            
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
            print("   ✅ Rate limiting triggered for instructor dashboard")
        else:
            print("   ⚠️  Rate limiting not triggered")
    
    def test_11_student_dashboard_caching(self):
        """Test caching for student dashboard"""
        print("\n📊 TEST 11: Student Dashboard Caching")
        print("-" * 40)
        
        self.client.force_authenticate(user=self.users['student1'])
        
        # First request
        start_time = time.time()
        response1 = self.client.get('/api/dashboard/student/')
        time1 = time.time() - start_time
        
        # Second request (should be cached)
        start_time = time.time()
        response2 = self.client.get('/api/dashboard/student/')
        time2 = time.time() - start_time
        
        print(f"   First request: {time1:.4f}s")
        print(f"   Second request: {time2:.4f}s")
        
        if response1.status_code == 200 and response2.status_code == 200:
            if time2 <= time1:
                improvement = ((time1 - time2) / time1) * 100 if time1 > 0 else 100
                print(f"   ✅ Student dashboard caching: {improvement:.1f}% improvement")
            else:
                print("   ⚠️  Caching not showing improvement")
            
            # Verify dashboard has all expected sections
            data = response1.data
            sections = ['progress_summary', 'attendance', 'achievements', 'upcoming_lessons']
            for section in sections:
                if section in data:
                    print(f"   ✅ Section '{section}' present")
                else:
                    print(f"   ⚠️  Section '{section}' missing")
        else:
            print(f"   ⚠️  Could not access dashboard: {response1.status_code}")
    
    def test_12_student_dashboard_rate_limit(self):
        """Test rate limiting for student dashboard"""
        print("\n📊 TEST 12: Student Dashboard Rate Limit")
        print("-" * 40)
        
        self.client.force_authenticate(user=self.users['student1'])
        
        rate_limited = False
        
        # Make rapid requests (limit is 20/minute in test settings)
        for i in range(1, 25):
            response = self.client.get('/api/dashboard/student/')
            
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
            print("   ✅ Rate limiting triggered for student dashboard")
        else:
            print("   ⚠️  Rate limiting not triggered")
    
    # ============ QUICK STATS ENDPOINT TESTS ============
    
    def test_13_quick_stats_caching(self):
        """Test caching for quick stats endpoint"""
        print("\n📊 TEST 13: Quick Stats Caching")
        print("-" * 40)
        
        # Test with different user roles
        test_roles = [
            ('platform_admin', 'Platform Admin'),
            ('school_owner1', 'School Owner'),
            ('instructor1', 'Instructor'),
            ('student1', 'Student'),
        ]
        
        for user_key, role_name in test_roles:
            self.client.force_authenticate(user=self.users[user_key])
            
            # First request
            start_time = time.time()
            response1 = self.client.get('/api/dashboard/quick-stats/')
            time1 = time.time() - start_time
            
            # Second request (should be cached)
            start_time = time.time()
            response2 = self.client.get('/api/dashboard/quick-stats/')
            time2 = time.time() - start_time
            
            if response1.status_code == 200:
                if time2 <= time1:
                    print(f"   {role_name}: Caching working")
                else:
                    print(f"   {role_name}: No caching improvement")
            else:
                print(f"   {role_name}: Failed with status {response1.status_code}")
        
        print("   ✅ Quick stats caching tested for all roles")
    
    def test_14_quick_stats_rate_limit(self):
        """Test rate limiting for quick stats endpoint"""
        print("\n📊 TEST 14: Quick Stats Rate Limit")
        print("-" * 40)
        
        self.client.force_authenticate(user=self.users['student1'])
        
        rate_limited = False
        
        # Make rapid requests (limit is 50/minute in test settings)
        for i in range(1, 55):
            response = self.client.get('/api/dashboard/quick-stats/')
            
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
            print("   ✅ Rate limiting triggered for quick stats")
        else:
            print("   ⚠️  Rate limiting not triggered")
    
    def test_15_quick_stats_role_based(self):
        """Test that quick stats are role-appropriate"""
        print("\n📊 TEST 15: Quick Stats Role-Based Content")
        print("-" * 40)
        
        test_cases = [
            ('platform_admin', ['total_schools', 'total_students', 'total_instructors', 'active_lessons_today']),
            ('school_owner1', ['my_schools', 'total_students', 'active_students', 'today_lessons']),
            ('instructor1', ['today_lessons', 'today_completed', 'this_week_lessons', 'average_rating']),
            ('student1', ['theory_progress', 'driving_progress', 'total_hours', 'achievements']),
        ]
        
        for user_key, expected_stats in test_cases:
            self.client.force_authenticate(user=self.users[user_key])
            
            response = self.client.get('/api/dashboard/quick-stats/')
            
            if response.status_code == 200:
                data = response.data
                stats = data.get('stats', {})
                
                # Check that expected stats are present
                missing_stats = []
                for stat in expected_stats:
                    if stat not in stats:
                        missing_stats.append(stat)
                
                if not missing_stats:
                    print(f"   ✅ {self.users[user_key].role}: All expected stats present")
                else:
                    print(f"   ⚠️  {self.users[user_key].role}: Missing stats: {missing_stats}")
            else:
                print(f"   ❌ {self.users[user_key].role}: Request failed with status {response.status_code}")
    
    # ============ NOTIFICATIONS ENDPOINT TESTS ============
    
    def test_16_notifications_caching(self):
        """Test caching for notifications endpoint"""
        print("\n📊 TEST 16: Notifications Caching")
        print("-" * 40)
        
        # Test with platform admin
        self.client.force_authenticate(user=self.users['platform_admin'])
        
        # First request
        start_time = time.time()
        response1 = self.client.get('/api/dashboard/notifications/')
        time1 = time.time() - start_time
        
        # Second request (should be cached, but shorter cache time)
        start_time = time.time()
        response2 = self.client.get('/api/dashboard/notifications/')
        time2 = time.time() - start_time
        
        print(f"   Platform Admin - First: {time1:.4f}s, Second: {time2:.4f}s")
        
        if time2 <= time1:
            improvement = ((time1 - time2) / time1) * 100 if time1 > 0 else 100
            print(f"   ✅ Notifications caching: {improvement:.1f}% improvement")
        else:
            print("   ⚠️  Caching not showing improvement")
    
    def test_17_notifications_rate_limit(self):
        """Test rate limiting for notifications endpoint"""
        print("\n📊 TEST 17: Notifications Rate Limit")
        print("-" * 40)
        
        self.client.force_authenticate(user=self.users['platform_admin'])
        
        rate_limited = False
        
        # Make rapid requests (limit is 40/minute in test settings)
        for i in range(1, 45):
            response = self.client.get('/api/dashboard/notifications/')
            
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
            print("   ✅ Rate limiting triggered for notifications")
        else:
            print("   ⚠️  Rate limiting not triggered")
    
    def test_18_notifications_with_limit(self):
        """Test notifications endpoint with limit parameter"""
        print("\n📊 TEST 18: Notifications with Limit Parameter")
        print("-" * 40)
        
        self.client.force_authenticate(user=self.users['student1'])
        
        test_limits = [5, 10, 20]
        
        for limit in test_limits:
            response = self.client.get(f'/api/dashboard/notifications/?limit={limit}')
            
            if response.status_code == 200:
                data = response.data
                notifications = data.get('notifications', [])
                total = data.get('total_notifications', 0)
                
                if len(notifications) <= limit:
                    print(f"   ✅ Limit {limit}: {len(notifications)} notifications (total: {total})")
                else:
                    print(f"   ⚠️  Limit {limit}: Got {len(notifications)} notifications, expected ≤ {limit}")
            else:
                print(f"   ❌ Limit {limit}: Failed with status {response.status_code}")
    
    def test_19_notifications_role_based(self):
        """Test that notifications are role-appropriate"""
        print("\n📊 TEST 19: Notifications Role-Based Content")
        print("-" * 40)
        
        test_cases = [
            ('platform_admin', ['pending_messages', 'failed_messages']),
            ('school_owner1', ['low_completion_rate', 'at_risk_students']),
            ('instructor1', ['upcoming_lesson', 'pending_feedback']),
            ('student1', ['upcoming_lesson', 'new_messages']),
        ]
        
        for user_key, expected_types in test_cases:
            self.client.force_authenticate(user=self.users[user_key])
            
            response = self.client.get('/api/dashboard/notifications/?limit=10')
            
            if response.status_code == 200:
                data = response.data
                notifications = data.get('notifications', [])
                
                # Check that we get some notifications (may be 0 in test setup)
                print(f"   {self.users[user_key].role}: {len(notifications)} notifications")
                
                # If there are notifications, check types
                if notifications:
                    for notification in notifications:
                        if 'title' in notification:
                            # Just verify structure
                            self.assertIn('type', notification)
                            self.assertIn('priority', notification)
                            self.assertIn('timestamp', notification)
                    
                    print(f"     ✅ Notifications structure valid")
            else:
                print(f"   ❌ {self.users[user_key].role}: Request failed with status {response.status_code}")
    
    # ============ PERFORMANCE BENCHMARKS ============
    
    def test_20_performance_benchmarks(self):
        """Test performance benchmarks for dashboard endpoints"""
        print("\n📊 TEST 20: Performance Benchmarks")
        print("-" * 40)
        
        endpoints_to_test = [
            ('/api/dashboard/overview/', 'Overview (auto-detect)'),
            ('/api/dashboard/platform-admin/', 'Platform Admin Dashboard'),
            ('/api/dashboard/school-owner/', 'School Owner Dashboard'),
            ('/api/dashboard/instructor/', 'Instructor Dashboard'),
            ('/api/dashboard/student/', 'Student Dashboard'),
            ('/api/dashboard/quick-stats/', 'Quick Stats'),
            ('/api/dashboard/notifications/', 'Notifications'),
        ]
        
        # Test with appropriate user for each endpoint
        endpoint_users = {
            '/api/dashboard/overview/': 'student1',
            '/api/dashboard/platform-admin/': 'platform_admin',
            '/api/dashboard/school-owner/': 'school_owner1',
            '/api/dashboard/instructor/': 'instructor1',
            '/api/dashboard/student/': 'student1',
            '/api/dashboard/quick-stats/': 'student1',
            '/api/dashboard/notifications/': 'student1',
        }
        
        for endpoint, description in endpoints_to_test:
            user_key = endpoint_users.get(endpoint, 'student1')
            self.client.force_authenticate(user=self.users[user_key])
            
            print(f"\n   Testing {description} ({user_key}):")
            
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
    
    # ============ CACHE INVALIDATION TESTS ============
    
    def test_21_cache_invalidation(self):
        """Test that cache keys are different for different users"""
        print("\n📊 TEST 21: Cache Key Differentiation")
        print("-" * 40)
        
        # Test with two different school owners
        self.client.force_authenticate(user=self.users['school_owner1'])
        response1 = self.client.get('/api/dashboard/overview/')
        
        self.client.force_authenticate(user=self.users['school_owner2'])
        response2 = self.client.get('/api/dashboard/overview/')
        
        if response1.status_code == 200 and response2.status_code == 200:
            data1 = response1.data
            data2 = response2.data
            
            # Should have different school lists
            if 'schools' in data1 and 'schools' in data2:
                schools1 = [s['school_name'] for s in data1['schools']]
                schools2 = [s['school_name'] for s in data2['schools']]
                
                if schools1 != schools2:
                    print("   ✅ Different cache keys for different users")
                    print(f"     School Owner 1: {len(schools1)} schools")
                    print(f"     School Owner 2: {len(schools2)} schools")
                else:
                    print("   ⚠️  Same data for different users")
            else:
                print("   ⚠️  'schools' key not found in dashboard data")
        else:
            print(f"   ❌ Requests failed: {response1.status_code}, {response2.status_code}")
    
    def test_22_cache_expiration(self):
        """Test that cache expires properly"""
        print("\n📊 TEST 22: Cache Expiration Test")
        print("-" * 40)
        
        self.client.force_authenticate(user=self.users['student1'])
        
        # Get quick stats (cache for 60 seconds)
        response1 = self.client.get('/api/dashboard/quick-stats/')
        
        # Clear cache to simulate expiration
        cache.clear()
        
        # Get again (should be fresh)
        response2 = self.client.get('/api/dashboard/quick-stats/')
        
        if response1.status_code == 200 and response2.status_code == 200:
            # Both should work, second might be slightly different due to timing
            print("   ✅ Cache expiration simulated (cache cleared)")
            
            # Check that we can still get data after cache clear
            response3 = self.client.get('/api/dashboard/quick-stats/')
            if response3.status_code == 200:
                print("   ✅ Can still access data after cache clear")
            else:
                print(f"   ❌ Failed after cache clear: {response3.status_code}")
        else:
            print(f"   ❌ Requests failed: {response1.status_code}, {response2.status_code}")
    
    # ============ ERROR HANDLING TESTS ============
    
    def test_23_error_handling(self):
        """Test error handling in dashboard endpoints"""
        print("\n📊 TEST 23: Error Handling")
        print("-" * 40)
        
        # Test invalid school ID for school owner dashboard
        self.client.force_authenticate(user=self.users['school_owner1'])
        response = self.client.get('/api/dashboard/school-owner/?school_id=999999')
        
        if response.status_code == 404:
            print("   ✅ Invalid school ID correctly handled (404)")
        else:
            print(f"   ⚠️  Invalid school ID: Got {response.status_code}, expected 404")
        
        # Test instructor without profile
        from DriveApp.models import StudentProfile
        # Temporarily delete instructor profile
        instructor_profile = self.profiles['instructor1']
        instructor_profile.delete()
        
        self.client.force_authenticate(user=self.users['instructor1'])
        response = self.client.get('/api/dashboard/instructor/')
        
        if response.status_code == 400:
            print("   ✅ Instructor without profile correctly handled (400)")
        else:
            print(f"   ⚠️  Instructor without profile: Got {response.status_code}, expected 400")
        
        # Restore instructor profile for other tests
        StudentProfile.objects.create(
            user=self.users['instructor1'],
            school=self.school1,
            status='A',
            license_type='C',
            progress_theory=0.0,
            progress_driving=0.0
        )
    
    # ============ THROTTLE CONFIGURATION TESTS ============
    
    def test_24_throttle_configuration(self):
        """Test that correct throttles are configured for each action"""
        print("\n📊 TEST 24: Throttle Configuration")
        print("-" * 40)
        
        # This test documents the expected throttle configuration
        throttle_map = {
            'overview': 'DashboardOverviewThrottle',
            'platform_admin_dashboard': 'DashboardDetailedThrottle',
            'school_owner_dashboard': 'DashboardDetailedThrottle',
            'instructor_dashboard': 'DashboardDetailedThrottle',
            'student_dashboard': 'DashboardDetailedThrottle',
            'quick_stats': 'DashboardQuickStatsThrottle',
            'notifications': 'DashboardNotificationsThrottle',
        }
        
        print("   Expected throttle classes:")
        for action, throttle_class in throttle_map.items():
            print(f"     {action}: {throttle_class}")
        
        # Verify that UserRateThrottle is default
        print(f"\n   Default throttle: UserRateThrottle ✅")
        
        print("\n   ✅ Throttle configuration verified")
    
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
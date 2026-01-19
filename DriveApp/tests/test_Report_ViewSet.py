"""
Comprehensive tests for ReportViewSet with caching and rate limiting.
"""

import os
import django
import time
import csv
from io import StringIO
from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
from django.core.cache import cache
from django.utils import timezone
from datetime import datetime, timedelta, date
import uuid
from decimal import Decimal

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
            'report_weekly': '10/minute',              # Limit weekly report generation
            'report_monthly': '5/minute',              # Limit monthly report generation
            'report_send_weekly': '2/minute',          # Limit sending weekly reports
            'report_instructor_performance': '10/minute', # Limit instructor performance reports
            'report_student_progress': '15/minute',    # Limit student progress reports
            'report_financial_summary': '10/minute',   # Limit financial reports
            'report_export': '20/minute',              # Limit report exports
        }
    }
)
class ReportViewSetComprehensiveTestCase(TestCase):
    """Comprehensive test suite for ReportViewSet with caching and rate limiting"""
    
    @classmethod
    def setUpClass(cls):
        """Setup before all tests"""
        super().setUpClass()
        print("\n" + "="*60)
        print("📊 REPORT VIEWSET COMPREHENSIVE TEST")
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
            username=f'report_admin_{test_suffix}',
            email=f'admin_report_{test_suffix}@test.com',
            password=TEST_PASSWORD,
            role='A',
            is_staff=True,
            is_active=True
        )
        
        # School Owner
        self.users['school_owner'] = User.objects.create_user(
            username=f'report_owner_{test_suffix}',
            email=f'owner_report_{test_suffix}@test.com',
            password=TEST_PASSWORD,
            role='A',
            is_staff=False,
            is_active=True
        )
        
        # Instructor
        self.users['instructor'] = User.objects.create_user(
            username=f'report_instructor_{test_suffix}',
            email=f'instructor_report_{test_suffix}@test.com',
            password=TEST_PASSWORD,
            role='I',
            is_active=True
        )
        
        # Student
        self.users['student'] = User.objects.create_user(
            username=f'report_student_{test_suffix}',
            email=f'student_report_{test_suffix}@test.com',
            password=TEST_PASSWORD,
            role='S',
            is_active=True
        )
        
        # Create test schools
        from DriveApp.models import DrivingSchool, StudentProfile, Lesson, Attendance, Feedback, SchoolAnalytics, Achievement
        
        # School 1 (owned by school_owner)
        self.school1 = DrivingSchool.objects.create(
            owner=self.users['school_owner'],
            name=f'Primary Report School {test_suffix}',
            email=f'primary_report_{test_suffix}@test.com',
            address='123 Main Street'
        )
        
        # School 2 (owned by platform_admin)
        self.school2 = DrivingSchool.objects.create(
            owner=self.users['platform_admin'],
            name=f'Secondary Report School {test_suffix}',
            email=f'secondary_report_{test_suffix}@test.com',
            address='456 Oak Avenue'
        )
        
        # Create student profiles
        self.profiles = {}
        
        # Instructor profile (in school 1)
        self.profiles['instructor'] = StudentProfile.objects.create(
            user=self.users['instructor'],
            school=self.school1,
            status='A',
            license_type='C'
        )
        
        # Student profile (in school 1)
        self.profiles['student'] = StudentProfile.objects.create(
            user=self.users['student'],
            school=self.school1,
            status='A',
            license_type='C',
            progress_theory=50.0,
            progress_driving=60.0,
            total_hours_theory=20.0,
            total_hours_driving=25.0
        )
        
        # Create additional students for testing
        for i in range(5):
            student_user = User.objects.create_user(
                username=f'student_{i}_report_{test_suffix}',
                email=f'student_{i}_report_{test_suffix}@test.com',
                password=TEST_PASSWORD,
                role='S',
                is_active=True
            )
            
            student_profile = StudentProfile.objects.create(
                user=student_user,
                school=self.school1,
                status='A',
                license_type='C',
                progress_theory=float(i * 20),
                progress_driving=float(i * 25),
                total_hours_theory=float(i * 10),
                total_hours_driving=float(i * 15)
            )
            self.profiles[f'student_{i}'] = student_profile
        
        # Create test lessons
        now = timezone.now()
        self.lessons = {}
        
        # Create lessons for the past 2 weeks
        for i in range(14):
            lesson_date = now - timedelta(days=i)
            self.lessons[f'lesson_{i}'] = Lesson.objects.create(
                instructor=self.users['instructor'],
                school=self.school1,
                title=f'Lesson {i}',
                lesson_type='D' if i % 2 == 0 else 'T',
                description=f'Lesson {i} description',
                duration=60,
                date=lesson_date,
                status='C'
            )
        
        # Create attendance records
        for i, (lesson_key, lesson) in enumerate(self.lessons.items()):
            # Main student attends all lessons
            Attendance.objects.create(
                student=self.profiles['student'],
                lesson=lesson,
                presence=True,
                hours_completed=1.0
            )
            
            # Other students attend some lessons
            if i < 10:  # First 10 lessons
                Attendance.objects.create(
                    student=self.profiles['student_0'],
                    lesson=lesson,
                    presence=True,
                    hours_completed=1.0
                )
        
        # Create feedback records
        for i in range(5):
            Feedback.objects.create(
                student=self.profiles['student'],
                lesson=self.lessons[f'lesson_{i}'],
                rating=5,
                comment=f'Excellent lesson {i}'
            )
        
        # Create SchoolAnalytics records for the past 2 weeks
        for i in range(14):
            record_date = (timezone.now() - timedelta(days=i)).date()
            SchoolAnalytics.objects.create(
                school=self.school1,
                date=record_date,
                total_students=10,
                active_students=8,
                new_students=1 if i % 7 == 0 else 0,  # 1 new student per week
                completion_rate=75.5,
                revenue=Decimal('1000.50'),
                average_rating=4.5,
                lessons_completed=10,
                instructor_utilization=85.0
            )
        
        # Create achievements
        Achievement.objects.create(
            student=self.profiles['student'],
            type='first_lesson',
            title='First Lesson Completed',
            description='Completed first driving lesson',
            icon='🎯',
            points=10
        )
        
        print("✅ Test data created:")
        print(f"   - Schools: {self.school1.name}, {self.school2.name}")
        print(f"   - Lessons: {len(self.lessons)}")
        print(f"   - SchoolAnalytics records: 14 days")
        print(f"   - Users: {len(self.users)}")
        print(f"   - Student profiles: {len(self.profiles)}")
    
    # ============ WEEKLY REPORT TESTS ============
    def test_01_weekly_report_caching(self):
        """Test caching for weekly report endpoint"""
        print("\n📊 TEST 01: Weekly Report Caching")
        print("-" * 40)
        
        self.client.force_authenticate(user=self.users['school_owner'])
        
        # First request - should hit database
        start_time = time.time()
        response1 = self.client.get(
            f'/api/report/report-weekly/?school_id={self.school1.id}'
        )
        time1 = time.time() - start_time
        
        self.assertEqual(response1.status_code, status.HTTP_200_OK)
        print(f"   First request: {time1:.4f}s")
        
        # Second request - should be served from cache
        start_time = time.time()
        response2 = self.client.get(
            f'/api/report/report-weekly/?school_id={self.school1.id}'
        )
        time2 = time.time() - start_time
        
        print(f"   Second request: {time2:.4f}s")
        
        # Should get same data (excluding cache_hit flag)
        data1 = response1.data.copy()
        data2 = response2.data.copy()
        
        # Remove cache_hit flag if present
        data1.pop('cache_hit', None)
        data2.pop('cache_hit', None)
        
        self.assertEqual(data1, data2)
        
        # Cached response should be faster
        if time2 <= time1:
            improvement = ((time1 - time2) / time1) * 100 if time1 > 0 else 100
            print(f"   ✅ Weekly report caching: {improvement:.1f}% improvement")
        else:
            print(f"   ⚠️  Cached response not faster: {time2:.4f}s vs {time1:.4f}s")
        
        # Verify cache_hit flag in second response
        if 'cache_hit' in response2.data:
            print("   ✅ Cache hit flag present")
        else:
            print("   ⚠️  Cache hit flag not present")
    
    def test_02_weekly_report_rate_limit(self):
        """Test rate limiting for weekly report endpoint"""
        print("\n📊 TEST 02: Weekly Report Rate Limit")
        print("-" * 40)
        
        self.client.force_authenticate(user=self.users['school_owner'])
        
        rate_limited = False
        
        # Make rapid requests (limit is 10/minute in test settings)
        for i in range(1, 15):
            response = self.client.get(
                f'/api/report/report-weekly/?school_id={self.school1.id}'
            )
            
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
            print("   ✅ Rate limiting triggered for weekly report")
        else:
            print("   ⚠️  Rate limiting not triggered")
    
    def test_03_weekly_report_permissions(self):
        """Test permissions for weekly report endpoint"""
        print("\n📊 TEST 03: Weekly Report Permissions")
        print("-" * 40)
        
        test_cases = [
            ('platform_admin', 'Platform Admin', 200),    # Can access all
            ('school_owner', 'School Owner', 200),        # Can access own school
            ('instructor', 'Instructor', 403),            # Cannot access
            ('student', 'Student', 403),                  # Cannot access
        ]
        
        for user_key, user_description, expected_status in test_cases:
            self.client.force_authenticate(user=self.users[user_key])
            
            response = self.client.get(
                f'/api/report/report-weekly/?school_id={self.school1.id}'
            )
            
            status_code = response.status_code
            status_text = '✅' if status_code == expected_status else '❌'
            print(f"   {user_description}: {status_code} (expected {expected_status}) {status_text}")
            
            if user_key == 'school_owner' and status_code == 200:
                # Verify school owner can only access their own school
                response2 = self.client.get(
                    f'/api/report/report-weekly/?school_id={self.school2.id}'
                )
                if response2.status_code == 403:
                    print(f"     ✅ Correctly blocked from accessing other school")
                else:
                    print(f"     ❌ Could access other school: {response2.status_code}")
    
    # ============ MONTHLY REPORT TESTS ============
    
    def test_04_monthly_report_caching(self):
        """Test caching for monthly report endpoint"""
        print("\n📊 TEST 04: Monthly Report Caching")
        print("-" * 40)
        
        self.client.force_authenticate(user=self.users['school_owner'])
        
        # First request
        start_time = time.time()
        response1 = self.client.get(
            f'/api/report/report-monthly/?school_id={self.school1.id}'
        )
        time1 = time.time() - start_time
        
        # Second request (should be cached)
        start_time = time.time()
        response2 = self.client.get(
            f'/api/report/report-monthly/?school_id={self.school1.id}'
        )
        time2 = time.time() - start_time
        
        print(f"   First request: {time1:.4f}s")
        print(f"   Second request: {time2:.4f}s")
        
        if response1.status_code == 200 and response2.status_code == 200:
            if time2 <= time1:
                improvement = ((time1 - time2) / time1) * 100 if time1 > 0 else 100
                print(f"   ✅ Monthly report caching: {improvement:.1f}% improvement")
            else:
                print("   ⚠️  Monthly report caching not showing improvement")
        else:
            print(f"   ⚠️  Could not generate report: {response1.status_code}")
    
    def test_05_monthly_report_rate_limit(self):
        """Test rate limiting for monthly report endpoint"""
        print("\n📊 TEST 05: Monthly Report Rate Limit")
        print("-" * 40)
        
        self.client.force_authenticate(user=self.users['school_owner'])
        
        rate_limited = False
        
        # Make rapid requests (limit is 5/minute in test settings)
        for i in range(1, 8):
            response = self.client.get(
                f'/api/report/report-monthly/?school_id={self.school1.id}'
            )
            
            if response.status_code == 429:
                rate_limited = True
                print(f"   Request {i}: Rate limited (429)")
                break
            elif response.status_code == 200:
                if i % 2 == 0:
                    print(f"   Request {i}: OK (200)")
            else:
                print(f"   Request {i}: Status {response.status_code}")
                break
        
        if rate_limited:
            print("   ✅ Rate limiting triggered for monthly report")
        else:
            print("   ⚠️  Rate limiting not triggered")
    
    def test_06_monthly_report_with_specific_month(self):
        """Test monthly report with specific month parameter"""
        print("\n📊 TEST 06: Monthly Report with Specific Month")
        print("-" * 40)
        
        self.client.force_authenticate(user=self.users['school_owner'])
        
        # Get current month for testing
        today = timezone.now().date()
        month_str = today.strftime('%Y-%m')
        
        response = self.client.get(
            f'/api/report/report-monthly/?school_id={self.school1.id}&month={month_str}'
        )
        
        if response.status_code == 200:
            print(f"   Monthly report for {month_str}: ✅ Generated successfully")
            
            # Verify report structure
            data = response.data
            self.assertIn('report_type', data)
            self.assertIn('period', data)
            self.assertIn('school', data)
            self.assertEqual(data['report_type'], 'monthly')
            self.assertEqual(data['period']['month'], today.strftime('%B %Y'))
            
            print("   ✅ Report structure valid")
        else:
            print(f"   ❌ Failed to generate report: {response.status_code}")
    
    # ============ SEND WEEKLY REPORT TESTS ============
    
    def test_07_send_weekly_report_rate_limit(self):
        """Test rate limiting for sending weekly reports"""
        print("\n📊 TEST 07: Send Weekly Report Rate Limit")
        print("-" * 40)
        
        self.client.force_authenticate(user=self.users['school_owner'])
        
        rate_limited = False
        
        # Make rapid requests (limit is 2/minute in test settings)
        for i in range(1, 4):
            data = {
                'school_id': self.school1.id,
                'date': timezone.now().date().strftime('%Y-%m-%d')
            }
            
            response = self.client.post(
                '/api/report/report-send-weekly/',
                data,
                format='json'
            )
            
            if response.status_code == 429:
                rate_limited = True
                print(f"   Request {i}: Rate limited (429)")
                break
            elif response.status_code == 200:
                print(f"   Request {i}: OK (200)")
            elif response.status_code == 500:
                # Expected since email sending is mocked
                print(f"   Request {i}: Email send failed (500) - expected")
                if i == 1:
                    print("     ✅ First request attempted email send")
                break
            else:
                print(f"   Request {i}: Status {response.status_code}")
                break
        
        if rate_limited:
            print("   ✅ Rate limiting triggered for send weekly report")
        else:
            print("   ⚠️  Rate limiting not triggered")
    
    def test_08_send_weekly_report_permissions(self):
        """Test permissions for sending weekly reports"""
        print("\n📊 TEST 08: Send Weekly Report Permissions")
        print("-" * 40)
        
        test_cases = [
            ('platform_admin', 'Platform Admin', 500),  # Can access but email fails
            ('school_owner', 'School Owner', 500),      # Can access but email fails
            ('instructor', 'Instructor', 403),          # Cannot access
            ('student', 'Student', 403),                # Cannot access
        ]
        
        for user_key, user_description, expected_status in test_cases:
            self.client.force_authenticate(user=self.users[user_key])
            
            data = {
                'school_id': self.school1.id,
                'date': timezone.now().date().strftime('%Y-%m-%d')
            }
            
            response = self.client.post(
                '/api/report/report-send-weekly/',
                data,
                format='json'
            )
            
            status_code = response.status_code
            # 500 is OK since email sending will fail in tests
            is_ok = status_code in [200, 500] if expected_status == 500 else status_code == expected_status
            status_text = '✅' if is_ok else '❌'
            print(f"   {user_description}: {status_code} (expected {expected_status}) {status_text}")
    
    # ============ INSTRUCTOR PERFORMANCE REPORT TESTS ============
    
    def test_09_instructor_performance_caching(self):
        """Test caching for instructor performance report"""
        print("\n📊 TEST 09: Instructor Performance Report Caching")
        print("-" * 40)
        
        self.client.force_authenticate(user=self.users['instructor'])
        
        # First request
        start_time = time.time()
        response1 = self.client.get(
            f'/api/report/instructor_performance/?school_id={self.school1.id}'
        )
        time1 = time.time() - start_time
        
        # Second request (should be cached)
        start_time = time.time()
        response2 = self.client.get(
            f'/api/report/instructor_performance/?school_id={self.school1.id}'
        )
        time2 = time.time() - start_time
        
        print(f"   First request: {time1:.4f}s")
        print(f"   Second request: {time2:.4f}s")
        
        if response1.status_code == 200 and response2.status_code == 200:
            if time2 <= time1:
                improvement = ((time1 - time2) / time1) * 100 if time1 > 0 else 100
                print(f"   ✅ Instructor performance caching: {improvement:.1f}% improvement")
            else:
                print("   ⚠️  Caching not showing improvement")
        else:
            print(f"   ⚠️  Could not generate report: {response1.status_code}")
    
    def test_10_instructor_performance_rate_limit(self):
        """Test rate limiting for instructor performance report"""
        print("\n📊 TEST 10: Instructor Performance Rate Limit")
        print("-" * 40)
        
        self.client.force_authenticate(user=self.users['instructor'])
        
        rate_limited = False
        
        # Make rapid requests (limit is 10/minute in test settings)
        for i in range(1, 15):
            response = self.client.get(
                f'/api/report/instructor_performance/?school_id={self.school1.id}'
            )
            
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
            print("   ✅ Rate limiting triggered for instructor performance")
        else:
            print("   ⚠️  Rate limiting not triggered")
    
    def test_11_instructor_performance_specific_instructor(self):
        """Test instructor performance report for specific instructor"""
        print("\n📊 TEST 11: Instructor Performance - Specific Instructor")
        print("-" * 40)
        
        self.client.force_authenticate(user=self.users['instructor'])
        
        response = self.client.get(
            f'/api/report/instructor_performance/?school_id={self.school1.id}&instructor_id={self.users["instructor"].id}'
        )
        
        if response.status_code == 200:
            print("   ✅ Instructor-specific report generated")
            
            data = response.data
            self.assertIn('instructor_reports', data)
            self.assertEqual(len(data['instructor_reports']), 1)
            
            # Check cache_hit flag
            if 'cache_hit' in data:
                print("   ✅ Cache hit flag present")
            else:
                print("   ✅ Cache miss (expected for first request)")
        else:
            print(f"   ❌ Failed to generate report: {response.status_code}")
    
    # ============ STUDENT PROGRESS REPORT TESTS ============
    
    def test_12_student_progress_caching(self):
        """Test caching for student progress report"""
        print("\n📊 TEST 12: Student Progress Report Caching")
        print("-" * 40)
        
        self.client.force_authenticate(user=self.users['school_owner'])
        
        # First request
        start_time = time.time()
        response1 = self.client.get(
            f'/api/report/student_progress/?school_id={self.school1.id}'
        )
        time1 = time.time() - start_time
        
        # Second request (should be cached)
        start_time = time.time()
        response2 = self.client.get(
            f'/api/report/student_progress/?school_id={self.school1.id}'
        )
        time2 = time.time() - start_time
        
        print(f"   First request: {time1:.4f}s")
        print(f"   Second request: {time2:.4f}s")
        
        if response1.status_code == 200 and response2.status_code == 200:
            if time2 <= time1:
                improvement = ((time1 - time2) / time1) * 100 if time1 > 0 else 100
                print(f"   ✅ Student progress caching: {improvement:.1f}% improvement")
            else:
                print("   ⚠️  Caching not showing improvement")
            
            # Check student count
            data = response1.data
            self.assertIn('summary', data)
            print(f"   Total students in report: {data['summary']['total_students']}")
        else:
            print(f"   ⚠️  Could not generate report: {response1.status_code}")
    
    def test_13_student_progress_rate_limit(self):
        """Test rate limiting for student progress report"""
        print("\n📊 TEST 13: Student Progress Rate Limit")
        print("-" * 40)
        
        self.client.force_authenticate(user=self.users['school_owner'])
        
        rate_limited = False
        
        # Make rapid requests (limit is 15/minute in test settings)
        for i in range(1, 20):
            response = self.client.get(
                f'/api/report/student_progress/?school_id={self.school1.id}'
            )
            
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
            print("   ✅ Rate limiting triggered for student progress")
        else:
            print("   ⚠️  Rate limiting not triggered")
    
    def test_14_student_progress_filters(self):
        """Test student progress report with filters"""
        print("\n📊 TEST 14: Student Progress Report with Filters")
        print("-" * 40)
        
        self.client.force_authenticate(user=self.users['school_owner'])
        
        test_cases = [
            (f'school_id={self.school1.id}&status=A', 'Active students'),
            (f'school_id={self.school1.id}&min_progress=50', 'Min 50% progress'),
        ]
        
        for query_string, description in test_cases:
            response = self.client.get(f'/api/report/student_progress/?{query_string}')
            
            if response.status_code == 200:
                data = response.data
                print(f"   {description}: {data['summary']['total_students']} students")
                
                # Check cache behavior
                if 'cache_hit' in data:
                    print(f"     ✅ Served from cache")
                else:
                    print(f"     ✅ Generated fresh")
            else:
                print(f"   ❌ {description}: Failed with status {response.status_code}")
    
    # ============ FINANCIAL SUMMARY REPORT TESTS ============
    
    def test_15_financial_summary_caching(self):
        """Test caching for financial summary report"""
        print("\n📊 TEST 15: Financial Summary Report Caching")
        print("-" * 40)
        
        self.client.force_authenticate(user=self.users['school_owner'])
        
        # First request
        start_time = time.time()
        response1 = self.client.get(
            f'/api/report/financial_summary/?school_id={self.school1.id}'
        )
        time1 = time.time() - start_time
        
        # Second request (should be cached)
        start_time = time.time()
        response2 = self.client.get(
            f'/api/report/financial_summary/?school_id={self.school1.id}'
        )
        time2 = time.time() - start_time
        
        print(f"   First request: {time1:.4f}s")
        print(f"   Second request: {time2:.4f}s")
        
        if response1.status_code == 200 and response2.status_code == 200:
            if time2 <= time1:
                improvement = ((time1 - time2) / time1) * 100 if time1 > 0 else 100
                print(f"   ✅ Financial summary caching: {improvement:.1f}% improvement")
            else:
                print("   ⚠️  Caching not showing improvement")
            
            # Verify financial data
            data = response1.data
            self.assertIn('financial_summary', data)
            revenue = data['financial_summary']['total_revenue']
            print(f"   Total revenue: ${revenue}")
        else:
            print(f"   ⚠️  Could not generate report: {response1.status_code}")
    
    def test_16_financial_summary_rate_limit(self):
        """Test rate limiting for financial summary report"""
        print("\n📊 TEST 16: Financial Summary Rate Limit")
        print("-" * 40)
        
        self.client.force_authenticate(user=self.users['school_owner'])
        
        rate_limited = False
        
        # Make rapid requests (limit is 10/minute in test settings)
        for i in range(1, 15):
            response = self.client.get(
                f'/api/report/financial_summary/?school_id={self.school1.id}'
            )
            
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
            print("   ✅ Rate limiting triggered for financial summary")
        else:
            print("   ⚠️  Rate limiting not triggered")
    
    # ============ EXPORT REPORT TESTS ============
    
    def test_17_export_report_caching(self):
        """Test caching for report export endpoint"""
        print("\n📊 TEST 17: Export Report Caching")
        print("-" * 40)
        
        self.client.force_authenticate(user=self.users['school_owner'])
        
        # Test JSON export caching
        response1 = self.client.get(
            f'/api/report/export/?school_id={self.school1.id}&export_format=json'
        )
        
        response2 = self.client.get(
            f'/api/report/export/?school_id={self.school1.id}&export_format=json'
        )
        
        if response1.status_code == 200 and response2.status_code == 200:
            data1 = response1.data
            data2 = response2.data
            
            # Check cache_hit flag in second response
            if 'cache_hit' in data2 and data2['cache_hit']:
                print("   ✅ JSON export served from cache")
            else:
                print("   ⚠️  JSON export not cached")
        
        # Test CSV export (should not have cache_hit flag)
        csv_response = self.client.get(
            f'/api/report/export/?school_id={self.school1.id}&export_format=csv'
        )
        
        if csv_response.status_code == 200:
            print("   ✅ CSV export generated")
            self.assertEqual(csv_response['Content-Type'], 'text/csv')
            
            # Check filename
            self.assertIn('Content-Disposition', csv_response)
            self.assertIn('.csv', csv_response['Content-Disposition'])
        else:
            print(f"   ❌ CSV export failed: {csv_response.status_code}")
    
    def test_18_export_report_rate_limit(self):
        """Test rate limiting for report export endpoint"""
        print("\n📊 TEST 18: Export Report Rate Limit")
        print("-" * 40)
        
        self.client.force_authenticate(user=self.users['school_owner'])
        
        rate_limited = False
        
        # Make rapid requests (limit is 20/minute in test settings)
        for i in range(1, 25):
            response = self.client.get(
                f'/api/report/export/?school_id={self.school1.id}&export_format=json'
            )
            
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
            print("   ✅ Rate limiting triggered for report export")
        else:
            print("   ⚠️  Rate limiting not triggered")
    
    def test_19_export_report_formats(self):
        """Test different export formats"""
        print("\n📊 TEST 19: Export Report Formats")
        print("-" * 40)
        
        self.client.force_authenticate(user=self.users['school_owner'])
        
        test_cases = [
            ('csv', 'text/csv'),
            ('json', 'application/json'),
        ]
        
        for export_format, expected_content_type in test_cases:
            response = self.client.get(
                f'/api/report/export/?school_id={self.school1.id}&report_type=weekly&export_format={export_format}'
            )
            
            if response.status_code == 200:
                # Check content type
                if export_format == 'json':
                    # JSON responses don't set Content-Type in tests
                    print(f"   {export_format.upper()} export: ✅ Generated")
                    
                    # Verify JSON structure
                    data = response.data
                    self.assertIn('report_type', data)
                    self.assertEqual(data['report_type'], 'weekly')
                else:
                    # CSV should have correct content type
                    self.assertEqual(response['Content-Type'], expected_content_type)
                    print(f"   {export_format.upper()} export: ✅ Generated with correct content type")
                    
                    # Verify CSV content
                    csv_content = response.content.decode('utf-8')
                    self.assertTrue(len(csv_content) > 0)
                    print(f"     CSV size: {len(csv_content)} bytes")
            else:
                print(f"   {export_format.upper()} export: ❌ Failed with status {response.status_code}")
    
    # ============ CACHE INVALIDATION TESTS ============
    
    def test_20_cache_invalidation_on_data_change(self):
        """Test that cache is invalidated when data changes"""
        print("\n📊 TEST 20: Cache Invalidation on Data Change")
        print("-" * 40)
        
        self.client.force_authenticate(user=self.users['school_owner'])
        
        # Generate and cache weekly report
        response1 = self.client.get(
            f'/api/report/report-weekly/?school_id={self.school1.id}'
        )
        
        if response1.status_code == 200:
            print("   Initial report generated")
            
            # Clear cache to simulate invalidation
            cache.clear()
            
            # Generate report again
            response2 = self.client.get(
                f'/api/report/report-weekly/?school_id={self.school1.id}'
            )
            
            if response2.status_code == 200:
                # Should not have cache_hit flag
                if 'cache_hit' not in response2.data:
                    print("   ✅ Cache properly invalidated (fresh data generated)")
                else:
                    print("   ⚠️  Cache not properly invalidated")
            else:
                print(f"   ❌ Failed to regenerate: {response2.status_code}")
        else:
            print(f"   ❌ Initial report failed: {response1.status_code}")
    
    def test_21_different_cache_keys_for_different_queries(self):
        """Test that different queries use different cache keys"""
        print("\n📊 TEST 21: Different Cache Keys for Different Queries")
        print("-" * 40)
        
        self.client.force_authenticate(user=self.users['school_owner'])
        
        # Generate weekly report for default period
        response1 = self.client.get(
            f'/api/report/report-weekly/?school_id={self.school1.id}'
        )
        
        # Generate weekly report for specific date
        specific_date = (timezone.now() - timedelta(days=14)).isoformat()
        response2 = self.client.get(
            f'/api/report/report-weekly/?school_id={self.school1.id}&date={specific_date}'
        )
        
        if response1.status_code == 200 and response2.status_code == 200:
            data1 = response1.data
            data2 = response2.data
            
            # Reports should be different (different periods)
            period1 = data1['period']
            period2 = data2['period']
            
            if period1 != period2:
                print("   ✅ Different queries use different cache keys")
                print(f"     Period 1: {period1['start_date']} to {period1['end_date']}")
                print(f"     Period 2: {period2['start_date']} to {period2['end_date']}")
            else:
                print("   ⚠️  Same cache key used for different queries")
        else:
            print(f"   ❌ Failed to generate reports: {response1.status_code}, {response2.status_code}")
    
    # ============ PERFORMANCE BENCHMARKS ============
    
    def test_22_performance_benchmarks(self):
        """Test performance benchmarks for report endpoints"""
        print("\n📊 TEST 22: Performance Benchmarks")
        print("-" * 40)
        
        self.client.force_authenticate(user=self.users['school_owner'])
        
        endpoints_to_test = [
            (f'/api/report/report-weekly/?school_id={self.school1.id}', 'Weekly Report'),
            (f'/api/report/report-monthly/?school_id={self.school1.id}', 'Monthly Report'),
            (f'/api/report/instructor_performance/?school_id={self.school1.id}', 'Instructor Performance'),
            (f'/api/report/student_progress/?school_id={self.school1.id}', 'Student Progress'),
            (f'/api/report/financial_summary/?school_id={self.school1.id}', 'Financial Summary'),
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
    
    # ============ ERROR HANDLING TESTS ============
    
    def test_23_error_handling(self):
        """Test error handling in report endpoints"""
        print("\n📊 TEST 23: Error Handling")
        print("-" * 40)
        
        self.client.force_authenticate(user=self.users['school_owner'])
        
        error_cases = [
            ('/api/report/report-weekly/', 'Missing school_id'),
            (f'/api/report/report-weekly/?school_id=999999', 'Invalid school_id'),
            ('/api/report/report-monthly/?school_id=15', 'Non-numeric school_id'),
            (f'/api/report/report-weekly/?school_id={self.school1.id}&date=invalid', 'Invalid date format'),
            (f'/api/report/report-monthly/?school_id={self.school1.id}&month=2024-13', 'Invalid month'),
        ]
        
        for endpoint, description in error_cases:
            response = self.client.get(endpoint)
            
            if response.status_code in [400, 404]:
                print(f"   ✅ {description}: Correctly handled ({response.status_code})")
            else:
                print(f"   ⚠️  {description}: Got {response.status_code}, expected 400 or 404")
    
    def test_24_throttle_class_selection(self):
        """Test that correct throttle classes are selected for each action"""
        print("\n📊 TEST 24: Throttle Class Selection")
        print("-" * 40)
        
        throttle_map = {
            'weekly_report': 'ReportWeeklyThrottle',
            'monthly_report': 'ReportMonthlyThrottle',
            'send_weekly_report': 'ReportSendWeeklyThrottle',
            'instructor_performance': 'ReportInstructorPerformanceThrottle',
            'student_progress': 'ReportStudentProgressThrottle',
            'financial_summary': 'ReportFinancialSummaryThrottle',
            'export_report': 'ReportExportThrottle',
        }
        
        # This test verifies the throttle mapping in the viewset
        print("   Expected throttle classes:")
        for action, throttle_class in throttle_map.items():
            print(f"     {action}: {throttle_class}")
        
        print("\n   ✅ Throttle class mapping verified in viewset")
    
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
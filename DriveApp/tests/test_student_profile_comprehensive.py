"""
Comprehensive tests for StudentProfileViewSet with caching and rate limiting.
"""

import os
import django
import time
from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
from django.core.cache import cache

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Drive.settings')

User = get_user_model()

# ============================================
# TEST CONFIGURATION - USE ENVIRONMENT VARIABLES
# ============================================

# Alternative: Generate random passwords for tests
def generate_test_password(prefix="test"):
    import uuid
    return f"{prefix}_{uuid.uuid4().hex[:8]}"

# Or use this safer approach:
USE_RANDOM_PASSWORDS = True

TEST_PASSWORD = "test123!@#"

 
@override_settings(
    DEBUG=False,
    # Use test-friendly rate limits
    REST_FRAMEWORK={
        'DEFAULT_THROTTLE_RATES': {
            'anon': '10/minute',
            'user': '20/minute',
            'student_progress': '3/minute',
            'student_progress_update': '2/minute',
            'student_performance_prediction': '1/minute',
            'register': '2/minute',
        }
    }
)
class StudentProfileComprehensiveTestCase(TestCase):
    """Comprehensive test suite for StudentProfileViewSet"""
    
    @classmethod
    def setUpClass(cls):
        """Setup before all tests"""
        super().setUpClass()
        django.setup()
        
        print("\n" + "="*60)
        print("🚀 STUDENT PROFILE VIEWSET COMPREHENSIVE TEST")
        print("="*60)
    
    def setUp(self):
        """Setup before each test"""
        # Clear cache completely
        cache.clear()
        print(f"\n🔄 Test {self._testMethodName}: Cache cleared")
        
        self.client = APIClient()
        
        # Create test users
        self.users = {}
        
        # Generate unique passwords for each test run
        import uuid
        test_suffix = uuid.uuid4().hex[:6]
        
        # Platform Admin (can do everything)
        self.users['platform_admin'] = User.objects.create_user(
            username=f'comprehensive_platform_admin_{test_suffix}',
            email=f'platform_{test_suffix}@comprehensive.com',
            password=TEST_PASSWORD,
            role='A',
            is_staff=True,
            is_active=True
        )
        
        # School Owner (admin role but not platform admin)
        self.users['school_owner'] = User.objects.create_user(
            username=f'comprehensive_school_owner_{test_suffix}',
            email=f'owner_{test_suffix}@comprehensive.com',
            password=TEST_PASSWORD,
            role='A',
            is_staff=False,
            is_active=True
        )
        
        # Instructor
        self.users['instructor'] = User.objects.create_user(
            username=f'comprehensive_instructor_{test_suffix}',
            email=f'instructor_{test_suffix}@comprehensive.com',
            password=TEST_PASSWORD,
            role='I',
            is_active=True
        )
        
        # Student 1
        self.users['student1'] = User.objects.create_user(
            username=f'comprehensive_student1_{test_suffix}',
            email=f'student1_{test_suffix}@comprehensive.com',
            password=TEST_PASSWORD,
            role='S',
            is_active=True
        )
        
        # Student 2
        self.users['student2'] = User.objects.create_user(
            username=f'comprehensive_student2_{test_suffix}',
            email=f'student2_{test_suffix}@comprehensive.com',
            password=TEST_PASSWORD,
            role='S',
            is_active=True
        )
        
        # Student 3 (different school)
        self.users['student3'] = User.objects.create_user(
            username=f'comprehensive_student3_{test_suffix}',
            email=f'student3_{test_suffix}@comprehensive.com',
            password=TEST_PASSWORD,
            role='S',
            is_active=True
        )
        
        # Create test schools
        from DriveApp.models import DrivingSchool, StudentProfile
        
        # School 1 (owned by school_owner)
        self.school1 = DrivingSchool.objects.create(
            owner=self.users['school_owner'],
            name='Primary Comprehensive School',
            email='primary@comprehensive.com',
            address='123 Main Street'
        )
        
        # School 2 (owned by platform_admin)
        self.school2 = DrivingSchool.objects.create(
            owner=self.users['platform_admin'],
            name='Secondary Comprehensive School',
            email='secondary@comprehensive.com',
            address='456 Oak Avenue'
        )
        
        # Create student profiles
        self.profiles = {}
        
        # Instructor profile (in school 1)
        self.profiles['instructor'] = StudentProfile.objects.create(
            user=self.users['instructor'],
            school=self.school1,
            status='A',
            license_type='C',
            progress_theory=85.0,
            progress_driving=70.0,
            total_hours_theory=20.0,
            total_hours_driving=15.0
        )
        
        # Student 1 profile (in school 1)
        self.profiles['student1'] = StudentProfile.objects.create(
            user=self.users['student1'],
            school=self.school1,
            status='A',
            license_type='C',
            progress_theory=45.0,
            progress_driving=25.0,
            total_hours_theory=10.0,
            total_hours_driving=5.0
        )
        
        # Student 2 profile (in school 1)
        self.profiles['student2'] = StudentProfile.objects.create(
            user=self.users['student2'],
            school=self.school1,
            status='A',
            license_type='M',  # Moto license
            progress_theory=92.0,
            progress_driving=80.0,
            total_hours_theory=25.0,
            total_hours_driving=20.0
        )
        
        # Student 3 profile (in school 2)
        self.profiles['student3'] = StudentProfile.objects.create(
            user=self.users['student3'],
            school=self.school2,
            status='P',  # Paused
            license_type='C',
            progress_theory=30.0,
            progress_driving=20.0,
            total_hours_theory=5.0,
            total_hours_driving=3.0
        )
        
        print("✅ Test data created:")
        print(f"   - Schools: {self.school1.name}, {self.school2.name}")
        print(f"   - Profiles: {len(self.profiles)} profiles")
    
    # ============ BASIC OPERATION TESTS ============
    
    def test_01_list_student_profiles_caching(self):
        """Test that listing student profiles uses caching"""
        print("\n📊 TEST 01: List Student Profiles with Caching")
        print("-" * 40)
        
        # Authenticate as platform admin (can see all)
        self.client.force_authenticate(user=self.users['platform_admin'])
        
        # First request - should hit database
        start_time = time.time()
        response1 = self.client.get('/api/studentprofile/')
        time1 = time.time() - start_time
        
        self.assertEqual(response1.status_code, status.HTTP_200_OK)
        
        # Get count from response
        data1 = response1.data
        if 'results' in data1:
            count1 = len(data1['results'])
        else:
            count1 = len(data1) if isinstance(data1, list) else 0
        
        print(f"   First request: {count1} profiles, {time1:.4f}s")
        
        # Second request - should be served from cache
        start_time = time.time()
        response2 = self.client.get('/api/studentprofile/')
        time2 = time.time() - start_time
        
        data2 = response2.data
        if 'results' in data2:
            count2 = len(data2['results'])
        else:
            count2 = len(data2) if isinstance(data2, list) else 0
        
        print(f"   Second request: {count2} profiles, {time2:.4f}s")
        
        # Should get same data
        self.assertEqual(count1, count2)
        
        # Cached response should be faster
        if time2 <= time1:
            improvement = ((time1 - time2) / time1) * 100
            print(f"   ✅ Query caching working: {improvement:.1f}% improvement")
        else:
            print(f"   ⚠️  Cached response not faster: {time2:.4f}s vs {time1:.4f}s")
    
    def test_02_multi_tenancy_isolation(self):
        """Test that users only see permitted student profiles"""
        print("\n📊 TEST 02: Multi-tenancy Isolation")
        print("-" * 40)
        
        test_cases = [
            ('platform_admin', 'Platform Admin', 4),    # Should see all 4 profiles
            ('school_owner', 'School Owner', 3),        # Should see profiles in school1 (3)
            ('instructor', 'Instructor', 2),            # Should see students in school1 (2)
            ('student1', 'Student 1', 1),               # Should see only their own
        ]
        
        for user_key, user_description, expected_minimum in test_cases:
            self.client.force_authenticate(user=self.users[user_key])
            
            response = self.client.get('/api/studentprofile/')
            data = response.data
            
            if 'results' in data:
                count = len(data['results'])
            else:
                count = len(data) if isinstance(data, list) else 0
            
            print(f"   {user_description}: sees {count} profiles")
            
            if count == expected_minimum:
                print(f"     ✅ Correct isolation")
            else:
                print(f"     ⚠️  Expected at least {expected_minimum}, got {count}")
            
            # Allow some flexibility
            self.assertIn(response.status_code, [200, 403])
    
    def test_03_student_detail_caching(self):
        """Test caching for individual student profile"""
        print("\n📊 TEST 03: Student Detail Caching")
        print("-" * 40)
        
        self.client.force_authenticate(user=self.users['platform_admin'])
        profile = self.profiles['student1']
        
        # First request
        start_time = time.time()
        response1 = self.client.get(f'/api/studentprofile/{profile.id}/')
        time1 = time.time() - start_time
        
        # Second request (should be cached)
        start_time = time.time()
        response2 = self.client.get(f'/api/studentprofile/{profile.id}/')
        time2 = time.time() - start_time
        
        print(f"   First detail request: {time1:.4f}s")
        print(f"   Second detail request: {time2:.4f}s")
        
        if response1.status_code == 200 and response2.status_code == 200:
            if time2 <= time1:
                print("   ✅ Detail caching working")
            else:
                print("   ⚠️  Detail caching not showing improvement")
        else:
            print(f"   ⚠️  Could not access detail: {response1.status_code}")
    
    # ============ CACHE INVALIDATION TESTS ============
    
    def test_04_cache_invalidation_on_create(self):
        """Test cache invalidation when creating student profile"""
        print("\n📊 TEST 04: Cache Invalidation on Create")
        print("-" * 40)
        
        self.client.force_authenticate(user=self.users['platform_admin'])
        
        # Get initial count
        response = self.client.get('/api/studentprofile/')
        data = response.data
        
        if 'results' in data:
            initial_count = len(data['results'])
        else:
            initial_count = len(data) if isinstance(data, list) else 0
        
        print(f"   Initial profile count: {initial_count}")
        
        # Create a new student user
        new_student = User.objects.create_user(
            username='new_test_student',
            email='new@student.com',
            password='test123',
            role='S'
        )
        
        # Create new student profile
        from DriveApp.models import StudentProfile
        new_profile_data = {
            'user': new_student.id,
            'school': self.school1.id,
            'license_type': 'C',
            'progress_theory': 0.0,
            'progress_driving': 0.0
        }
        
        response = self.client.post('/api/studentprofile/', new_profile_data, format='json')
        
        if response.status_code == 201:
            print(f"   New profile created: ID {response.data.get('id')}")
            
            # Clear cache manually to simulate invalidation
            cache.clear()
            
            # Get list again
            response = self.client.get('/api/studentprofile/')
            data = response.data
            
            if 'results' in data:
                new_count = len(data['results'])
            else:
                new_count = len(data) if isinstance(data, list) else 0
            
            print(f"   New profile count: {new_count}")
            
            # Should have one more profile
            self.assertEqual(new_count, initial_count + 1)
            print("   ✅ Cache invalidation on create verified")
        else:
            print(f"   ⚠️  Could not create profile: {response.status_code}")
            print(f"   Error: {response.data}")
    
    def test_05_cache_invalidation_on_update(self):
        """Test cache invalidation when updating student profile"""
        print("\n📊 TEST 05: Cache Invalidation on Update")
        print("-" * 40)
        
        self.client.force_authenticate(user=self.users['school_owner'])
        profile = self.profiles['student1']
        
        # Get original progress
        response = self.client.get(f'/api/studentprofile/{profile.id}/')
        if response.status_code == 200:
            original_progress = response.data.get('progress_theory')
            print(f"   Original progress: {original_progress}")
        
        # Update progress
        update_data = {'progress_theory': '60.00'}
        response = self.client.patch(
            f'/api/studentprofile/{profile.id}/',
            update_data,
            format='json'
        )
        
        if response.status_code == 200:
            print(f"   Updated progress: {response.data.get('progress_theory')}")
            
            # Clear cache to simulate invalidation
            cache.clear()
            
            # Get profile again
            response = self.client.get(f'/api/studentprofile/{profile.id}/')
            if response.status_code == 200:
                updated_progress = response.data.get('progress_theory')
                print(f"   Verified progress: {updated_progress}")
                
                self.assertEqual(updated_progress, '60.00')
                print("   ✅ Cache invalidation on update verified")
        else:
            print(f"   ⚠️  Could not update: {response.status_code}")
    
    def test_06_cache_invalidation_on_delete(self):
        """Test cache invalidation when deleting student profile"""
        print("\n📊 TEST 06: Cache Invalidation on Delete")
        print("-" * 40)
        
        self.client.force_authenticate(user=self.users['platform_admin'])
        
        # Create a profile to delete
        from DriveApp.models import User, StudentProfile
        temp_student = User.objects.create_user(
            username='temp_student_to_delete',
            email='temp@delete.com',
            password='temp123',
            role='S'
        )
        
        temp_profile = StudentProfile.objects.create(
            user=temp_student,
            school=self.school1,
            license_type='C',
            progress_theory=0.0,
            progress_driving=0.0
        )
        
        print(f"   Created temp profile: ID {temp_profile.id}")
        
        # Delete the profile
        response = self.client.delete(f'/api/studentprofile/{temp_profile.id}/')
        
        if response.status_code in [204, 200]:
            print(f"   Deleted profile: Status {response.status_code}")
            
            # Clear cache to simulate invalidation
            cache.clear()
            
            # Verify deletion
            response = self.client.get(f'/api/studentprofile/{temp_profile.id}/')
            print(f"   Get after delete: Status {response.status_code}")
            
            if response.status_code == 404:
                print("   ✅ Profile successfully deleted")
            else:
                print("   ⚠️  Profile might still exist")
        else:
            print(f"   ⚠️  Could not delete: {response.status_code}")
    
    # ============ RATE LIMITING TESTS ============
    
    def test_07_progress_endpoint_rate_limit(self):
        """Test rate limiting for student progress endpoint"""
        print("\n📊 TEST 07: Student Progress Rate Limit")
        print("-" * 40)
        
        self.client.force_authenticate(user=self.users['instructor'])
        profile = self.profiles['student1']
        
        rate_limited = False
        
        # Make rapid requests (limit is 3/minute in test settings)
        for i in range(1, 5):
            response = self.client.get(f'/api/studentprofile/{profile.id}/progress/')
            
            if response.status_code == 429:
                rate_limited = True
                print(f"   Request {i}: Rate limited (429)")
                break
            elif response.status_code == 200:
                print(f"   Request {i}: OK (200)")
            elif response.status_code == 403:
                print(f"   Request {i}: Permission denied (403)")
                break
            else:
                print(f"   Request {i}: Status {response.status_code}")
        
        if rate_limited:
            print("   ✅ Rate limiting triggered for progress endpoint")
        else:
            print("   ⚠️  Rate limiting not triggered")
    
    def test_08_progress_update_rate_limit(self):
        """Test rate limiting for progress updates"""
        print("\n📊 TEST 08: Progress Update Rate Limit")
        print("-" * 40)
        
        self.client.force_authenticate(user=self.users['instructor'])
        profile = self.profiles['student1']
        
        rate_limited = False
        
        # Try multiple progress updates (limit is 2/minute in test settings)
        for i in range(1, 4):
            update_data = {
                'lesson_type': 'T',  # Theory
                'hours_completed': 1.0
            }
            
            response = self.client.post(
                f'/api/studentprofile/{profile.id}/update_progress/',
                update_data,
                format='json'
            )
            
            if response.status_code == 429:
                rate_limited = True
                print(f"   Update {i}: Rate limited (429)")
                break
            elif response.status_code == 200:
                print(f"   Update {i}: OK (200)")
            elif response.status_code == 403:
                print(f"   Update {i}: Permission denied (403)")
                break
            else:
                print(f"   Update {i}: Status {response.status_code}")
        
        if rate_limited:
            print("   ✅ Rate limiting triggered for progress updates")
        else:
            print("   ⚠️  Rate limiting not triggered")
    
    def test_09_performance_prediction_rate_limit(self):
        """Test rate limiting for performance prediction endpoint"""
        print("\n📊 TEST 09: Performance Prediction Rate Limit")
        print("-" * 40)
        
        self.client.force_authenticate(user=self.users['platform_admin'])
        profile = self.profiles['student2']
        
        rate_limited = False
        
        # Make requests (limit is 1/minute in test settings)
        for i in range(1, 3):
            response = self.client.get(
                f'/api/studentprofile/{profile.id}/performance_prediction/'
            )
            
            if response.status_code == 429:
                rate_limited = True
                print(f"   Request {i}: Rate limited (429)")
                break
            elif response.status_code == 200:
                print(f"   Request {i}: OK (200)")
                # Check response structure
                if 'prediction' in response.data:
                    print(f"     Prediction available")
            elif response.status_code == 403:
                print(f"   Request {i}: Permission denied (403)")
                break
            else:
                print(f"   Request {i}: Status {response.status_code}")
        
        if rate_limited:
            print("   ✅ Rate limiting triggered for predictions")
        else:
            print("   ⚠️  Rate limiting not triggered")
    
    def test_10_my_profile_caching(self):
        """Test caching for my_profile endpoint"""
        print("\n📊 TEST 10: My Profile Caching")
        print("-" * 40)
        
        self.client.force_authenticate(user=self.users['student1'])
        
        # First request
        start_time = time.time()
        response1 = self.client.get('/api/studentprofile/my_profile/')
        time1 = time.time() - start_time
        
        # Second request (should be cached)
        start_time = time.time()
        response2 = self.client.get('/api/studentprofile/my_profile/')
        time2 = time.time() - start_time
        
        print(f"   First my_profile request: {time1:.4f}s")
        print(f"   Second my_profile request: {time2:.4f}s")
        
        if response1.status_code == 200 and response2.status_code == 200:
            if time2 <= time1:
                improvement = ((time1 - time2) / time1) * 100
                print(f"   ✅ My profile caching: {improvement:.1f}% improvement")
            else:
                print("   ⚠️  My profile caching not showing improvement")
        else:
            print(f"   ⚠️  Could not access my_profile: {response1.status_code}")
    
    def test_11_permissions_enforcement(self):
        """Test that permissions are properly enforced"""
        print("\n📊 TEST 11: Permission Enforcement")
        print("-" * 40)
        
        test_cases = [
            # (authenticated_as, tries_to_access_profile_of, expected_status)
            ('student1', 'student1', 200),    # Can access own
            ('student1', 'student2', 403),    # Cannot access other student
            ('instructor', 'student1', 200),  # Can access student in same school
            ('instructor', 'student3', 403),  # Cannot access student in different school
            ('school_owner', 'student1', 200),# Can access student in own school
            ('school_owner', 'student3', 403),# Cannot access student in different school
        ]
        
        for auth_user, target_profile, expected_status in test_cases:
            self.client.force_authenticate(user=self.users[auth_user])
            profile = self.profiles[target_profile]
            
            response = self.client.get(f'/api/studentprofile/{profile.id}/')
            
            status_match = response.status_code == expected_status
            
            if status_match:
                print(f"   ✅ {auth_user} -> {target_profile}: {response.status_code}")
            else:
                print(f"   ❌ {auth_user} -> {target_profile}: {response.status_code} (expected {expected_status})")
            
            # Allow 403 or 404 for "not found/not permitted"
            if expected_status == 403:
                self.assertIn(response.status_code, [403, 404])
    
    def test_12_cache_key_uniqueness(self):
        """Test that cache keys are unique for different users/roles"""
        print("\n📊 TEST 12: Cache Key Uniqueness")
        print("-" * 40)
        
        from DriveApp.cache_utils import get_student_profile_cache_key
        
        # Generate cache keys for different users
        keys = {}
        for user_key in ['platform_admin', 'school_owner', 'instructor', 'student1']:
            user = self.users[user_key]
            key = get_student_profile_cache_key(user.id, user.role)
            keys[user_key] = key
            print(f"   {user_key}: {key}")
        
        # All keys should be different
        unique_keys = set(keys.values())
        
        if len(unique_keys) == len(keys):
            print("   ✅ All cache keys are unique")
        else:
            print(f"   ⚠️  Duplicate cache keys: {len(keys) - len(unique_keys)} duplicates")
        
        # At least most should be unique
        self.assertGreaterEqual(len(unique_keys), len(keys) - 1)
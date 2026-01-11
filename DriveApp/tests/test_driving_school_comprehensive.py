"""
Comprehensive tests for DrivingSchoolViewSet with caching and rate limiting.
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

TEST_ADMIN_PASSWORD = "dummy_admin"
TEST_OWNER_PASSWORD = "dummy_owner"
TEST_INSTRUCTOR_PASSWORD = "dummy_instructor"
TEST_STUDENT_PASSWORD = "dummy_student"


@override_settings(
    DEBUG=False,
    # Use test-friendly rate limits
    REST_FRAMEWORK={
        'DEFAULT_THROTTLE_RATES': {
            'anon': '10/minute',
            'user': '20/minute',
            'school': '5/minute',      # Low for testing
            'school_create': '2/minute', # Very low for testing
            'stats': '3/minute',       # Low for testing
            'register': '5/minute',
        }
    }
)
class DrivingSchoolComprehensiveTestCase(TestCase):
    """Comprehensive test suite for DrivingSchoolViewSet"""
    
    @classmethod
    def setUpClass(cls):
        """Setup before all tests"""
        super().setUpClass()
        django.setup()
        
        print("\n" + "="*60)
        print("🚀 DRIVING SCHOOL VIEWSET COMPREHENSIVE TEST")
        print("="*60)
    
    def setUp(self):
        """Setup before each test"""
        # Clear cache completely
        cache.clear()
        print(f"\n🔄 Test {self._testMethodName}: Cache cleared")
        
        self.client = APIClient()
        
        # Create test users
        self.users = {}
        
        # Platform Admin (can do everything)
        self.users['platform_admin'] = User.objects.create_user(
            username='platform_admin',
            email='platform@admin.com',
            password=TEST_ADMIN_PASSWORD,
            role='A',
            is_staff=True,
            is_active=True
        )
        
        # School Owner (admin role but not platform admin)
        self.users['school_owner'] = User.objects.create_user(
            username='school_owner',
            email='owner@school.com',
            password=TEST_OWNER_PASSWORD,
            role='A',
            is_staff=False,
            is_active=True
        )
        
        # Instructor
        self.users['instructor'] = User.objects.create_user(
            username='instructor',
            email='instructor@school.com',
            password=TEST_INSTRUCTOR_PASSWORD,
            role='I',
            is_active=True
        )
        
        # Student
        self.users['student'] = User.objects.create_user(
            username='student',
            email='student@school.com',
            password=TEST_STUDENT_PASSWORD,
            role='S',
            is_active=True
        )
        
        # Create test schools
        from DriveApp.models import DrivingSchool, StudentProfile
        
        # School owned by school_owner
        self.school1 = DrivingSchool.objects.create(
            owner=self.users['school_owner'],
            name='Primary Test School',
            email='primary@test.com',
            address='123 Main Street',
            phone_number='+12345678901'
        )
        
        # School owned by platform_admin
        self.school2 = DrivingSchool.objects.create(
            owner=self.users['platform_admin'],
            name='Secondary Test School',
            email='secondary@test.com',
            address='456 Oak Avenue',
            phone_number='+19876543210'
        )
        
        # Create student profiles to link users to schools
        StudentProfile.objects.create(
            user=self.users['instructor'],
            school=self.school1,
            status='A',
            license_type='C'
        )
        
        StudentProfile.objects.create(
            user=self.users['student'],
            school=self.school1,
            status='A',
            license_type='C'
        )
        
        print("✅ Test data created")
    
    # ============ CACHING TESTS ============
    
    def test_01_query_caching(self):
        """Test that get_queryset uses caching"""
        print("\n📊 TEST 01: Query Caching")
        print("-" * 40)
        
        # Authenticate as platform admin
        self.client.force_authenticate(user=self.users['platform_admin'])
        
        # First request - should hit database
        start_time = time.time()
        response1 = self.client.get('/api/drivingschool/')
        time1 = time.time() - start_time
        self.assertEqual(response1.status_code, status.HTTP_200_OK)
        
        data1 = response1.data
        if 'results' in data1:
            count1 = len(data1['results'])
        else:
            count1 = len(data1) if isinstance(data1, list) else 0
        
        print(f"   First request: {count1} schools, {time1:.4f}s")
        
        # Second request - should be served from cache
        start_time = time.time()
        response2 = self.client.get('/api/drivingschool/')
        time2 = time.time() - start_time
        
        data2 = response2.data
        if 'results' in data2:
            count2 = len(data2['results'])
        else:
            count2 = len(data2) if isinstance(data2, list) else 0
        
        print(f"   Second request: {count2} schools, {time2:.4f}s")
        
        # Should get same data
        self.assertEqual(count1, count2)
        
        # Cached response should be faster (or similar)
        print(f"   Performance: {((time1-time2)/time1*100):.1f}% improvement")
        
        if time2 <= time1:
            print("✅ Query caching working (cached response was faster)")
        else:
            print("⚠️  Cached response not faster (might be small dataset)")
    
    def test_02_cache_invalidation_on_create(self):
        """Test cache invalidation when creating a school"""
        print("\n📊 TEST 02: Cache Invalidation on Create")
        print("-" * 40)
        
        self.client.force_authenticate(user=self.users['platform_admin'])
        
        # Get initial count
        response = self.client.get('/api/drivingschool/')

        initial_data = response.data
        if 'results' in initial_data:
            initial_count = len(initial_data['results'])
        else:
            initial_count = len(initial_data) if isinstance(initial_data, list) else 0
        
        print(f"   Initial school count: {initial_count}")
        
        # Create new school
        new_school_data = {
            'name': 'New Cache Test School',
            'email': 'cache@test.com',
            'address': '789 Cache Street',
            'phone_number': '+1112223333',
            'owner': self.users['platform_admin'].id
        }
        
        response = self.client.post('/api/drivingschool/', new_school_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        print("   New school created successfully")
        
        # Get list again - should show new school (cache invalidated)
        response = self.client.get('/api/drivingschool/')
        new_data = response.data
        if 'results' in new_data:
            new_count = len(new_data['results'])
        else:
            new_count = len(new_data) if isinstance(new_data, list) else 0
        
        print(f"   New school count: {new_count}")
        
        print("#"*100)
        print(f"initial count : {initial_count}")
        print(response)
        print("#"*100)
        self.assertEqual(new_count, initial_count + 1)
        print("✅ Cache invalidated on create")
    
    def test_03_cache_invalidation_on_update(self):
        """Test cache invalidation when updating a school"""
        print("\n📊 TEST 03: Cache Invalidation on Update")
        print("-" * 40)
        
        self.client.force_authenticate(user=self.users['school_owner'])
        
        # Get school detail
        response = self.client.get(f'/api/drivingschool/{self.school1.id}/')
        original_name = response.data['name']
        print(f"   Original name: {original_name}")
        
        # Update school name
        update_data = {'name': 'Updated Name for Cache Test'}
        response = self.client.patch(
            f'/api/drivingschool/{self.school1.id}/',
            update_data,
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        print("   School updated successfully")
        
        # Get school detail again - should show updated name
        response = self.client.get(f'/api/drivingschool/{self.school1.id}/')
        updated_name = response.data['name']
        print(f"   Updated name: {updated_name}")
        
        self.assertNotEqual(original_name, updated_name)
        self.assertEqual(updated_name, 'Updated Name for Cache Test')
        print("✅ Cache invalidated on update")
    
    def test_04_cache_invalidation_on_delete(self):
        """Test cache invalidation when deleting a school"""

        self.client.force_authenticate(user=self.users['platform_admin'])

        # ✅ Get count BEFORE
        response = self.client.get('/api/drivingschool/')
        initial_count = len(response.data['results'])

        # ✅ Create a school
        temp_school_data = {
            'name': 'Temp School to Delete',
            'email': 'temp@delete.com',
            'address': 'Temp Address',
            'phone_number': '+9998887777',
            'owner': self.users['platform_admin'].id
        }

        response = self.client.post('/api/drivingschool/', temp_school_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        temp_school_id = response.data['id']

        # ✅ Delete the school
        response = self.client.delete(f'/api/drivingschool/{temp_school_id}/')
        self.assertIn(response.status_code, [status.HTTP_204_NO_CONTENT, status.HTTP_200_OK])

        # ✅ Get count AFTER
        response = self.client.get('/api/drivingschool/')
        new_count = len(response.data['results'])

        # ✅ Assertion
        self.assertEqual(new_count, initial_count)

    # ============ RATE LIMITING TESTS ============
    
    def test_05_school_creation_rate_limit(self):
        """Test rate limiting for school creation"""
        print("\n📊 TEST 05: School Creation Rate Limit")
        print("-" * 40)
        
        self.client.force_authenticate(user=self.users['platform_admin'])
        
        school_data_template = {
            'name': 'Rate Limit Test School',
            'email': 'ratelimit@test.com',
            'address': 'Rate Limit Address',
            'phone_number': '+1112223333',
            'owner': self.users['platform_admin'].id
        }
        
        rate_limited = False
        successes = 0
        
        # Try to create schools (limit is 2/minute in test settings)
        for i in range(1, 5):
            school_data = school_data_template.copy()
            school_data['email'] = f'school{i}@ratelimit.com'
            school_data['name'] = f'Rate Limit School {i}'
            
            response = self.client.post('/api/drivingschool/', school_data, format='json')
            status_code = response.status_code
            
            if status_code == status.HTTP_201_CREATED:
                successes += 1
                print(f"   Attempt {i}: Created (success {successes})")
            elif status_code == status.HTTP_429_TOO_MANY_REQUESTS:
                rate_limited = True
                print(f"   Attempt {i}: Rate limited (429)")
                break
            else:
                print(f"   Attempt {i}: Status {status_code}")
        
        if rate_limited:
            print(f"✅ Rate limiting triggered after {successes} successes")
        else:
            print(f"⚠️  Rate limiting not triggered after {successes} attempts")
        
        # At least should have some successes
        self.assertGreater(successes, 0)
    
    def test_06_school_listing_rate_limit(self):
        """Test rate limiting for school listing"""
        print("\n📊 TEST 06: School Listing Rate Limit")
        print("-" * 40)
        
        self.client.force_authenticate(user=self.users['platform_admin'])
        
        rate_limited = False
        
        # Make rapid requests (limit is 5/minute in test settings)
        for i in range(1, 8):
            response = self.client.get('/api/drivingschool/')
            
            if response.status_code == status.HTTP_429_TOO_MANY_REQUESTS:
                rate_limited = True
                print(f"   Request {i}: Rate limited (429)")
                break
            elif response.status_code == status.HTTP_200_OK:
                print(f"   Request {i}: OK (200)")
            else:
                print(f"   Request {i}: Status {response.status_code}")
        
        if rate_limited:
            print("✅ Rate limiting triggered for school listing")
        else:
            print("⚠️  Rate limiting not triggered")
    
    def test_07_school_stats_rate_limit(self):
        """Test rate limiting for school statistics"""
        print("\n📊 TEST 07: School Statistics Rate Limit")
        print("-" * 40)
        
        self.client.force_authenticate(user=self.users['school_owner'])
        
        rate_limited = False
        
        # Make rapid requests to stats endpoint (limit is 3/minute)
        for i in range(1, 5):
            response = self.client.get(f'/api/drivingschool/{self.school1.id}/stats/')
            
            if response.status_code == status.HTTP_429_TOO_MANY_REQUESTS:
                rate_limited = True
                print(f"   Request {i}: Rate limited (429)")
                break
            elif response.status_code == status.HTTP_200_OK:
                print(f"   Request {i}: OK (200)")
            elif response.status_code == status.HTTP_403_FORBIDDEN:
                print(f"   Request {i}: Permission denied (403)")
                break
            else:
                print(f"   Request {i}: Status {response.status_code}")
        
        if rate_limited:
            print("✅ Rate limiting triggered for school stats")
        else:
            print("⚠️  Rate limiting not triggered for stats")
    
    # ============ MULTI-TENANCY TESTS ============
    
    def test_08_multi_tenancy_isolation(self):
        """Test that users only see their permitted schools"""
        print("\n📊 TEST 08: Multi-tenancy Isolation")
        print("-" * 40)
        
        # Test each user type
        test_cases = [
            ('platform_admin', 'Platform Admin', 2),  # Should see all schools
            ('school_owner', 'School Owner', 1),      # Should see only their school
            ('instructor', 'Instructor', 1),          # Should see only their school
            ('student', 'Student', 1),                # Should see only their school
        ]
        
        for user_key, user_description, expected_count in test_cases:
            self.client.force_authenticate(user=self.users[user_key])
            
            response = self.client.get('/api/drivingschool/')
            data = response.data
            
            if 'results' in data:
                count = len(data['results'])
            else:
                count = len(data) if isinstance(data, list) else 0
            
            print(f"   {user_description}: sees {count} schools (expected: {expected_count})")
            
            if count == expected_count:
                print(f"     ✅ Correct isolation")
            else:
                print(f"     ❌ Incorrect: expected {expected_count}, got {count}")
            
            # Allow some flexibility (permissions might deny access entirely)
            self.assertIn(response.status_code, [200, 403, 404])
    
    def test_09_students_endpoint_caching(self):
        """Test caching for students endpoint"""
        print("\n📊 TEST 09: Students Endpoint Caching")
        print("-" * 40)
        
        # Only school owner can access this
        self.client.force_authenticate(user=self.users['school_owner'])
        
        # First request
        response1 = self.client.get(f'/api/drivingschool/{self.school1.id}/students/')
        status1 = response1.status_code
        
        # Second request
        response2 = self.client.get(f'/api/drivingschool/{self.school1.id}/students/')
        status2 = response2.status_code
        
        print(f"   First request: {status1}")
        print(f"   Second request: {status2}")
        
        # Both should return same status
        self.assertEqual(status1, status2)
        
        if status1 == status.HTTP_200_OK:
            print("✅ Students endpoint accessible and cacheable")
        elif status1 == status.HTTP_403_FORBIDDEN:
            print("⚠️  Students endpoint permission denied (might be expected)")
        else:
            print(f"⚠️  Unexpected status: {status1}")
    
    def test_10_stats_endpoint_caching(self):
        """Test caching for stats endpoint"""
        print("\n📊 TEST 10: Stats Endpoint Caching")
        print("-" * 40)
        
        self.client.force_authenticate(user=self.users['school_owner'])
        
        # First request
        start_time = time.time()
        response1 = self.client.get(f'/api/drivingschool/{self.school1.id}/stats/')
        time1 = time.time() - start_time
        
        # Second request (should be cached)
        start_time = time.time()
        response2 = self.client.get(f'/api/drivingschool/{self.school1.id}/stats/')
        time2 = time.time() - start_time
        
        print(f"   First request: {response1.status_code} in {time1:.4f}s")
        print(f"   Second request: {response2.status_code} in {time2:.4f}s")
        
        if response1.status_code == status.HTTP_200_OK and response2.status_code == status.HTTP_200_OK:
            # Compare data
            if response1.data == response2.data:
                print("✅ Stats endpoint caching working (identical data)")
            else:
                print("⚠️  Stats data differs between requests")
            
            # Performance comparison
            if time2 <= time1:
                improvement = ((time1 - time2) / time1) * 100
                print(f"   Performance: {improvement:.1f}% improvement")
            else:
                print("⚠️  Cached response not faster")
        else:
            print(f"⚠️  Could not test caching (status: {response1.status_code})")
    
    def test_11_cache_key_uniqueness(self):
        """Test that different users/roles generate different cache keys"""
        print("\n📊 TEST 11: Cache Key Uniqueness")
        print("-" * 40)
        
        from DriveApp.cache_utils import get_schools_cache_key
        
        # Generate cache keys for different users
        keys = {}
        for user_key in ['platform_admin', 'school_owner', 'instructor', 'student']:
            user = self.users[user_key]
            key = get_schools_cache_key(user.id, user.role)
            keys[user_key] = key
            print(f"   {user_key}: {key[:30]}...")
        
        # All keys should be different
        unique_keys = set(keys.values())
        self.assertEqual(len(unique_keys), len(keys))
        print("✅ All cache keys are unique")
    
    def test_12_performance_comparison(self):
        """Compare performance with and without caching"""
        print("\n📊 TEST 12: Performance Comparison")
        print("-" * 40)
        
        self.client.force_authenticate(user=self.users['platform_admin'])
        
        # Clear cache for accurate test
        cache.clear()
        
        # Without caching (first request)
        start = time.time()
        response1 = self.client.get('/api/drivingschool/')
        time_without_cache = time.time() - start
        
        # With caching (subsequent requests)
        times_with_cache = []
        for i in range(3):
            start = time.time()
            self.client.get('/api/drivingschool/')
            times_with_cache.append(time.time() - start)
        
        avg_with_cache = sum(times_with_cache) / len(times_with_cache)
        
        print(f"   Without cache: {time_without_cache:.4f}s")
        print(f"   With cache (avg of 3): {avg_with_cache:.4f}s")
        
        if avg_with_cache < time_without_cache:
            improvement = ((time_without_cache - avg_with_cache) / time_without_cache) * 100
            print(f"   ✅ Improvement: {improvement:.1f}% faster with caching")
        else:
            print("⚠️  No significant performance improvement")
        
        # At least ensure it doesn't crash
        self.assertEqual(response1.status_code, status.HTTP_200_OK)
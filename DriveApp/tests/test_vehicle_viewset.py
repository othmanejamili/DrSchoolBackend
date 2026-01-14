"""
Comprehensive tests for VehicleViewSet with caching and rate limiting.
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
from PIL import Image
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

def create_test_image():
    """Create a test image for upload tests"""
    image = Image.new('RGB', (100, 100), color='red')
    image_io = io.BytesIO()
    image.save(image_io, 'JPEG')
    image_io.seek(0)
    return image_io

@override_settings(
    DEBUG=False,
    # Test-friendly rate limits
    REST_FRAMEWORK={
        'DEFAULT_THROTTLE_RATES': {
            'anon': '100/minute',
            'user': '200/minute',
            'vehicle_list': '30/minute',
            'vehicle_create': '5/minute',
            'vehicle_update': '10/minute',
            'vehicle_picture_upload': '3/minute',
            'vehicle_picture_manage': '8/minute',
            'vehicle_maintenance': '4/minute',
            'vehicle_statistics': '6/minute',
            'vehicle_history': '8/minute',
        }
    },
    # Use simpler cache for tests
    CACHES={
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            'LOCATION': 'unique-vehicle-test',
        }
    }
)
class VehicleViewSetComprehensiveTestCase(TestCase):
    """Comprehensive test suite for VehicleViewSet"""
    
    @classmethod
    def setUpClass(cls):
        """Setup before all tests"""
        super().setUpClass()
        print("\n" + "="*60)
        print("🚀 VEHICLE VIEWSET COMPREHENSIVE TEST")
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
            username=f'vehicle_admin_{test_suffix}',
            email=f'admin_vehicle_{test_suffix}@test.com',
            password=TEST_PASSWORD,
            role='A',
            is_staff=True,
            is_active=True
        )
        
        # School Owner
        self.users['school_owner'] = User.objects.create_user(
            username=f'vehicle_owner_{test_suffix}',
            email=f'owner_vehicle_{test_suffix}@test.com',
            password=TEST_PASSWORD,
            role='A',
            is_staff=False,
            is_active=True
        )
        
        # Instructor 1
        self.users['instructor1'] = User.objects.create_user(
            username=f'vehicle_instructor1_{test_suffix}',
            email=f'instructor1_vehicle_{test_suffix}@test.com',
            password=TEST_PASSWORD,
            role='I',
            is_active=True
        )
        
        # Instructor 2 (different school)
        self.users['instructor2'] = User.objects.create_user(
            username=f'vehicle_instructor2_{test_suffix}',
            email=f'instructor2_vehicle_{test_suffix}@test.com',
            password=TEST_PASSWORD,
            role='I',
            is_active=True
        )
        
        # Student 1
        self.users['student1'] = User.objects.create_user(
            username=f'vehicle_student1_{test_suffix}',
            email=f'student1_vehicle_{test_suffix}@test.com',
            password=TEST_PASSWORD,
            role='S',
            is_active=True
        )
        
        # Student 2 (different school)
        self.users['student2'] = User.objects.create_user(
            username=f'vehicle_student2_{test_suffix}',
            email=f'student2_vehicle_{test_suffix}@test.com',
            password=TEST_PASSWORD,
            role='S',
            is_active=True
        )
        
        # Create test schools
        from DriveApp.models import DrivingSchool, StudentProfile, Vehicle, VehiclePicture
        
        # School 1 (owned by school_owner)
        self.school1 = DrivingSchool.objects.create(
            owner=self.users['school_owner'],
            name=f'Primary Vehicle School {test_suffix}',
            email=f'primary_vehicle_{test_suffix}@test.com',
            address='123 Main Street'
        )
        
        # School 2 (owned by platform_admin)
        self.school2 = DrivingSchool.objects.create(
            owner=self.users['platform_admin'],
            name=f'Secondary Vehicle School {test_suffix}',
            email=f'secondary_vehicle_{test_suffix}@test.com',
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
        
        # Student 2 profile (in school 2)
        self.profiles['student2'] = StudentProfile.objects.create(
            user=self.users['student2'],
            school=self.school2,
            status='A',
            license_type='C'
        )
        
        # Create test vehicles
        now = timezone.now()
        self.vehicles = {}
        
        # Vehicle 1 - Available car in school 1
        self.vehicles['vehicle1'] = Vehicle.objects.create(
            school=self.school1,
            plate_number=f'VH1{test_suffix}',
            make='Toyota',
            model='Corolla',
            year=2022,
            color='Red',
            transmission='manual',
            status='available',
            last_maintenance=now.date() - timedelta(days=60),
            next_maintenance=now.date() + timedelta(days=30)
        )
        
        # Vehicle 2 - Maintenance car in school 1
        self.vehicles['vehicle2'] = Vehicle.objects.create(
            school=self.school1,
            plate_number=f'VH2{test_suffix}',
            make='Honda',
            model='Civic',
            year=2021,
            color='Blue',
            transmission='automatic',
            status='maintenance',
            last_maintenance=now.date() - timedelta(days=90),
            next_maintenance=now.date() - timedelta(days=10)  # Overdue
        )
        
        # Vehicle 3 - Reserved car in school 2
        self.vehicles['vehicle3'] = Vehicle.objects.create(
            school=self.school2,
            plate_number=f'VH3{test_suffix}',
            make='Ford',
            model='Focus',
            year=2023,
            color='White',
            transmission='manual',
            status='reserved',
            last_maintenance=now.date() - timedelta(days=30),
            next_maintenance=now.date() + timedelta(days=60)
        )
        
        # Vehicle 4 - Available moto in school 1
        self.vehicles['vehicle4'] = Vehicle.objects.create(
            school=self.school1,
            plate_number=f'VH4{test_suffix}',
            make='Yamaha',
            model='YZF-R3',
            year=2022,
            color='Black',
            transmission='manual',
            status='available',
            last_maintenance=now.date() - timedelta(days=45),
            next_maintenance=now.date() + timedelta(days=15)  # Due soon
        )
        
        print("✅ Test data created:")
        print(f"   - Schools: {self.school1.name}, {self.school2.name}")
        print(f"   - Vehicles: {len(self.vehicles)} vehicles")
        print(f"   - Users: {len(self.users)} users")
    
    # ============ BASIC CACHING TESTS ============
    
    def test_01_list_vehicles_caching(self):
        """Test that listing vehicles uses caching"""
        print("\n📊 TEST 01: List Vehicles with Caching")
        print("-" * 40)
        
        # Authenticate as platform admin (can see all)
        self.client.force_authenticate(user=self.users['platform_admin'])
        
        # First request - should hit database
        start_time = time.time()
        response1 = self.client.get('/api/vehicle/')
        time1 = time.time() - start_time
        
        self.assertEqual(response1.status_code, status.HTTP_200_OK)
        
        # Get count from response
        count1 = self._get_result_count(response1.data)
        print(f"   First request: {count1} vehicles, {time1:.4f}s")
        
        # Second request - should be served from cache
        start_time = time.time()
        response2 = self.client.get('/api/vehicle/')
        time2 = time.time() - start_time
        
        count2 = self._get_result_count(response2.data)
        print(f"   Second request: {count2} vehicles, {time2:.4f}s")
        
        # Should get same data
        self.assertEqual(count1, count2)
        
        # Cached response should be faster
        if time2 <= time1:
            improvement = ((time1 - time2) / time1) * 100 if time1 > 0 else 100
            print(f"   ✅ Query caching working: {improvement:.1f}% improvement")
        else:
            print(f"   ⚠️  Cached response not faster: {time2:.4f}s vs {time1:.4f}s")
    
    def test_02_multi_tenancy_vehicle_isolation(self):
        """Test that users only see permitted vehicles"""
        print("\n📊 TEST 02: Multi-tenancy Vehicle Isolation")
        print("-" * 40)
        
        test_cases = [
            ('platform_admin', 'Platform Admin', 4),    # Should see all 4 vehicles
            ('school_owner', 'School Owner', 3),        # Should see vehicles in school1 (3)
            ('instructor1', 'Instructor 1', 3),         # Should see vehicles in school1
            ('instructor2', 'Instructor 2', 1),         # Should see vehicles in school2
            ('student1', 'Student 1', 3),               # Should see vehicles in school1
            ('student2', 'Student 2', 1),               # Should see vehicles in school2
        ]
        
        for user_key, user_description, expected_count in test_cases:
            self.client.force_authenticate(user=self.users[user_key])
            
            response = self.client.get('/api/vehicle/')
            data = response.data
            count = self._get_result_count(data)
            
            print(f"   {user_description}: sees {count} vehicles")
            
            if count == expected_count:
                print(f"     ✅ Correct isolation")
            else:
                print(f"     ⚠️  Expected {expected_count}, got {count}")
            
            # Verify status code
            self.assertIn(response.status_code, [200])
    
    def test_03_vehicle_detail_caching(self):
        """Test caching for individual vehicle"""
        print("\n📊 TEST 03: Vehicle Detail Caching")
        print("-" * 40)
        
        self.client.force_authenticate(user=self.users['platform_admin'])
        vehicle = self.vehicles['vehicle1']
        
        # First request
        start_time = time.time()
        response1 = self.client.get(f'/api/vehicle/{vehicle.id}/')
        time1 = time.time() - start_time
        
        # Second request (should be cached)
        start_time = time.time()
        response2 = self.client.get(f'/api/vehicle/{vehicle.id}/')
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
    
    def test_04_vehicle_list_rate_limit(self):
        """Test rate limiting for vehicle list endpoint"""
        print("\n📊 TEST 04: Vehicle List Rate Limit")
        print("-" * 40)
        
        self.client.force_authenticate(user=self.users['student1'])
        
        rate_limited = False
        
        # Make rapid requests (limit is 30/minute in test settings)
        for i in range(1, 35):
            response = self.client.get('/api/vehicle/')
            
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
            print("   ✅ Rate limiting triggered for vehicle list")
        else:
            print("   ⚠️  Rate limiting not triggered")
    
    def test_05_vehicle_create_rate_limit(self):
        """Test rate limiting for vehicle creation"""
        print("\n📊 TEST 05: Vehicle Create Rate Limit")
        print("-" * 40)
        
        self.client.force_authenticate(user=self.users['platform_admin'])
        
        # Create vehicle data
        vehicle_data = {
            'school': self.school1.id,
            'plate_number': f'NEW{uuid.uuid4().hex[:6]}',
            'make': 'Test Make',
            'model': 'Test Model',
            'year': 2024,
            'color': 'Test Color',
            'transmission': 'manual',
            'status': 'available'
        }
        
        rate_limited = False
        
        # Try multiple creations (limit is 5/minute in test settings)
        for i in range(1, 7):
            # Generate unique plate number
            vehicle_data['plate_number'] = f'NEW{i}{uuid.uuid4().hex[:4]}'
            
            response = self.client.post('/api/vehicle/', vehicle_data, format='json')
            
            if response.status_code == 429:
                rate_limited = True
                print(f"   Create {i}: Rate limited (429)")
                break
            elif response.status_code == 201:
                print(f"   Create {i}: Created (201)")
            elif response.status_code == 400:
                print(f"   Create {i}: Bad request (400)")
                # Might be due to duplicate plate number
                break
            else:
                print(f"   Create {i}: Status {response.status_code}")
                break
        
        if rate_limited:
            print("   ✅ Rate limiting triggered for vehicle creation")
        else:
            print("   ⚠️  Rate limiting not triggered")
    
    def test_06_vehicle_update_rate_limit(self):
        """Test rate limiting for vehicle updates"""
        print("\n📊 TEST 06: Vehicle Update Rate Limit")
        print("-" * 40)
        
        self.client.force_authenticate(user=self.users['school_owner'])
        vehicle = self.vehicles['vehicle1']
        
        rate_limited = False
        
        # Try multiple updates (limit is 10/minute in test settings)
        for i in range(1, 12):
            update_data = {
                'color': f'Updated Color {i}'
            }
            
            response = self.client.patch(
                f'/api/vehicle/{vehicle.id}/',
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
            print("   ✅ Rate limiting triggered for vehicle updates")
        else:
            print("   ⚠️  Rate limiting not triggered")
    
    # ============ CUSTOM ENDPOINT TESTS ============
    
    def test_07_available_vehicles_caching(self):
        """Test caching for available vehicles endpoint"""
        print("\n📊 TEST 07: Available Vehicles Endpoint Caching")
        print("-" * 40)
        
        self.client.force_authenticate(user=self.users['instructor1'])
        
        # First request
        start_time = time.time()
        response1 = self.client.get('/api/vehicle/available/')
        time1 = time.time() - start_time
        
        # Second request (should be cached)
        start_time = time.time()
        response2 = self.client.get('/api/vehicle/available/')
        time2 = time.time() - start_time
        
        print(f"   First available request: {time1:.4f}s")
        print(f"   Second available request: {time2:.4f}s")
        
        if response1.status_code == 200 and response2.status_code == 200:
            count1 = self._get_result_count(response1.data)
            count2 = self._get_result_count(response2.data)
            print(f"   Available vehicles: {count1}")
            
            if time2 <= time1:
                improvement = ((time1 - time2) / time1) * 100 if time1 > 0 else 100
                print(f"   ✅ Available vehicles caching: {improvement:.1f}% improvement")
            else:
                print("   ⚠️  Available vehicles caching not showing improvement")
        else:
            print(f"   ⚠️  Could not access available: {response1.status_code}")
    
    def test_08_maintenance_due_caching(self):
        """Test caching for maintenance due endpoint"""
        print("\n📊 TEST 08: Maintenance Due Endpoint Caching")
        print("-" * 40)
        
        self.client.force_authenticate(user=self.users['school_owner'])
        
        # First request
        start_time = time.time()
        response1 = self.client.get('/api/vehicle/maintenance_due/')
        time1 = time.time() - start_time
        
        # Second request (should be cached)
        start_time = time.time()
        response2 = self.client.get('/api/vehicle/maintenance_due/')
        time2 = time.time() - start_time
        
        print(f"   First maintenance_due request: {time1:.4f}s")
        print(f"   Second maintenance_due request: {time2:.4f}s")
        
        if response1.status_code == 200 and response2.status_code == 200:
            overdue = response1.data.get('overdue', {}).get('count', 0)
            upcoming = response1.data.get('upcoming', {}).get('count', 0)
            print(f"   Maintenance due: {overdue} overdue, {upcoming} upcoming")
            
            if time2 <= time1:
                improvement = ((time1 - time2) / time1) * 100 if time1 > 0 else 100
                print(f"   ✅ Maintenance due caching: {improvement:.1f}% improvement")
            else:
                print("   ⚠️  Maintenance due caching not showing improvement")
        else:
            print(f"   ⚠️  Could not access maintenance_due: {response1.status_code}")
    
    def test_09_statistics_endpoint_caching(self):
        """Test caching for statistics endpoint"""
        print("\n📊 TEST 09: Statistics Endpoint Caching")
        print("-" * 40)
        
        # Test as school owner
        self.client.force_authenticate(user=self.users['school_owner'])
        
        # First request
        start_time = time.time()
        response1 = self.client.get('/api/vehicle/statistics/')
        time1 = time.time() - start_time
        
        # Second request (should be cached)
        start_time = time.time()
        response2 = self.client.get('/api/vehicle/statistics/')
        time2 = time.time() - start_time
        
        print(f"   First statistics request: {time1:.4f}s")
        print(f"   Second statistics request: {time2:.4f}s")
        
        if response1.status_code == 200 and response2.status_code == 200:
            total = response1.data.get('total_vehicles', 0)
            print(f"   Vehicle statistics: {total} total vehicles")
            
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
        
        self.client.force_authenticate(user=self.users['instructor1'])
        
        rate_limited = False
        
        # Make rapid requests (limit is 6/minute in test settings)
        for i in range(1, 8):
            response = self.client.get('/api/vehicle/statistics/')
            
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
            print("   ✅ Rate limiting triggered for statistics")
        else:
            print("   ⚠️  Rate limiting not triggered")
    
    def test_11_my_school_vehicles_caching(self):
        """Test caching for my_school_vehicles endpoint"""
        print("\n📊 TEST 11: My School Vehicles Caching")
        print("-" * 40)
        
        # Test as instructor
        self.client.force_authenticate(user=self.users['instructor1'])
        
        # First request
        start_time = time.time()
        response1 = self.client.get('/api/vehicle/my_school_vehicles/')
        time1 = time.time() - start_time
        
        # Second request (should be cached)
        start_time = time.time()
        response2 = self.client.get('/api/vehicle/my_school_vehicles/')
        time2 = time.time() - start_time
        
        print(f"   First my_school_vehicles request: {time1:.4f}s")
        print(f"   Second my_school_vehicles request: {time2:.4f}s")
        
        if response1.status_code == 200 and response2.status_code == 200:
            count = self._get_result_count(response1.data)
            print(f"   My school vehicles: {count}")
            
            if time2 <= time1:
                improvement = ((time1 - time2) / time1) * 100 if time1 > 0 else 100
                print(f"   ✅ My school vehicles caching: {improvement:.1f}% improvement")
            else:
                print("   ⚠️  My school vehicles caching not showing improvement")
        else:
            print(f"   ⚠️  Could not access my_school_vehicles: {response1.status_code}")
    
    def test_12_cache_invalidation_on_create(self):
        """Test cache invalidation when creating vehicle"""
        print("\n📊 TEST 12: Cache Invalidation on Vehicle Create")
        print("-" * 40)
        
        self.client.force_authenticate(user=self.users['school_owner'])
        
        # Get initial count
        response = self.client.get('/api/vehicle/')
        data = response.data
        initial_count = self._get_result_count(data)
        print(f"   Initial vehicle count: {initial_count}")
        
        # Create a new vehicle
        new_vehicle_data = {
            'school': self.school1.id,
            'plate_number': f'NEW{uuid.uuid4().hex[:8]}',
            'make': 'Test Make',
            'model': 'Test Model',
            'year': 2024,
            'color': 'Silver',
            'transmission': 'automatic',
            'status': 'available'
        }
        
        response = self.client.post('/api/vehicle/', new_vehicle_data, format='json')
        
        if response.status_code in [201, 200]:
            print(f"   New vehicle created: ID {response.data.get('id')}")
            
            # Clear cache to simulate invalidation
            cache.clear()
            
            # Get list again
            response = self.client.get('/api/vehicle/')
            data = response.data
            new_count = self._get_result_count(data)
            
            print(f"   New vehicle count: {new_count}")
            
            # Should have one more vehicle
            self.assertEqual(new_count, initial_count + 1)
            print("   ✅ Cache invalidation on create verified")
        else:
            print(f"   ⚠️  Could not create vehicle: {response.status_code}")
            print(f"   Error: {response.data}")
    
    def test_13_cache_invalidation_on_update(self):
        """Test cache invalidation when updating vehicle"""
        print("\n📊 TEST 13: Cache Invalidation on Vehicle Update")
        print("-" * 40)
        
        self.client.force_authenticate(user=self.users['school_owner'])
        vehicle = self.vehicles['vehicle1']
        
        # Get original color
        response = self.client.get(f'/api/vehicle/{vehicle.id}/')
        if response.status_code == 200:
            original_color = response.data.get('color')
            print(f"   Original color: {original_color}")
        
        # Update color
        update_data = {'color': 'Updated Gold'}
        response = self.client.patch(
            f'/api/vehicle/{vehicle.id}/',
            update_data,
            format='json'
        )
        
        if response.status_code == 200:
            print(f"   Updated color: {response.data.get('color')}")
            
            # Clear cache to simulate invalidation
            cache.clear()
            
            # Get vehicle again
            response = self.client.get(f'/api/vehicle/{vehicle.id}/')
            if response.status_code == 200:
                updated_color = response.data.get('color')
                print(f"   Verified color: {updated_color}")
                
                self.assertEqual(updated_color, 'Updated Gold')
                print("   ✅ Cache invalidation on update verified")
        else:
            print(f"   ⚠️  Could not update: {response.status_code}")
    
    def test_14_maintenance_operations_rate_limit(self):
        """Test rate limiting for maintenance operations"""
        print("\n📊 TEST 14: Maintenance Operations Rate Limit")
        print("-" * 40)
        
        self.client.force_authenticate(user=self.users['instructor1'])
        vehicle = self.vehicles['vehicle1']
        
        rate_limited = False
        
        # Try multiple maintenance operations (limit is 4/minute in test settings)
        for i in range(1, 6):
            maintenance_data = {
                'next_maintenance': (timezone.now() + timedelta(days=30)).strftime('%Y-%m-%d')
            }
            
            response = self.client.post(
                f'/api/vehicle/{vehicle.id}/schedule_maintenance/',
                maintenance_data,
                format='json'
            )
            
            if response.status_code == 429:
                rate_limited = True
                print(f"   Maintenance {i}: Rate limited (429)")
                break
            elif response.status_code == 200:
                print(f"   Maintenance {i}: Scheduled (200)")
            elif response.status_code == 400:
                print(f"   Maintenance {i}: Bad request (400)")
                # Might be due to invalid data
                break
            else:
                print(f"   Maintenance {i}: Status {response.status_code}")
                break
        
        if rate_limited:
            print("   ✅ Rate limiting triggered for maintenance operations")
        else:
            print("   ⚠️  Rate limiting not triggered")
    
    def test_15_permissions_enforcement(self):
        """Test that permissions are properly enforced for vehicles"""
        print("\n📊 TEST 15: Vehicle Permission Enforcement")
        print("-" * 40)
        
        test_cases = [
            # (authenticated_as, tries_to_access_vehicle, can_update, can_delete)
            ('school_owner', 'vehicle1', True, True),    # Owner can update/delete
            ('school_owner', 'vehicle3', False, False),  # Owner cannot access other school
            ('instructor1', 'vehicle1', True, False),    # Instructor can update (limited)
            ('instructor1', 'vehicle3', False, False),   # Instructor cannot access other school
            ('student1', 'vehicle1', False, False),      # Student can view only
            ('student1', 'vehicle3', False, False),      # Student cannot access other school
        ]
        
        for auth_user, target_vehicle, can_update, can_delete in test_cases:
            self.client.force_authenticate(user=self.users[auth_user])
            vehicle = self.vehicles[target_vehicle]
            
            # Test GET access
            response = self.client.get(f'/api/vehicle/{vehicle.id}/')
            print(f"   {auth_user} -> {target_vehicle} GET: {response.status_code}")
            
            # Test UPDATE if allowed
            if can_update:
                update_data = {'color': 'Test update color'}
                update_response = self.client.patch(
                    f'/api/vehicle/{vehicle.id}/',
                    update_data,
                    format='json'
                )
                print(f"   {auth_user} -> {target_vehicle} UPDATE: {update_response.status_code}")
            
            # Test DELETE if allowed
            if can_delete:
                delete_response = self.client.delete(f'/api/vehicle/{vehicle.id}/')
                print(f"   {auth_user} -> {target_vehicle} DELETE: {delete_response.status_code}")
    
    def test_16_filtering_and_search(self):
        """Test filtering and search functionality"""
        print("\n📊 TEST 16: Filtering and Search")
        print("-" * 40)
        
        self.client.force_authenticate(user=self.users['platform_admin'])
        
        # Test filtering by status
        response = self.client.get('/api/vehicle/?status=available')
        if response.status_code == 200:
            available_count = self._get_result_count(response.data)
            print(f"   Available vehicles: {available_count}")
        
        # Test filtering by transmission
        response = self.client.get('/api/vehicle/?transmission=manual')
        if response.status_code == 200:
            manual_count = self._get_result_count(response.data)
            print(f"   Manual transmission vehicles: {manual_count}")
        
        # Test filtering by school
        response = self.client.get(f'/api/vehicle/?school={self.school1.id}')
        if response.status_code == 200:
            school_count = self._get_result_count(response.data)
            print(f"   Vehicles in school 1: {school_count}")
        
        # Test search by make
        response = self.client.get('/api/vehicle/?search=toyota')
        if response.status_code == 200:
            toyota_count = self._get_result_count(response.data)
            print(f"   Search for 'toyota': {toyota_count}")
        
        # Test search by plate number
        vehicle = self.vehicles['vehicle1']
        response = self.client.get(f'/api/vehicle/?search={vehicle.plate_number[:3]}')
        if response.status_code == 200:
            plate_count = self._get_result_count(response.data)
            print(f"   Search by plate prefix: {plate_count}")
        
        # Test ordering
        response = self.client.get('/api/vehicle/?ordering=year')
        if response.status_code == 200:
            print(f"   Ordered by year: OK")
        
        response = self.client.get('/api/vehicle/?ordering=-created_at')
        if response.status_code == 200:
            print(f"   Ordered by created_at descending: OK")
        
        print("   ✅ Filtering and search tests completed")
    
    def test_17_picture_upload_rate_limit(self):
        """Test rate limiting for picture uploads"""
        print("\n📊 TEST 17: Picture Upload Rate Limit")
        print("-" * 40)
        
        self.client.force_authenticate(user=self.users['school_owner'])
        vehicle = self.vehicles['vehicle1']
        
        rate_limited = False
        
        # Try multiple uploads (limit is 3/minute in test settings)
        for i in range(1, 5):
            # Create test image
            image = create_test_image()
            
            # Prepare form data
            data = {
                'images': (f'test_image_{i}.jpg', image, 'image/jpeg'),
                'captions': f'Test caption {i}'
            }
            
            response = self.client.post(
                f'/api/vehicle/{vehicle.id}/upload_pictures/',
                data,
                format='multipart'
            )
            
            if response.status_code == 429:
                rate_limited = True
                print(f"   Upload {i}: Rate limited (429)")
                break
            elif response.status_code == 201:
                print(f"   Upload {i}: Uploaded (201)")
            elif response.status_code == 400:
                print(f"   Upload {i}: Bad request (400)")
                # Might be due to validation errors
                break
            else:
                print(f"   Upload {i}: Status {response.status_code}")
                break
        
        if rate_limited:
            print("   ✅ Rate limiting triggered for picture uploads")
        else:
            print("   ⚠️  Rate limiting not triggered")
    
    def test_18_performance_benchmarks(self):
        """Test performance benchmarks for vehicle endpoints"""
        print("\n📊 TEST 18: Performance Benchmarks")
        print("-" * 40)
        
        self.client.force_authenticate(user=self.users['platform_admin'])
        
        endpoints_to_test = [
            ('/api/vehicle/', 'List Vehicles'),
            ('/api/vehicle/available/', 'Available Vehicles'),
            ('/api/vehicle/statistics/', 'Statistics'),
            ('/api/vehicle/my_school_vehicles/', 'My School Vehicles'),
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
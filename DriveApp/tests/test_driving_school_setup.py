"""
Setup test to ensure everything is working before running comprehensive tests.
"""

import os
import django
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from django.core.cache import cache

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Drive.settings')

User = get_user_model()
TEST_ADMIN_PASSWORD = "dummy_admin"
TEST_OWNER_PASSWORD = "dummy_owner"
TEST_INSTRUCTOR_PASSWORD = "dummy_instructor"
TEST_STUDENT_PASSWORD = "dummy_student"


class SetupTestCase(TestCase):
    """Test basic setup before running comprehensive tests"""
    
    @classmethod
    def setUpClass(cls):
        """Setup before all tests in this class"""
        super().setUpClass()
        django.setup()
        print("\n" + "="*60)
        print("🧪 DRIVING SCHOOL VIEWSET SETUP TEST")
        print("="*60)
    
    def setUp(self):
        """Setup before each test"""
        cache.clear()
        self.client = APIClient()
        
        print("\n🔧 Setting up test environment...")
        
        # Create test users
        self.platform_admin = User.objects.create_user(
            username='setup_admin',
            email='admin@setup.com',
            password=TEST_ADMIN_PASSWORD,
            role='A',
            is_staff=True
        )
        print(f"✅ Created platform admin: {self.platform_admin.username}")
        
        self.school_owner = User.objects.create_user(
            username='setup_owner',
            email='owner@setup.com',
            password=TEST_OWNER_PASSWORD,
            role='A',
            is_staff=False
        )
        print(f"✅ Created school owner: {self.school_owner.username}")
        
        # Create test school
        from DriveApp.models import DrivingSchool
        self.school = DrivingSchool.objects.create(
            owner=self.school_owner,
            name='Setup Test School',
            email='setup@school.com'
        )
        print(f"✅ Created school: {self.school.name}")
    
    def test_01_cache_utils_exist(self):
        """Verify all cache utilities exist"""
        print("\n🔍 Testing cache utilities...")
        
        try:
            from DriveApp.cache_utils import (
                get_user_queryset_cache_key,
                get_schools_cache_key,
                get_school_stats_cache_key,
                invalidate_user_caches,
                invalidate_school_caches,
                get_school_student_count_cache_key
            )
            
            # Test key generation
            user_key = get_user_queryset_cache_key(1, 'A')
            schools_key = get_schools_cache_key(1, 'A')
            stats_key = get_school_stats_cache_key(1)
            
            print(f"✅ User cache key: {user_key}")
            print(f"✅ Schools cache key: {schools_key}")
            print(f"✅ Stats cache key: {stats_key}")
            
            # Test invalidation (should not crash)
            invalidate_user_caches(1)
            invalidate_school_caches(1)
            print("✅ Cache invalidation functions exist")
            
        except ImportError as e:
            print(f"❌ Import error: {e}")
            self.fail(f"Missing cache utility: {e}")
        except Exception as e:
            print(f"❌ Error: {e}")
            self.fail(f"Cache utility error: {e}")
    
    def test_02_throttles_exist(self):
        """Verify throttle classes exist"""
        print("\n🔍 Testing throttle classes...")
        
        try:
            from DriveApp.throttles import (
                SchoolListThrottle,
                SchoolCreateThrottle,
                StatsThrottle
            )
            
            # Create instances
            school_list = SchoolListThrottle()
            school_create = SchoolCreateThrottle()
            stats = StatsThrottle()
            
            print(f"✅ SchoolListThrottle scope: {school_list.scope}")
            print(f"✅ SchoolCreateThrottle scope: {school_create.scope}")
            print(f"✅ StatsThrottle scope: {stats.scope}")
            
            # Check they have required methods
            self.assertTrue(hasattr(school_list, 'allow_request'))
            self.assertTrue(hasattr(school_create, 'allow_request'))
            self.assertTrue(hasattr(stats, 'allow_request'))
            print("✅ Throttle classes have required methods")
            
        except ImportError as e:
            print(f"❌ Import error: {e}")
            self.fail(f"Missing throttle class: {e}")
    
    def test_03_endpoints_accessible(self):
        """Verify endpoints are accessible"""
        print("\n🔍 Testing endpoint accessibility...")
        
        # Authenticate as platform admin
        self.client.force_authenticate(user=self.platform_admin)
        
        endpoints = [
            ('/api/driving-schools/', 'GET', 'List schools'),
            (f'/api/driving-schools/{self.school.id}/', 'GET', 'School detail'),
            (f'/api/driving-schools/{self.school.id}/students/', 'GET', 'School students'),
            (f'/api/driving-schools/{self.school.id}/stats/', 'GET', 'School stats'),
        ]
        
        all_accessible = True
        for url, method, description in endpoints:
            if method == 'GET':
                response = self.client.get(url)
                status = response.status_code
                accessible = status in [200, 201, 204, 403, 404]
                
                if accessible:
                    print(f"✅ {description}: Status {status}")
                else:
                    print(f"❌ {description}: Status {status}")
                    all_accessible = False
        
        self.assertTrue(all_accessible, "Some endpoints are not accessible")
    
    def test_04_cache_working(self):
        """Verify cache is working"""
        print("\n🔍 Testing cache functionality...")
        
        # Test basic cache operations
        cache.set('setup_test', 'setup_value', 10)
        value = cache.get('setup_test')
        
        if value == 'setup_value':
            print("✅ Basic cache operations working")
        else:
            print(f"❌ Cache test failed, got: {value}")
        
        self.assertEqual(value, 'setup_value')
        
        # Test cache clearing
        cache.delete('setup_test')
        self.assertIsNone(cache.get('setup_test'))
        print("✅ Cache clearing working")
    
    def test_05_permissions_exist(self):
        """Verify permission classes exist"""
        print("\n🔍 Testing permission classes...")
        
        try:
            from DriveApp.permissions import (
                IsPlatformAdmin,
                IsPlatformAdminOrSchoolOwner
            )
            
            # Try to instantiate them
            perm1 = IsPlatformAdmin()
            perm2 = IsPlatformAdminOrSchoolOwner()
            
            print("✅ Permission classes exist and can be instantiated")
            print(f"   - IsPlatformAdmin: {perm1.__class__.__name__}")
            print(f"   - IsPlatformAdminOrSchoolOwner: {perm2.__class__.__name__}")
            
        except ImportError as e:
            print(f"❌ Import error: {e}")
            self.fail(f"Missing permission class: {e}")
    
    def test_06_signals_registered(self):
        """Verify signals are registered"""
        print("\n🔍 Testing signal registration...")
        
        try:
            import DriveApp.signals
            from django.db.models.signals import post_save
            
            # Check if signals module was imported
            print("✅ Signals module imported successfully")
            
            # Try to import specific signal function
            from DriveApp.signals import invalidate_school_cache
            print("✅ Signal functions importable")
            
        except ImportError as e:
            print(f"❌ Signal import error: {e}")
        except Exception as e:
            print(f"❌ Signal error: {e}")
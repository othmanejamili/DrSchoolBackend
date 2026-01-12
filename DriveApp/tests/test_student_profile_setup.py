"""
Setup test for StudentProfileViewSet to ensure everything works before comprehensive tests.
"""
TEST_ADMIN_PASSWORD = "dummy_admin123"
TEST_OWNER_PASSWORD = "dummy_owner123"
TEST_INSTRUCTOR_PASSWORD = "dummy_instructor123"
TEST_STUDENT_PASSWORD = "dummy_student123"

import os
import django
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from django.core.cache import cache

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Drive.settings')

User = get_user_model()


class StudentProfileSetupTestCase(TestCase):
    """Test basic setup before running comprehensive tests"""
    
    @classmethod
    def setUpClass(cls):
        """Setup before all tests in this class"""
        super().setUpClass()
        django.setup()
        print("\n" + "="*60)
        print("🧪 STUDENT PROFILE VIEWSET SETUP TEST")
        print("="*60)
    
    def setUp(self):
        """Setup before each test"""
        cache.clear()
        self.client = APIClient()
        
        print("\n🔧 Setting up test environment...")
        
        # Create test users with different roles
        self.users = {}
        
        # Platform Admin
        self.users['platform_admin'] = User.objects.create_user(
            username='setup_platform_admin',
            email='platform@setup.com',
            password=TEST_ADMIN_PASSWORD,
            role='A',
            is_staff=True
        )
        print(f"✅ Created platform admin: {self.users['platform_admin'].username}")
        
        # School Owner
        self.users['school_owner'] = User.objects.create_user(
            username='setup_school_owner',
            email='owner@setup.com',
            password=TEST_OWNER_PASSWORD,
            role='A',
            is_staff=False
        )
        print(f"✅ Created school owner: {self.users['school_owner'].username}")
        
        # Instructor
        self.users['instructor'] = User.objects.create_user(
            username='setup_instructor',
            email='instructor@setup.com',
            password=TEST_INSTRUCTOR_PASSWORD,
            role='I'
        )
        print(f"✅ Created instructor: {self.users['instructor'].username}")
        
        # Student 1
        self.users['student1'] = User.objects.create_user(
            username='setup_student1',
            email='student1@setup.com',
            password=TEST_STUDENT_PASSWORD,
            role='S'
        )
        print(f"✅ Created student 1: {self.users['student1'].username}")
        
        # Student 2
        self.users['student2'] = User.objects.create_user(
            username='setup_student2',
            email='student2@setup.com',
            password=TEST_STUDENT_PASSWORD,
            role='S'
        )
        print(f"✅ Created student 2: {self.users['student2'].username}")
        
        # Create test school
        from DriveApp.models import DrivingSchool, StudentProfile
        self.school = DrivingSchool.objects.create(
            owner=self.users['school_owner'],
            name='Setup Test School',
            email='setup@school.com'
        )
        print(f"✅ Created school: {self.school.name}")
        
        # Create student profiles
        self.profiles = {}
        
        # Instructor profile
        self.profiles['instructor'] = StudentProfile.objects.create(
            user=self.users['instructor'],
            school=self.school,
            status='A',
            license_type='C',
            progress_theory=80.0,
            progress_driving=60.0
        )
        print(f"✅ Created instructor profile: {self.profiles['instructor'].id}")
        
        # Student 1 profile
        self.profiles['student1'] = StudentProfile.objects.create(
            user=self.users['student1'],
            school=self.school,
            status='A',
            license_type='C',
            progress_theory=50.0,
            progress_driving=30.0
        )
        print(f"✅ Created student 1 profile: {self.profiles['student1'].id}")
        
        # Student 2 profile
        self.profiles['student2'] = StudentProfile.objects.create(
            user=self.users['student2'],
            school=self.school,
            status='A',
            license_type='C',
            progress_theory=90.0,
            progress_driving=75.0
        )
        print(f"✅ Created student 2 profile: {self.profiles['student2'].id}")
    
    def test_01_cache_utils_exist(self):
        """Verify all student profile cache utilities exist"""
        print("\n🔍 Testing student profile cache utilities...")
        
        try:
            from DriveApp.cache_utils import (
                get_student_profile_cache_key,
                get_student_profile_detail_cache_key,
                get_student_progress_cache_key,
                get_student_prediction_cache_key,
                invalidate_student_profile_cache,
                invalidate_student_profiles_by_school
            )
            
            # Test key generation
            profile_key = get_student_profile_cache_key(1, 'A')
            detail_key = get_student_profile_detail_cache_key(1)
            progress_key = get_student_progress_cache_key(1)
            prediction_key = get_student_prediction_cache_key(1)
            
            print(f"✅ Profile cache key: {profile_key}")
            print(f"✅ Detail cache key: {detail_key}")
            print(f"✅ Progress cache key: {progress_key}")
            print(f"✅ Prediction cache key: {prediction_key}")
            
            # Test invalidation (should not crash)
            invalidate_student_profile_cache(1)
            invalidate_student_profiles_by_school(1)
            print("✅ Cache invalidation functions exist")
            
        except ImportError as e:
            print(f"❌ Import error: {e}")
            self.fail(f"Missing cache utility: {e}")
        except Exception as e:
            print(f"❌ Error: {e}")
            self.fail(f"Cache utility error: {e}")
    
    def test_02_throttles_exist(self):
        """Verify student profile throttle classes exist"""
        print("\n🔍 Testing student profile throttle classes...")
        
        try:
            from DriveApp.throttles import (
                StudentProgressThrottle,
                StudentProgressUpdateThrottle,
                StudentPerformancePredictionThrottle,
                RegisterStudentThrottle
            )
            
            # Create instances
            progress = StudentProgressThrottle()
            progress_update = StudentProgressUpdateThrottle()
            prediction = StudentPerformancePredictionThrottle()
            register = RegisterStudentThrottle()
            
            print(f"✅ StudentProgressThrottle scope: {progress.scope}")
            print(f"✅ StudentProgressUpdateThrottle scope: {progress_update.scope}")
            print(f"✅ StudentPerformancePredictionThrottle scope: {prediction.scope}")
            print(f"✅ RegisterStudentThrottle scope: {register.scope}")
            
            # Check they have required methods
            self.assertTrue(hasattr(progress, 'allow_request'))
            self.assertTrue(hasattr(progress_update, 'allow_request'))
            print("✅ Throttle classes have required methods")
            
        except ImportError as e:
            print(f"❌ Import error: {e}")
            self.fail(f"Missing throttle class: {e}")
    
    def test_03_cache_working(self):
        """Verify cache is working for student profiles"""
        print("\n🔍 Testing cache for student profiles...")
        
        from DriveApp.cache_utils import (
            get_student_profile_cache_key,
            get_student_profile_detail_cache_key
        )
        
        # Test cache operations
        profile = self.profiles['student1']
        
        # Generate cache keys
        list_key = get_student_profile_cache_key(profile.user.id, profile.user.role)
        detail_key = get_student_profile_detail_cache_key(profile.id)
        
        # Set test data in cache
        cache.set(list_key, [profile], 60)
        cache.set(detail_key, {'id': profile.id}, 60)
        
        # Get from cache
        cached_list = cache.get(list_key)
        cached_detail = cache.get(detail_key)
        
        if cached_list:
            print(f"✅ List cache working: {len(cached_list)} items")
        else:
            print("❌ List cache failed")
        
        if cached_detail:
            print(f"✅ Detail cache working: ID {cached_detail['id']}")
        else:
            print("❌ Detail cache failed")
        
        self.assertIsNotNone(cached_list)
        self.assertIsNotNone(cached_detail)
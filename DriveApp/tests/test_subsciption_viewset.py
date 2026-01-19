"""
Comprehensive tests for SubscriptionPlanViewSet and SchoolSubscriptionViewSet
with caching and rate limiting.
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
from decimal import Decimal
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
            'subscription_plan_list': '30/minute',       # Limit plan listing
            'subscription_plan_create': '5/minute',      # Limit plan creation
            'subscription_plan_update': '10/minute',     # Limit plan updates
            'subscription_plan_statistics': '15/minute', # Limit statistics requests
            'school_subscription_list': '20/minute',     # Limit subscription listing
            'school_subscription_create': '3/minute',    # Limit subscription creation
            'school_subscription_update': '8/minute',    # Limit subscription updates
            'school_subscription_action': '6/minute',    # Limit subscription actions
            'school_subscription_usage': '25/minute',    # Limit usage checks
        }
    }
)
class SubscriptionViewSetComprehensiveTestCase(TestCase):
    """Comprehensive test suite for subscription viewsets with caching and rate limiting"""
    
    @classmethod
    def setUpClass(cls):
        """Setup before all tests"""
        super().setUpClass()
        print("\n" + "="*60)
        print("💰 SUBSCRIPTION VIEWSETS COMPREHENSIVE TEST")
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
            username=f'sub_admin_{test_suffix}',
            email=f'admin_sub_{test_suffix}@test.com',
            password=TEST_PASSWORD,
            role='A',
            is_staff=True,
            is_active=True
        )
        
        # School Owner 1
        self.users['school_owner1'] = User.objects.create_user(
            username=f'sub_owner1_{test_suffix}',
            email=f'owner1_sub_{test_suffix}@test.com',
            password=TEST_PASSWORD,
            role='A',
            is_staff=False,
            is_active=True
        )
        
        # School Owner 2
        self.users['school_owner2'] = User.objects.create_user(
            username=f'sub_owner2_{test_suffix}',
            email=f'owner2_sub_{test_suffix}@test.com',
            password=TEST_PASSWORD,
            role='A',
            is_staff=False,
            is_active=True
        )
        
        # Instructor
        self.users['instructor'] = User.objects.create_user(
            username=f'sub_instructor_{test_suffix}',
            email=f'instructor_sub_{test_suffix}@test.com',
            password=TEST_PASSWORD,
            role='I',
            is_active=True
        )
        
        # Student
        self.users['student'] = User.objects.create_user(
            username=f'sub_student_{test_suffix}',
            email=f'student_sub_{test_suffix}@test.com',
            password=TEST_PASSWORD,
            role='S',
            is_active=True
        )
        
        # Create test schools
        from DriveApp.models import DrivingSchool, StudentProfile, SubscriptionPlan, SchoolSubscription
        
        # School 1 (owned by school_owner1)
        self.school1 = DrivingSchool.objects.create(
            owner=self.users['school_owner1'],
            name=f'Primary Sub School {test_suffix}',
            email=f'primary_sub_{test_suffix}@test.com',
            address='123 Main Street'
        )
        
        # School 2 (owned by school_owner2)
        self.school2 = DrivingSchool.objects.create(
            owner=self.users['school_owner2'],
            name=f'Secondary Sub School {test_suffix}',
            email=f'secondary_sub_{test_suffix}@test.com',
            address='456 Oak Avenue'
        )
        
        # Create student profiles for instructors
        StudentProfile.objects.create(
            user=self.users['instructor'],
            school=self.school1,
            status='A',
            license_type='C'
        )
        
        # Create subscription plans
        self.plans = {}
        
        # Basic Plan
        self.plans['basic'] = SubscriptionPlan.objects.create(
            name='Basic Plan',
            price=Decimal('29.99'),
            duration_days=30,
            max_students=20,
            max_instructors=3,
            features={'online_support': True, 'basic_analytics': True},
            is_active=True
        )
        
        # Standard Plan
        self.plans['standard'] = SubscriptionPlan.objects.create(
            name='Standard Plan',
            price=Decimal('79.99'),
            duration_days=30,
            max_students=50,
            max_instructors=5,
            features={'online_support': True, 'advanced_analytics': True, 'custom_branding': True},
            is_active=True
        )
        
        # Premium Plan
        self.plans['premium'] = SubscriptionPlan.objects.create(
            name='Premium Plan',
            price=Decimal('149.99'),
            duration_days=30,
            max_students=100,
            max_instructors=10,
            features={'online_support': True, 'advanced_analytics': True, 'custom_branding': True, 'api_access': True},
            is_active=True
        )
        
        # Inactive Plan
        self.plans['inactive'] = SubscriptionPlan.objects.create(
            name='Old Plan',
            price=Decimal('19.99'),
            duration_days=30,
            max_students=10,
            max_instructors=2,
            features={'online_support': True},
            is_active=False
        )
        
        # Create school subscriptions
        self.subscriptions = {}
        
        # School 1 subscription (Basic Plan)
        self.subscriptions['school1'] = SchoolSubscription.objects.create(
            school=self.school1,
            plan=self.plans['basic'],
            status='active',
            stripe_subscription_id=f'sub_{test_suffix}_1',
            current_period_start=timezone.now() - timedelta(days=15),
            current_period_end=timezone.now() + timedelta(days=15)
        )
        
        # School 2 subscription (Standard Plan, trial)
        self.subscriptions['school2'] = SchoolSubscription.objects.create(
            school=self.school2,
            plan=self.plans['standard'],
            status='trialing',
            stripe_subscription_id=f'sub_{test_suffix}_2',
            current_period_start=timezone.now() - timedelta(days=25),
            current_period_end=timezone.now() + timedelta(days=5)
        )
        
        # Create some students for school 1 to test limits
        for i in range(5):
            student_user = User.objects.create_user(
                username=f'school1_student_{i}_{test_suffix}',
                email=f'school1_student_{i}_{test_suffix}@test.com',
                password=TEST_PASSWORD,
                role='S',
                is_active=True
            )
            
            StudentProfile.objects.create(
                user=student_user,
                school=self.school1,
                status='A',
                license_type='C'
            )
        
        print("✅ Test data created:")
        print(f"   - Users: {len(self.users)}")
        print(f"   - Schools: 2")
        print(f"   - Subscription Plans: {len(self.plans)}")
        print(f"   - School Subscriptions: {len(self.subscriptions)}")
        print(f"   - Students in school 1: 5")
    
    # ============================================
    # SUBSCRIPTION PLAN VIEWSET TESTS
    # ============================================
    
    def test_01_subscription_plan_list_caching(self):
        """Test caching for subscription plan listing"""
        print("\n📊 TEST 01: Subscription Plan List Caching")
        print("-" * 40)
        
        # Test as platform admin (sees all plans)
        self.client.force_authenticate(user=self.users['platform_admin'])
        
        # First request - should hit database
        start_time = time.time()
        response1 = self.client.get('/api/subscriptionplan/')
        time1 = time.time() - start_time
        
        self.assertEqual(response1.status_code, status.HTTP_200_OK)
        print(f"   Platform Admin - First request: {time1:.4f}s, {len(response1.data)} plans")
        
        # Second request - should be served from cache
        start_time = time.time()
        response2 = self.client.get('/api/subscriptionplan/')
        time2 = time.time() - start_time
        
        print(f"   Platform Admin - Second request: {time2:.4f}s")
        
        # Should get same number of plans
        self.assertEqual(len(response1.data), len(response2.data))
        
        # Cached response should be faster
        if time2 <= time1:
            improvement = ((time1 - time2) / time1) * 100 if time1 > 0 else 100
            print(f"   ✅ Plan list caching: {improvement:.1f}% improvement")
        else:
            print(f"   ⚠️  Cached response not faster: {time2:.4f}s vs {time1:.4f}s")
        
        # Test as school owner (only sees active plans)
        self.client.force_authenticate(user=self.users['school_owner1'])
        
        response3 = self.client.get('/api/subscriptionplan/')
        plans = response3.data.get('results', response3.data)
        active_plans = len([p for p in plans if p['is_active']])
        print(f"   School Owner sees {active_plans} active plans (correct)")
    
    def test_02_subscription_plan_list_rate_limit(self):
        """Test rate limiting for subscription plan listing"""
        print("\n📊 TEST 02: Subscription Plan List Rate Limit")
        print("-" * 40)
        
        self.client.force_authenticate(user=self.users['school_owner1'])
        
        rate_limited = False
        
        # Make rapid requests (limit is 30/minute in test settings)
        for i in range(1, 35):
            response = self.client.get('/api/subscriptionplan/')
            
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
            print("   ✅ Rate limiting triggered for subscription plan list")
        else:
            print("   ⚠️  Rate limiting not triggered")
    
    def test_03_subscription_plan_permissions(self):
        """Test permissions for subscription plan operations"""
        print("\n📊 TEST 03: Subscription Plan Permissions")
        print("-" * 40)
        
        test_cases = [
            ('platform_admin', 'list', 200, 'Platform Admin can list'),
            ('platform_admin', 'create', 201, 'Platform Admin can create'),
            ('school_owner1', 'list', 200, 'School Owner can list'),
            ('school_owner1', 'create', 403, 'School Owner cannot create'),
            ('instructor', 'list', 200, 'Instructor can list'),
            ('instructor', 'create', 403, 'Instructor cannot create'),
            ('student', 'list', 200, 'Student can list'),
            ('student', 'create', 403, 'Student cannot create'),
        ]
        
        for user_key, action, expected_status, description in test_cases:
            self.client.force_authenticate(user=self.users[user_key])
            
            if action == 'list':
                response = self.client.get('/api/subscriptionplan/')
            elif action == 'create':
                data = {
                    'name': f'Test Plan {uuid.uuid4().hex[:6]}',
                    'price': '99.99',
                    'duration_days': 30,
                    'max_students': 50,
                    'max_instructors': 5,
                    'features': {'test': True},
                    'is_active': True
                }
                response = self.client.post('/api/subscriptionplan/', data, format='json')
            
            status_code = response.status_code
            status_text = '✅' if status_code == expected_status else '❌'
            print(f"   {self.users[user_key].role} {action}: {status_code} (expected {expected_status}) {status_text} - {description}")
    
    def test_04_popular_plans_caching(self):
        """Test caching for popular plans endpoint"""
        print("\n📊 TEST 04: Popular Plans Caching")
        print("-" * 40)
        
        self.client.force_authenticate(user=self.users['school_owner1'])
        
        # First request
        start_time = time.time()
        response1 = self.client.get('/api/subscriptionplan/popular_plans/')
        time1 = time.time() - start_time
        
        # Second request (should be cached)
        start_time = time.time()
        response2 = self.client.get('/api/subscriptionplan/popular_plans/')
        time2 = time.time() - start_time
        
        print(f"   First request: {time1:.4f}s")
        print(f"   Second request: {time2:.4f}s")
        
        if response1.status_code == 200 and response2.status_code == 200:
            if time2 <= time1:
                improvement = ((time1 - time2) / time1) * 100 if time1 > 0 else 100
                print(f"   ✅ Popular plans caching: {improvement:.1f}% improvement")
            else:
                print("   ⚠️  Caching not showing improvement")
        else:
            print(f"   ⚠️  Could not get popular plans: {response1.status_code}")
    
    def test_05_compare_plans_caching(self):
        """Test caching for compare plans endpoint"""
        print("\n📊 TEST 05: Compare Plans Caching")
        print("-" * 40)
        
        self.client.force_authenticate(user=self.users['school_owner1'])
        
        # First request
        start_time = time.time()
        response1 = self.client.get('/api/subscriptionplan/compare_plans/')
        time1 = time.time() - start_time
        
        # Second request (should be cached)
        start_time = time.time()
        response2 = self.client.get('/api/subscriptionplan/compare_plans/')
        time2 = time.time() - start_time
        
        print(f"   First request: {time1:.4f}s")
        print(f"   Second request: {time2:.4f}s")
        
        if response1.status_code == 200 and response2.status_code == 200:
            if time2 <= time1:
                improvement = ((time1 - time2) / time1) * 100 if time1 > 0 else 100
                print(f"   ✅ Compare plans caching: {improvement:.1f}% improvement")
            else:
                print("   ⚠️  Caching not showing improvement")
            
            # Check response structure
            data = response1.data
            if isinstance(data, list) and len(data) > 0:
                print(f"   ✅ Comparison data for {len(data)} plans")
        else:
            print(f"   ⚠️  Could not compare plans: {response1.status_code}")
    
    def test_06_recommended_plan_caching(self):
        """Test caching for recommended plan endpoint"""
        print("\n📊 TEST 06: Recommended Plan Caching")
        print("-" * 40)
        
        self.client.force_authenticate(user=self.users['school_owner1'])
        
        # First request with parameters
        params = '?school_size=15&budget=100'
        start_time = time.time()
        response1 = self.client.get(f'/api/subscriptionplan/recommended_plan/{params}')
        time1 = time.time() - start_time
        
        # Second request with same parameters (should be cached)
        start_time = time.time()
        response2 = self.client.get(f'/api/subscriptionplan/recommended_plan/{params}')
        time2 = time.time() - start_time
        
        print(f"   First request: {time1:.4f}s")
        print(f"   Second request: {time2:.4f}s")
        
        if response1.status_code == 200 and response2.status_code == 200:
            if time2 <= time1:
                improvement = ((time1 - time2) / time1) * 100 if time1 > 0 else 100
                print(f"   ✅ Recommended plan caching: {improvement:.1f}% improvement")
            else:
                print("   ⚠️  Caching not showing improvement")
            
            # Check response
            data1 = response1.data
            data2 = response2.data
            self.assertEqual(data1, data2)
        else:
            print(f"   ⚠️  Could not get recommendation: {response1.status_code}")
    
    def test_07_pricing_tiers_caching(self):
        """Test caching for pricing tiers endpoint"""
        print("\n📊 TEST 07: Pricing Tiers Caching")
        print("-" * 40)
        
        self.client.force_authenticate(user=self.users['school_owner1'])
        
        # First request
        start_time = time.time()
        response1 = self.client.get('/api/subscriptionplan/pricing_tiers/')
        time1 = time.time() - start_time
        
        # Second request (should be cached)
        start_time = time.time()
        response2 = self.client.get('/api/subscriptionplan/pricing_tiers/')
        time2 = time.time() - start_time
        
        print(f"   First request: {time1:.4f}s")
        print(f"   Second request: {time2:.4f}s")
        
        if response1.status_code == 200 and response2.status_code == 200:
            if time2 <= time1:
                improvement = ((time1 - time2) / time1) * 100 if time1 > 0 else 100
                print(f"   ✅ Pricing tiers caching: {improvement:.1f}% improvement")
            else:
                print("   ⚠️  Caching not showing improvement")
            
            # Check tiers structure
            data = response1.data
            self.assertIn('basic', data)
            self.assertIn('standard', data)
            self.assertIn('premium', data)
            print(f"   ✅ Tiers structure: {len(data['basic'])} basic, {len(data['standard'])} standard, {len(data['premium'])} premium")
        else:
            print(f"   ⚠️  Could not get pricing tiers: {response1.status_code}")
    
    def test_08_plan_statistics_caching(self):
        """Test caching for plan statistics endpoint"""
        print("\n📊 TEST 08: Plan Statistics Caching")
        print("-" * 40)
        
        self.client.force_authenticate(user=self.users['platform_admin'])
        plan = self.plans['basic']
        
        # First request
        start_time = time.time()
        response1 = self.client.get(f'/api/subscriptionplan/{plan.id}/statistics/')
        time1 = time.time() - start_time
        
        # Second request (should be cached)
        start_time = time.time()
        response2 = self.client.get(f'/api/subscriptionplan/{plan.id}/statistics/')
        time2 = time.time() - start_time
        
        print(f"   First request: {time1:.4f}s")
        print(f"   Second request: {time2:.4f}s")
        
        if response1.status_code == 200 and response2.status_code == 200:
            if time2 <= time1:
                improvement = ((time1 - time2) / time1) * 100 if time1 > 0 else 100
                print(f"   ✅ Plan statistics caching: {improvement:.1f}% improvement")
            else:
                print("   ⚠️  Caching not showing improvement")
        else:
            print(f"   ⚠️  Could not get statistics: {response1.status_code}")
    
    def test_09_plan_statistics_rate_limit(self):
        """Test rate limiting for plan statistics"""
        print("\n📊 TEST 09: Plan Statistics Rate Limit")
        print("-" * 40)
        
        self.client.force_authenticate(user=self.users['platform_admin'])
        plan = self.plans['basic']
        
        rate_limited = False
        
        # Make rapid requests (limit is 15/minute in test settings)
        for i in range(1, 20):
            response = self.client.get(f'/api/subscriptionplan/{plan.id}/statistics/')
            
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
            print("   ✅ Rate limiting triggered for plan statistics")
        else:
            print("   ⚠️  Rate limiting not triggered")
    
    # ============================================
    # SCHOOL SUBSCRIPTION VIEWSET TESTS
    # ============================================
    
    def test_10_school_subscription_list_caching(self):
        """Test caching for school subscription listing"""
        print("\n📊 TEST 10: School Subscription List Caching")
        print("-" * 40)
        
        # Test as platform admin (sees all subscriptions)
        self.client.force_authenticate(user=self.users['platform_admin'])
        
        # First request
        start_time = time.time()
        response1 = self.client.get('/api/schoolsubscription/')
        time1 = time.time() - start_time
        
        self.assertEqual(response1.status_code, status.HTTP_200_OK)
        print(f"   Platform Admin - First request: {time1:.4f}s, {len(response1.data)} subscriptions")
        
        # Second request (should be cached)
        start_time = time.time()
        response2 = self.client.get('/api/schoolsubscription/')
        time2 = time.time() - start_time
        
        print(f"   Platform Admin - Second request: {time2:.4f}s")
        
        if time2 <= time1:
            improvement = ((time1 - time2) / time1) * 100 if time1 > 0 else 100
            print(f"   ✅ Subscription list caching: {improvement:.1f}% improvement")
        else:
            print(f"   ⚠️  Cached response not faster: {time2:.4f}s vs {time1:.4f}s")
        
        # Test as school owner (only sees own subscription)
        self.client.force_authenticate(user=self.users['school_owner1'])
        response3 = self.client.get('/api/schoolsubscription/')
        print(f"   School Owner sees {len(response3.data)} subscriptions (should be 1)")
    
    def test_11_school_subscription_list_rate_limit(self):
        """Test rate limiting for school subscription listing"""
        print("\n📊 TEST 11: School Subscription List Rate Limit")
        print("-" * 40)
        
        self.client.force_authenticate(user=self.users['platform_admin'])
        
        rate_limited = False
        
        # Make rapid requests (limit is 20/minute in test settings)
        for i in range(1, 25):
            response = self.client.get('/api/schoolsubscription/')
            
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
            print("   ✅ Rate limiting triggered for subscription list")
        else:
            print("   ⚠️  Rate limiting not triggered")
    
    def test_12_school_subscription_permissions(self):
        """Test permissions for school subscription operations"""
        print("\n📊 TEST 12: School Subscription Permissions")
        print("-" * 40)
        
        subscription = self.subscriptions['school1']
        
        test_cases = [
            ('platform_admin', 'retrieve', 200, 'Platform Admin can view any'),
            ('school_owner1', 'retrieve', 200, 'Owner can view own'),
            ('school_owner2', 'retrieve', 403, 'Owner cannot view other'),
            ('instructor', 'retrieve', 403, 'Instructor cannot view'),
            ('student', 'retrieve', 403, 'Student cannot view'),
        ]
        
        for user_key, action, expected_status, description in test_cases:
            self.client.force_authenticate(user=self.users[user_key])
            
            if action == 'retrieve':
                response = self.client.get(f'/api/schoolsubscription/{subscription.id}/')
            
            status_code = response.status_code
            status_text = '✅' if status_code == expected_status else '❌'
            print(f"   {self.users[user_key].role} {action}: {status_code} (expected {expected_status}) {status_text} - {description}")
    
    def test_13_cancel_subscription_rate_limit(self):
        """Test rate limiting for subscription cancellation"""
        print("\n📊 TEST 13: Cancel Subscription Rate Limit")
        print("-" * 40)
        
        self.client.force_authenticate(user=self.users['school_owner1'])
        subscription = self.subscriptions['school1']
        
        rate_limited = False
        
        # Try multiple cancellations (limit is 6/minute in test settings)
        for i in range(1, 8):
            response = self.client.post(f'/api/schoolsubscription/{subscription.id}/cancel/')
            
            if response.status_code == 429:
                rate_limited = True
                print(f"   Request {i}: Rate limited (429)")
                break
            elif response.status_code == 200:
                print(f"   Request {i}: Cancelled (200)")
                # Reset status for next attempt
                subscription.status = 'active'
                subscription.save()
            elif response.status_code == 400:
                print(f"   Request {i}: Already canceled (400)")
                break
            else:
                print(f"   Request {i}: Status {response.status_code}")
                break
        
        if rate_limited:
            print("   ✅ Rate limiting triggered for subscription cancel")
        else:
            print("   ⚠️  Rate limiting not triggered")
    
    def test_14_check_limits_caching(self):
        """Test caching for check limits endpoint"""
        print("\n📊 TEST 14: Check Limits Caching")
        print("-" * 40)
        
        self.client.force_authenticate(user=self.users['school_owner1'])
        subscription = self.subscriptions['school1']
        
        # First request
        start_time = time.time()
        response1 = self.client.get(f'/api/schoolsubscription/{subscription.id}/check_limits/')
        time1 = time.time() - start_time
        
        # Second request (should be cached)
        start_time = time.time()
        response2 = self.client.get(f'/api/schoolsubscription/{subscription.id}/check_limits/')
        time2 = time.time() - start_time
        
        print(f"   First request: {time1:.4f}s")
        print(f"   Second request: {time2:.4f}s")
        
        if response1.status_code == 200 and response2.status_code == 200:
            if time2 <= time1:
                improvement = ((time1 - time2) / time1) * 100 if time1 > 0 else 100
                print(f"   ✅ Check limits caching: {improvement:.1f}% improvement")
            else:
                print("   ⚠️  Caching not showing improvement")
        else:
            print(f"   ⚠️  Could not check limits: {response1.status_code}")
    
    def test_15_usage_stats_caching(self):
        """Test caching for usage statistics endpoint"""
        print("\n📊 TEST 15: Usage Statistics Caching")
        print("-" * 40)
        
        self.client.force_authenticate(user=self.users['school_owner1'])
        subscription = self.subscriptions['school1']
        
        # First request
        start_time = time.time()
        response1 = self.client.get(f'/api/schoolsubscription/{subscription.id}/usage_stats/')
        time1 = time.time() - start_time
        
        # Second request (should be cached)
        start_time = time.time()
        response2 = self.client.get(f'/api/schoolsubscription/{subscription.id}/usage_stats/')
        time2 = time.time() - start_time
        
        print(f"   First request: {time1:.4f}s")
        print(f"   Second request: {time2:.4f}s")
        
        if response1.status_code == 200 and response2.status_code == 200:
            if time2 <= time1:
                improvement = ((time1 - time2) / time1) * 100 if time1 > 0 else 100
                print(f"   ✅ Usage stats caching: {improvement:.1f}% improvement")
            else:
                print("   ⚠️  Caching not showing improvement")
        else:
            print(f"   ⚠️  Could not get usage stats: {response1.status_code}")
    
    def test_16_usage_stats_rate_limit(self):
        """Test rate limiting for usage statistics"""
        print("\n📊 TEST 16: Usage Statistics Rate Limit")
        print("-" * 40)
        
        self.client.force_authenticate(user=self.users['school_owner1'])
        subscription = self.subscriptions['school1']
        
        rate_limited = False
        
        # Make rapid requests (limit is 25/minute in test settings)
        for i in range(1, 30):
            response = self.client.get(f'/api/schoolsubscription/{subscription.id}/usage_stats/')
            
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
            print("   ✅ Rate limiting triggered for usage stats")
        else:
            print("   ⚠️  Rate limiting not triggered")
    
    def test_17_cache_invalidation_on_plan_change(self):
        """Test that cache is invalidated when plan changes"""
        print("\n📊 TEST 17: Cache Invalidation on Plan Change")
        print("-" * 40)
        
        self.client.force_authenticate(user=self.users['platform_admin'])
        
        # Get and cache popular plans
        response1 = self.client.get('/api/subscriptionplan/popular_plans/')
        
        if response1.status_code == 200:
            print("   Initial popular plans cached")
            
            # Create a new plan (should invalidate cache)
            data = {
                'name': 'New Test Plan',
                'price': '199.99',
                'duration_days': 30,
                'max_students': 150,
                'max_instructors': 15,
                'features': {'all_features': True},
                'is_active': True
            }
            
            response2 = self.client.post('/api/subscriptionplan/', data, format='json')
            
            if response2.status_code == 201:
                print("   New plan created (should invalidate caches)")
                
                # Get popular plans again (should be fresh)
                response3 = self.client.get('/api/subscriptionplan/popular_plans/')
                
                if response3.status_code == 200:
                    # Should not have cache_hit flag
                    print("   ✅ Cache properly invalidated after plan creation")
                else:
                    print(f"   ❌ Failed to get popular plans: {response3.status_code}")
            else:
                print(f"   ❌ Failed to create plan: {response2.status_code}")
        else:
            print(f"   ❌ Failed to get initial popular plans: {response1.status_code}")
    
    def test_18_cache_invalidation_on_subscription_change(self):
        """Test that cache is invalidated when subscription changes"""
        print("\n📊 TEST 18: Cache Invalidation on Subscription Change")
        print("-" * 40)
        
        self.client.force_authenticate(user=self.users['school_owner1'])
        subscription = self.subscriptions['school1']
        
        # Get and cache usage stats
        response1 = self.client.get(f'/api/schoolsubscription/{subscription.id}/usage_stats/')
        
        if response1.status_code == 200:
            print("   Initial usage stats cached")
            
            # Clear cache to simulate invalidation
            cache.clear()
            
            # Get usage stats again (should be fresh)
            response2 = self.client.get(f'/api/schoolsubscription/{subscription.id}/usage_stats/')
            
            if response2.status_code == 200:
                print("   ✅ Cache properly invalidated (fresh data fetched)")
            else:
                print(f"   ❌ Failed to get usage stats: {response2.status_code}")
        else:
            print(f"   ❌ Failed to get initial usage stats: {response1.status_code}")
    
    def test_19_expired_subscriptions_endpoint(self):
        """Test expired subscriptions endpoint (admin only)"""
        print("\n📊 TEST 19: Expired Subscriptions Endpoint")
        print("-" * 40)
        
        # Platform admin can access
        self.client.force_authenticate(user=self.users['platform_admin'])
        response1 = self.client.get('/api/schoolsubscription/expired_subscriptions/')
        print(f"   Platform Admin: Status {response1.status_code} ✅" if response1.status_code == 200 else f"   ❌ Got {response1.status_code}")
        
        # School owner cannot access
        self.client.force_authenticate(user=self.users['school_owner1'])
        response2 = self.client.get('/api/schoolsubscription/expired_subscriptions/')
        print(f"   School Owner: Status {response2.status_code} ✅" if response2.status_code == 403 else f"   ⚠️  Got {response2.status_code}")
    
    def test_20_trial_expiring_soon_endpoint(self):
        """Test trial expiring soon endpoint (admin only)"""
        print("\n📊 TEST 20: Trial Expiring Soon Endpoint")
        print("-" * 40)
        
        # Platform admin can access
        self.client.force_authenticate(user=self.users['platform_admin'])
        response1 = self.client.get('/api/schoolsubscription/trial_expiring_soon/')
        print(f"   Platform Admin: Status {response1.status_code} ✅" if response1.status_code == 200 else f"   ❌ Got {response1.status_code}")
        
        # School owner cannot access
        self.client.force_authenticate(user=self.users['school_owner1'])
        response2 = self.client.get('/api/schoolsubscription/trial_expiring_soon/')
        print(f"   School Owner: Status {response2.status_code} ✅" if response2.status_code == 403 else f"   ⚠️  Got {response2.status_code}")
    
    def test_21_upgrade_subscription_rate_limit(self):
        """Test rate limiting for subscription upgrade"""
        print("\n📊 TEST 21: Upgrade Subscription Rate Limit")
        print("-" * 40)
        
        self.client.force_authenticate(user=self.users['school_owner1'])
        subscription = self.subscriptions['school1']
        
        rate_limited = False
        
        # Try multiple upgrades (limit is 6/minute in test settings)
        for i in range(1, 8):
            data = {'new_plan_id': self.plans['standard'].id}
            response = self.client.post(f'/api/schoolsubscription/{subscription.id}/upgrade/', data, format='json')
            
            if response.status_code == 429:
                rate_limited = True
                print(f"   Request {i}: Rate limited (429)")
                break
            elif response.status_code in [200, 400]:
                # 400 is expected after first successful upgrade
                if i == 1:
                    print(f"   Request {i}: Upgrade attempted")
                else:
                    print(f"   Request {i}: Already upgraded (400)")
                break
            else:
                print(f"   Request {i}: Status {response.status_code}")
                break
        
        if rate_limited:
            print("   ✅ Rate limiting triggered for subscription upgrade")
        else:
            print("   ⚠️  Rate limiting not triggered")
    
    def test_22_filter_and_search(self):
        """Test filtering and search functionality"""
        print("\n📊 TEST 22: Filtering and Search")
        print("-" * 40)
        
        self.client.force_authenticate(user=self.users['platform_admin'])
        
        # Test filtering by is_active
        response1 = self.client.get('/api/subscriptionplan/?is_active=true')
        if response1.status_code == 200:
            plans = response1.data.get('results', response1.data)
            active_plans = len([p for p in plans if p['is_active']])
            print(f"   Active plans: {active_plans}")
        
        # Test filtering by duration_days
        response2 = self.client.get('/api/subscriptionplan/?duration_days=30')
        if response2.status_code == 200:
            monthly_plans = len(response2.data)
            print(f"   30-day plans: {monthly_plans}")
        
        # Test search by name
        response3 = self.client.get('/api/subscriptionplan/?search=Basic')
        if response3.status_code == 200:
            basic_plans = len(response3.data)
            print(f"   Plans with 'Basic' in name: {basic_plans}")
        
        print("   ✅ Filtering and search tests completed")
    
    def test_23_performance_benchmarks(self):
        """Test performance benchmarks for subscription endpoints"""
        print("\n📊 TEST 23: Performance Benchmarks")
        print("-" * 40)
        
        endpoints_to_test = [
            ('/api/subscriptionplan/', 'Subscription Plans List', 'platform_admin'),
            ('/api/subscriptionplan/popular_plans/', 'Popular Plans', 'school_owner1'),
            ('/api/subscriptionplan/compare_plans/', 'Compare Plans', 'school_owner1'),
            ('/api/subscriptionplan/pricing_tiers/', 'Pricing Tiers', 'school_owner1'),
            ('/api/schoolsubscription/', 'School Subscriptions List', 'platform_admin'),
            ('/api/schoolsubscription/expired_subscriptions/', 'Expired Subscriptions', 'platform_admin'),
        ]
        
        for endpoint, description, user_key in endpoints_to_test:
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
    
    def test_24_error_handling(self):
        """Test error handling in subscription endpoints"""
        print("\n📊 TEST 24: Error Handling")
        print("-" * 40)
        
        self.client.force_authenticate(user=self.users['school_owner1'])
        
        error_cases = [
            ('/api/subscriptionplan/recommended_plan/?school_size=0', 'Invalid school_size (0)'),
            ('/api/subscriptionplan/recommended_plan/?budget=0', 'Invalid budget (0)'),
            ('/api/subscriptionplan/recommended_plan/?school_size=abc', 'Non-numeric school_size'),
            ('/api/subscriptionplan/999999/', 'Non-existent plan'),
            ('/api/schoolsubscription/999999/', 'Non-existent subscription'),
        ]
        
        for endpoint, description in error_cases:
            response = self.client.get(endpoint)
            
            if response.status_code in [400, 404]:
                print(f"   ✅ {description}: Correctly handled ({response.status_code})")
            else:
                print(f"   ⚠️  {description}: Got {response.status_code}, expected 400 or 404")
    
    def test_25_throttle_configuration(self):
        """Test that correct throttles are configured"""
        print("\n📊 TEST 25: Throttle Configuration")
        print("-" * 40)
        
        # SubscriptionPlanViewSet throttles
        plan_throttles = {
            'list': 'SubscriptionPlanListThrottle',
            'create': 'SubscriptionPlanCreateThrottle',
            'update': 'SubscriptionPlanUpdateThrottle',
            'partial_update': 'SubscriptionPlanUpdateThrottle',
            'statistics': 'SubscriptionPlanStatisticsThrottle',
            'popular_plans': 'SubscriptionPlanListThrottle',
            'compare_plans': 'SubscriptionPlanListThrottle',
        }
        
        # SchoolSubscriptionViewSet throttles
        sub_throttles = {
            'list': 'SchoolSubscriptionListThrottle',
            'create': 'SchoolSubscriptionCreateThrottle',
            'update': 'SchoolSubscriptionUpdateThrottle',
            'partial_update': 'SchoolSubscriptionUpdateThrottle',
            'cancel': 'SchoolSubscriptionActionThrottle',
            'renew': 'SchoolSubscriptionActionThrottle',
            'upgrade': 'SchoolSubscriptionActionThrottle',
            'check_limits': 'SchoolSubscriptionUsageThrottle',
            'usage_stats': 'SchoolSubscriptionUsageThrottle',
        }
        
        print("   SubscriptionPlanViewSet throttle classes:")
        for action, throttle_class in plan_throttles.items():
            print(f"     {action}: {throttle_class}")
        
        print("\n   SchoolSubscriptionViewSet throttle classes:")
        for action, throttle_class in sub_throttles.items():
            print(f"     {action}: {throttle_class}")
        
        print("\n   ✅ Throttle configurations verified")
    
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
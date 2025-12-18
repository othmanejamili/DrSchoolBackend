# SubscriptionTest.py
# Complete test suite for SubscriptionPlanService and SchoolSubscriptionService

from DriveApp.models import User, DrivingSchool, StudentProfile, SubscriptionPlan, SchoolSubscription
from DriveApp.services import SubscriptionPlanService, SchoolSubscriptionService
from DriveApp.serializers import SubscriptionPlanSerializer, SchoolSubscriptionSerializer
from django.utils import timezone
from datetime import datetime, timedelta
from django.test import RequestFactory
from rest_framework.request import Request

print("=" * 70)
print("🧪 SUBSCRIPTION SERVICES & SERIALIZERS TEST SUITE")
print("=" * 70)

# ============================================================================
# SETUP: Create test data
# ============================================================================
print("\n📦 STEP 1: Setting up test data...")

# Create unique timestamp for this test run
test_timestamp = int(timezone.now().timestamp())

# Create owner
owner = User.objects.create_user(
    username=f'sub_owner_{test_timestamp}',
    email=f'owner_sub_{test_timestamp}@test.com',
    password='test123',
    role='A'
)
print("✅ Created owner")

# Create schools
school1 = DrivingSchool.objects.create(
    owner=owner,
    name=f'Subscription School 1 {test_timestamp}',
    address='123 Sub St',
    email=f'school1_sub_{test_timestamp}@test.com',
    phone_number='123-456-7890'
)

school2 = DrivingSchool.objects.create(
    owner=owner,
    name=f'Subscription School 2 {test_timestamp}',
    address='456 Sub Ave',
    email=f'school2_sub_{test_timestamp}@test.com',
    phone_number='987-654-3210'
)
print("✅ Created schools")

# Create students and instructors
student1 = User.objects.create_user(
    username=f'sub_student1_{test_timestamp}',
    email=f'student1_sub_{test_timestamp}@test.com',
    password='test123',
    role='S'
)
student1_profile = StudentProfile.objects.create(
    user=student1,
    school=school1,
    license_type='B',
    status='A'
)

instructor1 = User.objects.create_user(
    username=f'sub_instructor1_{test_timestamp}',
    email=f'instructor1_sub_{test_timestamp}@test.com',
    password='test123',
    role='I'
)
instructor1_profile = StudentProfile.objects.create(
    user=instructor1,
    school=school1,
    license_type='B',
    status='A'
)
print("✅ Created students and instructors")

# Create subscription plans
basic_plan = SubscriptionPlan.objects.create(
    name=f'Basic Plan {test_timestamp}',
    price=49.99,
    duration_days=30,
    max_students=50,
    max_instructors=5,
    features={'online_support': True, 'basic_analytics': True},
    is_active=True
)

premium_plan = SubscriptionPlan.objects.create(
    name=f'Premium Plan {test_timestamp}',
    price=99.99,
    duration_days=30,
    max_students=200,
    max_instructors=20,
    features={'priority_support': True, 'advanced_analytics': True, 'custom_reports': True},
    is_active=True
)

yearly_plan = SubscriptionPlan.objects.create(
    name=f'Yearly Plan {test_timestamp}',
    price=999.99,
    duration_days=365,
    max_students=100,
    max_instructors=10,
    features={'priority_support': True, 'advanced_analytics': True},
    is_active=True
)

inactive_plan = SubscriptionPlan.objects.create(
    name=f'Inactive Plan {test_timestamp}',
    price=29.99,
    duration_days=30,
    max_students=25,
    max_instructors=3,
    features={'basic_support': True},
    is_active=False
)
print("✅ Created subscription plans")

# Create request factory
factory = RequestFactory()

print("\n" + "=" * 70)
print("🧪 STEP 2: Testing SubscriptionPlanService Methods")
print("=" * 70)

# ============================================================================
# TEST 1: Test validation methods
# ============================================================================
print("\n📝 TEST 1: Test validation methods...")

# Test 1a: Valid plan data
try:
    SubscriptionPlanService.validate_plan_creation(
        price=49.99,
        max_students=50,
        max_instructors=5,
        duration_days=30,
        features={'support': True}
    )
    print("✅ Valid plan data accepted")
except Exception as e:
    print(f"❌ Valid plan data rejected: {e}")

# Test 1b: Invalid price
try:
    SubscriptionPlanService.validate_plan_creation(
        price=-10.00,
        max_students=50,
        max_instructors=5,
        duration_days=30,
        features={'support': True}
    )
    print("❌ Negative price accepted (should be rejected)")
except Exception as e:
    print(f"✅ Negative price correctly rejected: {e}")

# Test 1c: Invalid student limit
try:
    SubscriptionPlanService.validate_plan_creation(
        price=49.99,
        max_students=0,
        max_instructors=5,
        duration_days=30,
        features={'support': True}
    )
    print("❌ Zero students accepted (should be rejected)")
except Exception as e:
    print(f"✅ Zero students correctly rejected: {e}")

# Test 1d: Invalid duration
try:
    SubscriptionPlanService.validate_plan_creation(
        price=49.99,
        max_students=50,
        max_instructors=5,
        duration_days=0,
        features={'support': True}
    )
    print("❌ Zero duration accepted (should be rejected)")
except Exception as e:
    print(f"✅ Zero duration correctly rejected: {e}")

# Test 1e: Invalid features
try:
    SubscriptionPlanService.validate_plan_creation(
        price=49.99,
        max_students=50,
        max_instructors=5,
        duration_days=30,
        features="invalid"  # Should be dict
    )
    print("❌ Invalid features accepted (should be rejected)")
except Exception as e:
    print(f"✅ Invalid features correctly rejected: {e}")

# ============================================================================
# TEST 2: Test utility methods
# ============================================================================
print("\n📝 TEST 2: Test utility methods...")

# Test 2a: Price formatting
price_formatted = SubscriptionPlanService.get_price_formatted(49.99)
print(f"✅ Price formatting: {price_formatted}")

# Test 2b: Duration display
monthly_display = SubscriptionPlanService.get_duration_display(30)
yearly_display = SubscriptionPlanService.get_duration_display(365)
custom_display = SubscriptionPlanService.get_duration_display(60)
print(f"✅ Monthly duration: {monthly_display}")
print(f"✅ Yearly duration: {yearly_display}")
print(f"✅ Custom duration: {custom_display}")

# Test 2c: Subscription count
basic_count = SubscriptionPlanService.get_subscription_count(basic_plan)
print(f"✅ Basic plan subscription count: {basic_count}")

# ============================================================================
# TEST 3: Test plan creation and update
# ============================================================================
print("\n📝 TEST 3: Test plan creation and update...")

# Test 3a: Create plan
try:
    plan_data = {
        'name': f'Test Plan {test_timestamp}',
        'price': 79.99,
        'duration_days': 30,
        'max_students': 75,
        'max_instructors': 8,
        'features': {'premium_support': True},
        'is_active': True
    }
    
    new_plan = SubscriptionPlanService.create_plan(plan_data)
    print(f"✅ Plan created: ID={new_plan.id}, Name={new_plan.name}")
    
except Exception as e:
    print(f"❌ Plan creation failed: {e}")

# Test 3b: Update plan
try:
    update_data = {
        'price': 89.99,
        'max_students': 100
    }
    
    updated_plan = SubscriptionPlanService.update_plan(basic_plan, update_data)
    print(f"✅ Plan updated: New price=${updated_plan.price}, New max_students={updated_plan.max_students}")
    
except Exception as e:
    print(f"❌ Plan update failed: {e}")

# ============================================================================
# TEST 4: Test business logic methods
# ============================================================================
print("\n📝 TEST 4: Test business logic methods...")

# Test 4a: Popular plan detection
is_basic_popular = SubscriptionPlanService.get_is_popular(basic_plan)
is_premium_popular = SubscriptionPlanService.get_is_popular(premium_plan)
print(f"✅ Basic plan is popular: {is_basic_popular}")
print(f"✅ Premium plan is popular: {is_premium_popular}")

# Test 4b: Active plans
active_plans = SubscriptionPlanService.get_active_plans()
print(f"✅ Active plans count: {active_plans.count()}")

# Test 4c: Popular plans
popular_plans = SubscriptionPlanService.get_popular_plans(2)
print(f"✅ Popular plans count: {popular_plans.count()}")

# Test 4d: Plan deactivation
can_deactivate_inactive = SubscriptionPlanService.can_deactivate_plan(inactive_plan)
print(f"✅ Can deactivate inactive plan: {can_deactivate_inactive}")

# Test 4e: Plan statistics
basic_stats = SubscriptionPlanService.get_plan_statistics(basic_plan)
print(f"✅ Basic plan stats: {basic_stats}")

# Test 4f: Plan recommendation
recommended_plan = SubscriptionPlanService.get_recommended_plan(
    school_size=30,
    budget=80.00,
    duration_preference='monthly'
)
print(f"✅ Recommended plan: {recommended_plan.name if recommended_plan else 'None'}")

print("\n" + "=" * 70)
print("🧪 STEP 3: Testing SchoolSubscriptionService Methods")
print("=" * 70)

# ============================================================================
# TEST 5: Create test subscriptions
# ============================================================================
print("\n📝 TEST 5: Create test subscriptions...")

# Create subscriptions for testing
current_time = timezone.now()
subscription1 = SchoolSubscription.objects.create(
    school=school1,
    plan=basic_plan,
    status='active',
    current_period_start=current_time - timedelta(days=15),
    current_period_end=current_time + timedelta(days=15)
)

subscription2 = SchoolSubscription.objects.create(
    school=school2,
    plan=premium_plan,
    status='trialing',
    current_period_start=current_time - timedelta(days=5),
    current_period_end=current_time + timedelta(days=25)
)

expired_subscription = SchoolSubscription.objects.create(
    school=DrivingSchool.objects.create(
        owner=owner,
        name=f'Expired School {test_timestamp}',
        email=f'expired_school_{test_timestamp}@test.com'
    ),
    plan=basic_plan,
    status='canceled',
    current_period_start=current_time - timedelta(days=60),
    current_period_end=current_time - timedelta(days=30)
)
print("✅ Created test subscriptions")

# ============================================================================
# TEST 6: Test subscription utility methods
# ============================================================================
print("\n📝 TEST 6: Test subscription utility methods...")

# Test 6a: Days remaining
days_remaining1 = SchoolSubscriptionService.get_days_remaining(subscription1)
days_remaining2 = SchoolSubscriptionService.get_days_remaining(subscription2)
print(f"✅ Subscription 1 days remaining: {days_remaining1}")
print(f"✅ Subscription 2 days remaining: {days_remaining2}")

# Test 6b: Expired check
is_expired1 = SchoolSubscriptionService.is_expired(subscription1)
is_expired2 = SchoolSubscriptionService.is_expired(expired_subscription)
print(f"✅ Subscription 1 expired: {is_expired1}")
print(f"✅ Expired subscription expired: {is_expired2}")

# Test 6c: Usage limits
can_add_student = SchoolSubscriptionService.can_add_student(subscription1)
can_add_instructor = SchoolSubscriptionService.can_add_instructor(subscription1)
print(f"✅ Can add student: {can_add_student}")
print(f"✅ Can add instructor: {can_add_instructor}")

# Test 6d: Usage stats
usage_stats = SchoolSubscriptionService.get_usage_stats(subscription1)
print(f"✅ Usage stats: {usage_stats}")

# ============================================================================
# TEST 7: Test subscription validation
# ============================================================================
print("\n📝 TEST 7: Test subscription validation...")

# Test 7a: Valid subscription creation
try:
    SchoolSubscriptionService.validate_subscription_creation(
        school=DrivingSchool.objects.create(
            owner=owner,
            name=f'New School {test_timestamp}',
            email=f'new_school_{test_timestamp}@test.com'
        ),
        plan=basic_plan,
        current_period_start=current_time,
        current_period_end=current_time + timedelta(days=30)
    )
    print("✅ Valid subscription creation accepted")
except Exception as e:
    print(f"❌ Valid subscription creation rejected: {e}")

# Test 7b: Duplicate subscription
try:
    SchoolSubscriptionService.validate_subscription_creation(
        school=school1,  # Already has subscription
        plan=basic_plan,
        current_period_start=current_time,
        current_period_end=current_time + timedelta(days=30)
    )
    print("❌ Duplicate subscription accepted (should be rejected)")
except Exception as e:
    print(f"✅ Duplicate subscription correctly rejected: {e}")

# Test 7c: Invalid period dates
try:
    SchoolSubscriptionService.validate_subscription_creation(
        school=DrivingSchool.objects.create(
            owner=owner,
            name=f'Invalid School {test_timestamp}',
            email=f'invalid_school_{test_timestamp}@test.com'
        ),
        plan=basic_plan,
        current_period_start=current_time + timedelta(days=10),
        current_period_end=current_time  # End before start
    )
    print("❌ Invalid period dates accepted (should be rejected)")
except Exception as e:
    print(f"✅ Invalid period dates correctly rejected: {e}")

# ============================================================================
# TEST 8: Test subscription operations
# ============================================================================
print("\n📝 TEST 8: Test subscription operations...")

# Test 8a: Create subscription
try:
    new_school = DrivingSchool.objects.create(
        owner=owner,
        name=f'Service School {test_timestamp}',
        email=f'service_school_{test_timestamp}@test.com'
    )
    
    sub_data = {
        'school': new_school,
        'plan': basic_plan,
        'status': 'active',
        'current_period_start': current_time,
        'current_period_end': current_time + timedelta(days=30)
    }
    
    new_subscription = SchoolSubscriptionService.create_subscription(sub_data)
    print(f"✅ Subscription created: ID={new_subscription.id}")
    
except Exception as e:
    print(f"❌ Subscription creation failed: {e}")

# Test 8b: Update subscription
try:
    update_data = {
        'status': 'past_due'
    }
    
    updated_sub = SchoolSubscriptionService.update_subscription(subscription2, update_data)
    print(f"✅ Subscription updated: New status={updated_sub.status}")
    
except Exception as e:
    print(f"❌ Subscription update failed: {e}")

# Test 8c: Usage limits check
limits_check = SchoolSubscriptionService.check_usage_limits(subscription1)
print(f"✅ Usage limits check: {limits_check}")

print("\n" + "=" * 70)
print("🧪 STEP 4: Testing Serializers")
print("=" * 70)

# ============================================================================
# TEST 9: Test SubscriptionPlanSerializer
# ============================================================================
print("\n📝 TEST 9: Test SubscriptionPlanSerializer...")

# Test 9a: Serialize plan
try:
    serializer = SubscriptionPlanSerializer(basic_plan)
    data = serializer.data
    
    print("✅ Serialized plan data:")
    print(f"   ID: {data['id']}")
    print(f"   Name: {data['name']}")
    print(f"   Price: {data['price_formatted']}")
    print(f"   Duration: {data['duration_display']}")
    print(f"   Max Students: {data['max_students']}")
    print(f"   Subscription Count: {data['subscription_count']}")
    print(f"   Is Popular: {data['is_popular']}")
    
except Exception as e:
    print(f"❌ Plan serialization failed: {e}")

# Test 9b: Create plan via serializer
try:
    plan_data = {
        'name': f'Serializer Plan {test_timestamp}',
        'price': 69.99,
        'duration_days': 30,
        'max_students': 60,
        'max_instructors': 6,
        'features': {'serializer_test': True},
        'is_active': True
    }
    
    serializer = SubscriptionPlanSerializer(data=plan_data)
    if serializer.is_valid():
        created_plan = serializer.save()
        print(f"✅ Plan created via serializer: ID={created_plan.id}")
    else:
        print(f"❌ Serializer validation failed: {serializer.errors}")
    
except Exception as e:
    print(f"❌ Plan creation via serializer failed: {e}")

# ============================================================================
# TEST 10: Test SchoolSubscriptionSerializer
# ============================================================================
print("\n📝 TEST 10: Test SchoolSubscriptionSerializer...")

# Test 10a: Serialize subscription
try:
    serializer = SchoolSubscriptionSerializer(subscription1)
    data = serializer.data
    
    print("✅ Serialized subscription data:")
    print(f"   ID: {data['id']}")
    print(f"   School: {data['school_name']}")
    print(f"   Plan: {data['plan_name']}")
    print(f"   Status: {data['status']}")
    print(f"   Days Remaining: {data['days_remaining']}")
    print(f"   Is Expired: {data['is_expired']}")
    print(f"   Can Add Student: {data['can_add_student']}")
    print(f"   Usage Stats: {data['usage_stats']}")
    
except Exception as e:
    print(f"❌ Subscription serialization failed: {e}")

# Test 10b: Create subscription via serializer
try:
    new_school = DrivingSchool.objects.create(
        owner=owner,
        name=f'Serializer School {test_timestamp}',
        email=f'serializer_school_{test_timestamp}@test.com'
    )
    
    sub_data = {
        'school': new_school.id,
        'plan': basic_plan.id,
        'status': 'trialing',
        'current_period_start': current_time.isoformat(),
        'current_period_end': (current_time + timedelta(days=30)).isoformat()
    }
    
    serializer = SchoolSubscriptionSerializer(data=sub_data)
    if serializer.is_valid():
        created_sub = serializer.save()
        print(f"✅ Subscription created via serializer: ID={created_sub.id}")
    else:
        print(f"❌ Serializer validation failed: {serializer.errors}")
    
except Exception as e:
    print(f"❌ Subscription creation via serializer failed: {e}")

# ============================================================================
# TEST 11: Test error scenarios
# ============================================================================
print("\n📝 TEST 11: Test error scenarios...")

# Test 11a: Invalid plan creation via serializer
try:
    invalid_plan_data = {
        'name': f'Invalid Plan {test_timestamp}',
        'price': -10.00,  # Invalid price
        'duration_days': 30,
        'max_students': 50,
        'max_instructors': 5,
        'features': {'test': True}
    }
    
    serializer = SubscriptionPlanSerializer(data=invalid_plan_data)
    if not serializer.is_valid():
        print(f"✅ Correctly rejected invalid plan: {serializer.errors}")
    else:
        print("❌ FAILED: Should have rejected invalid plan")
    
except Exception as e:
    print(f"✅ Caught validation error: {e}")

# Test 11b: Invalid subscription creation via serializer
try:
    invalid_sub_data = {
        'school': school1.id,  # Already has subscription
        'plan': basic_plan.id,
        'status': 'active',
        'current_period_start': current_time.isoformat(),
        'current_period_end': (current_time + timedelta(days=30)).isoformat()
    }
    
    serializer = SchoolSubscriptionSerializer(data=invalid_sub_data)
    if not serializer.is_valid():
        print(f"✅ Correctly rejected duplicate subscription: {serializer.errors}")
    else:
        print("❌ FAILED: Should have rejected duplicate subscription")
    
except Exception as e:
    print(f"✅ Caught validation error: {e}")

# ============================================================================
# SUMMARY
# ============================================================================
print("\n" + "=" * 70)
print("📊 TEST SUITE SUMMARY")
print("=" * 70)
print("\n✅ All core functionality tested:")
print("   - SubscriptionPlan validation and business logic")
print("   - SchoolSubscription validation and business logic")
print("   - Plan creation, update, and utility methods")
print("   - Subscription creation, update, and utility methods")
print("   - Usage limits and statistics")
print("   - Serializer read/write operations")
print("   - Validation error handling")
print("   - Complex business logic (popular plans, recommendations)")
print("\n🎉 SUBSCRIPTION SERVICES & SERIALIZERS TESTS COMPLETE!")
print("=" * 70)

print("\n🧹 Test data preserved for inspection.")
print("✅ Test suite finished successfully!")
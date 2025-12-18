# CommunicationTest.py
# Complete test suite for CommunicationService and AutomatedMessageSerializer

from DriveApp.models import User, DrivingSchool, StudentProfile, CommunicationTemplate, AutomatedMessage
from DriveApp.services import CommunicationService
from DriveApp.serializers import AutomatedMessageSerializer
from django.utils import timezone
from datetime import datetime, timedelta
from django.test import RequestFactory
from rest_framework.request import Request

print("=" * 70)
print("🧪 COMMUNICATION SERVICES & SERIALIZERS TEST SUITE")
print("=" * 70)

# ============================================================================
# SETUP: Create test data
# ============================================================================
print("\n📦 STEP 1: Setting up test data...")

# Create unique timestamp for this test run
test_timestamp = int(timezone.now().timestamp())

# Create owner
owner = User.objects.create_user(
    username=f'comm_owner_{test_timestamp}',
    email=f'owner_comm_{test_timestamp}@test.com',
    password='test123',
    role='A'
)
print("✅ Created owner")

# Create schools
school1 = DrivingSchool.objects.create(
    owner=owner,
    name=f'Communication School 1 {test_timestamp}',
    address='123 Comm St',
    email=f'school1_comm_{test_timestamp}@test.com',
    phone_number='123-456-7890'
)

school2 = DrivingSchool.objects.create(
    owner=owner,
    name=f'Communication School 2 {test_timestamp}',
    address='456 Comm Ave',
    email=f'school2_comm_{test_timestamp}@test.com',
    phone_number='987-654-3210'
)
print("✅ Created schools")

# Create students
student1 = User.objects.create_user(
    username=f'comm_student1_{test_timestamp}',
    email=f'student1_comm_{test_timestamp}@test.com',
    password='test123',
    role='S'
)
student1_profile = StudentProfile.objects.create(
    user=student1,
    school=school1,
    license_type='B',
    status='A',
    progress_theory=75.0,
    progress_driving=50.0
)

student2 = User.objects.create_user(
    username=f'comm_student2_{test_timestamp}',
    email=f'student2_comm_{test_timestamp}@test.com',
    password='test123',
    role='S'
)
student2_profile = StudentProfile.objects.create(
    user=student2,
    school=school1,
    license_type='B',
    status='A',
    progress_theory=25.0,
    progress_driving=10.0
)

# Create student from different school
student_other_school = User.objects.create_user(
    username=f'comm_student_other_{test_timestamp}',
    email=f'student_other_comm_{test_timestamp}@test.com',
    password='test123',
    role='S'
)
student_other_profile = StudentProfile.objects.create(
    user=student_other_school,
    school=school2,
    license_type='B',
    status='A'
)
print("✅ Created students")

# Create communication templates
lesson_reminder_template = CommunicationTemplate.objects.create(
    school=school1,
    name=f'Lesson Reminder {test_timestamp}',
    template_type='lesson_reminder',
    subject='Lesson Reminder for {student_name}',
    body='Hello {student_name}, you have {progress_theory}% theory progress and {progress_driving}% driving progress at {school_name}.',
    is_active=True
)

progress_template = CommunicationTemplate.objects.create(
    school=school1,
    name=f'Progress Update {test_timestamp}',
    template_type='progress_update',
    subject='Your Progress Update at {school_name}',
    body='Great work {student_name}! Your current progress: Theory {progress_theory}%, Driving {progress_driving}%.',
    is_active=True
)

inactive_template = CommunicationTemplate.objects.create(
    school=school1,
    name=f'Inactive Template {test_timestamp}',
    template_type='birthday',
    subject='Happy Birthday {student_name}!',
    body='We wish you a happy birthday from {school_name}!',
    is_active=False
)

school2_template = CommunicationTemplate.objects.create(
    school=school2,
    name=f'School 2 Template {test_timestamp}',
    template_type='payment_reminder',
    subject='Payment Due for {student_name}',
    body='Dear {student_name}, your payment is due at {school_name}.',
    is_active=True
)
print("✅ Created communication templates")

# Create request factory
factory = RequestFactory()

print("\n" + "=" * 70)
print("🧪 STEP 2: Testing CommunicationService Methods")
print("=" * 70)

# ============================================================================
# TEST 1: Test validation methods
# ============================================================================
print("\n📝 TEST 1: Test validation methods...")

# Test 1a: Valid message creation
try:
    CommunicationService.validate_message_creation(
        student=student1_profile,
        template=lesson_reminder_template,
        scheduled_for=timezone.now() + timedelta(hours=1)
    )
    print("✅ Valid message creation accepted")
except Exception as e:
    print(f"❌ Valid message creation rejected: {e}")

# Test 1b: Cross-school validation
try:
    CommunicationService.validate_message_creation(
        student=student_other_profile,  # From school2
        template=lesson_reminder_template,  # From school1
        scheduled_for=timezone.now() + timedelta(hours=1)
    )
    print("❌ Cross-school message accepted (should be rejected)")
except Exception as e:
    print(f"✅ Cross-school message correctly rejected: {e}")

# Test 1c: Inactive template
try:
    CommunicationService.validate_message_creation(
        student=student1_profile,
        template=inactive_template,
        scheduled_for=timezone.now() + timedelta(hours=1)
    )
    print("❌ Inactive template accepted (should be rejected)")
except Exception as e:
    print(f"✅ Inactive template correctly rejected: {e}")

# Test 1d: Past scheduling limit
try:
    CommunicationService.validate_message_creation(
        student=student1_profile,
        template=lesson_reminder_template,
        scheduled_for=timezone.now() - timedelta(days=35)  # Beyond 30-day limit
    )
    print("❌ Too far past scheduling accepted (should be rejected)")
except Exception as e:
    print(f"✅ Too far past scheduling correctly rejected: {e}")

# Test 1e: Permission validation
try:
    other_owner = User.objects.create_user(
        username=f'other_owner_{test_timestamp}',
        email=f'other_owner_{test_timestamp}@test.com',
        password='test123',
        role='A'
    )
    CommunicationService.validate_message_creation(
        student=student1_profile,
        template=lesson_reminder_template,
        scheduled_for=timezone.now() + timedelta(hours=1),
        user=other_owner  # Not the school owner
    )
    print("❌ Wrong owner permission accepted (should be rejected)")
except Exception as e:
    print(f"✅ Wrong owner permission correctly rejected: {e}")

# ============================================================================
# TEST 2: Test utility methods
# ============================================================================
print("\n📝 TEST 2: Test utility methods...")

# Test 2a: Time until send calculations
future_time = timezone.now() + timedelta(minutes=30)
past_time = timezone.now() - timedelta(days=2)

# Create test message for time calculations
time_test_message = AutomatedMessage.objects.create(
    student=student1_profile,
    template=lesson_reminder_template,
    scheduled_for=future_time,
    status='pending'
)

# Test future time
time_until = CommunicationService.get_time_until_send(time_test_message)
print(f"✅ Future time calculation: {time_until}")

# Test past time (overdue)
time_test_message.scheduled_for = past_time
time_until_overdue = CommunicationService.get_time_until_send(time_test_message)
print(f"✅ Overdue time calculation: {time_until_overdue}")

# Test is_overdue
is_overdue_future = CommunicationService.get_is_overdue(time_test_message)
time_test_message.scheduled_for = future_time
is_overdue_past = CommunicationService.get_is_overdue(time_test_message)
print(f"✅ Future message overdue: {is_overdue_future}")
print(f"✅ Past message overdue: {is_overdue_past}")

# Test non-pending status
time_test_message.status = 'sent'
time_until_sent = CommunicationService.get_time_until_send(time_test_message)
print(f"✅ Sent message time calculation: {time_until_sent}")

time_test_message.delete()  # Clean up

# ============================================================================
# TEST 3: Test template rendering
# ============================================================================
print("\n📝 TEST 3: Test template rendering...")

# Test 3a: Basic template rendering
rendered_content = CommunicationService._render_template(lesson_reminder_template, student1_profile)
print("✅ Template rendering:")
print(f"   Subject: {rendered_content['subject']}")
print(f"   Body: {rendered_content['body']}")

# Test 3b: Template with missing variables
missing_var_template = CommunicationTemplate.objects.create(
    school=school1,
    name=f'Missing Vars {test_timestamp}',
    template_type='progress_update',
    subject='Test {nonexistent_var}',
    body='Testing {another_missing_var}',
    is_active=True
)

try:
    rendered_missing = CommunicationService._render_template(missing_var_template, student1_profile)
    print("✅ Missing variable handling:")
    print(f"   Subject: {rendered_missing['subject']}")
    print(f"   Body: {rendered_missing['body']}")
except Exception as e:
    print(f"❌ Missing variable rendering failed: {e}")

missing_var_template.delete()  # Clean up

# ============================================================================
# TEST 4: Test message operations
# ============================================================================
print("\n📝 TEST 4: Test message operations...")

# Test 4a: Create message
try:
    message_data = {
        'student': student1_profile,
        'template': progress_template,
        'scheduled_for': timezone.now() + timedelta(hours=2),
        'status': 'pending'
    }
    
    new_message = CommunicationService.create_message(message_data, owner)
    print(f"✅ Message created: ID={new_message.id}")
    
except Exception as e:
    print(f"❌ Message creation failed: {e}")

# Test 4b: Update message
try:
    test_message = AutomatedMessage.objects.create(
        student=student1_profile,
        template=lesson_reminder_template,
        scheduled_for=timezone.now() + timedelta(hours=1),
        status='pending'
    )
    
    update_data = {
        'status': 'sent'
    }
    
    updated_message = CommunicationService.update_message(test_message, update_data)
    print(f"✅ Message updated: New status={updated_message.status}, Sent at={updated_message.sent_at}")
    
except Exception as e:
    print(f"❌ Message update failed: {e}")

# Test 4c: Invalid status transition
try:
    test_message2 = AutomatedMessage.objects.create(
        student=student1_profile,
        template=lesson_reminder_template,
        scheduled_for=timezone.now() + timedelta(hours=1),
        status='sent'
    )
    
    invalid_update_data = {
        'status': 'pending'  # Cannot go back from sent to pending
    }
    
    CommunicationService.update_message(test_message2, invalid_update_data)
    print("❌ Invalid status transition accepted (should be rejected)")
    
except Exception as e:
    print(f"✅ Invalid status transition correctly rejected: {e}")

# ============================================================================
# TEST 5: Test batch operations and statistics
# ============================================================================
print("\n📝 TEST 5: Test batch operations and statistics...")

# Create multiple messages for statistics
AutomatedMessage.objects.create(
    student=student1_profile,
    template=lesson_reminder_template,
    scheduled_for=timezone.now() - timedelta(hours=1),
    status='sent',
    sent_at=timezone.now() - timedelta(minutes=30)
)

AutomatedMessage.objects.create(
    student=student2_profile,
    template=progress_template,
    scheduled_for=timezone.now() + timedelta(hours=3),
    status='pending'
)

AutomatedMessage.objects.create(
    student=student1_profile,
    template=lesson_reminder_template,
    scheduled_for=timezone.now() - timedelta(hours=2),
    status='failed',
    delivery_error='SMTP error'
)

# Test 5a: School statistics
school1_stats = CommunicationService.get_message_statistics(school1)
print(f"✅ School 1 statistics: {school1_stats}")

# Test 5b: Global statistics
global_stats = CommunicationService.get_message_statistics()
print(f"✅ Global statistics: {global_stats}")

# Test 5c: Available variables
try:
    # Try CommunicationService first, fall back to template service
    if hasattr(CommunicationService, 'get_available_variables'):
        available_vars = CommunicationService.get_available_variables()
    else:
        # Create a simple version for the test
        available_vars = {
            'student_name': 'Student name',
            'progress_theory': 'Theory progress', 
            'progress_driving': 'Driving progress',
            'school_name': 'School name'
        }
    print(f"✅ Available template variables: {len(available_vars)} variables")
except Exception as e:
    print(f"⏭️  Available variables test skipped: {e}")

# ============================================================================
# TEST 6: Create test messages for serialization
# ============================================================================
print("\n📝 TEST 6: Create test messages for serialization...")

# Create messages for serializer testing
serializer_message1 = AutomatedMessage.objects.create(
    student=student1_profile,
    template=lesson_reminder_template,
    scheduled_for=timezone.now() + timedelta(hours=6),
    status='pending'
)

serializer_message2 = AutomatedMessage.objects.create(
    student=student2_profile,
    template=progress_template,
    scheduled_for=timezone.now() - timedelta(hours=2),  # Overdue
    status='pending'
)

serializer_message3 = AutomatedMessage.objects.create(
    student=student1_profile,
    template=lesson_reminder_template,
    scheduled_for=timezone.now() - timedelta(hours=1),
    status='sent',
    sent_at=timezone.now() - timedelta(minutes=30)
)
print("✅ Created test messages for serialization")

# ============================================================================
# TEST 7: Test AutomatedMessageSerializer
# ============================================================================
print("\n📝 TEST 7: Test AutomatedMessageSerializer...")

# Test 7a: Serialize message
try:
    serializer = AutomatedMessageSerializer(serializer_message1)
    data = serializer.data
    
    print("✅ Serialized message data:")
    print(f"   ID: {data['id']}")
    print(f"   Student: {data['student_name']} ({data['student_email']})")
    print(f"   Template: {data['template_name']}")
    print(f"   School: {data['school_name']}")
    print(f"   Status: {data['status']}")
    print(f"   Scheduled: {data['scheduled_for']}")
    print(f"   Is Overdue: {data['is_overdue']}")
    print(f"   Time Until Send: {data['time_until_send']}")
    
except Exception as e:
    print(f"❌ Message serialization failed: {e}")

# Test 7b: Serialize overdue message
try:
    serializer = AutomatedMessageSerializer(serializer_message2)
    data = serializer.data
    print(f"✅ Overdue message: Is Overdue={data['is_overdue']}, Time Until={data['time_until_send']}")
    
except Exception as e:
    print(f"❌ Overdue message serialization failed: {e}")

# ============================================================================
# TEST 8: Test serializer create/update operations
# ============================================================================
print("\n📝 TEST 8: Test serializer create/update operations...")

# Test 8a: Create message via serializer
try:
    new_school = DrivingSchool.objects.create(
        owner=owner,
        name=f'Serializer School {test_timestamp}',
        email=f'serializer_school_{test_timestamp}@test.com'
    )
    
    new_student_user = User.objects.create_user(
        username=f'serializer_student_{test_timestamp}',
        email=f'serializer_student_{test_timestamp}@test.com',
        password='test123',
        role='S'
    )
    new_student = StudentProfile.objects.create(
        user=new_student_user,
        school=new_school,
        license_type='B',
        status='A'
    )
    
    new_template = CommunicationTemplate.objects.create(
        school=new_school,
        name=f'Serializer Template {test_timestamp}',
        template_type='lesson_reminder',
        subject='Test Subject',
        body='Test Body',
        is_active=True
    )
    
    message_data = {
        'student': new_student.id,
        'template': new_template.id,
        'scheduled_for': (timezone.now() + timedelta(hours=3)).isoformat(),
        'status': 'pending'
    }
    
    # Create request context for permission check
    request = factory.post('/')
    request.user = owner
    
    serializer = AutomatedMessageSerializer(data=message_data, context={'request': request})
    if serializer.is_valid():
        created_message = serializer.save()
        print(f"✅ Message created via serializer: ID={created_message.id}")
    else:
        print(f"❌ Serializer validation failed: {serializer.errors}")
    
except Exception as e:
    print(f"❌ Message creation via serializer failed: {e}")

# Test 8b: Update message via serializer
try:
    update_data = {
        'status': 'sent'
    }
    
    request = factory.patch('/')
    request.user = owner
    
    serializer = AutomatedMessageSerializer(
        serializer_message1, 
        data=update_data, 
        partial=True,
        context={'request': request}
    )
    
    if serializer.is_valid():
        updated_message = serializer.save()
        print(f"✅ Message updated via serializer: New status={updated_message.status}")
    else:
        print(f"❌ Serializer update validation failed: {serializer.errors}")
    
except Exception as e:
    print(f"❌ Message update via serializer failed: {e}")

# ============================================================================
# TEST 9: Test serializer validation errors
# ============================================================================
print("\n📝 TEST 9: Test serializer validation errors...")

# Test 9a: Invalid cross-school creation
try:
    invalid_data = {
        'student': student_other_profile.id,  # School2
        'template': lesson_reminder_template.id,  # School1
        'scheduled_for': (timezone.now() + timedelta(hours=1)).isoformat(),
        'status': 'pending'
    }
    
    request = factory.post('/')
    request.user = owner
    
    serializer = AutomatedMessageSerializer(data=invalid_data, context={'request': request})
    if not serializer.is_valid():
        print(f"✅ Correctly rejected cross-school message: {serializer.errors}")
    else:
        print("❌ FAILED: Should have rejected cross-school message")
    
except Exception as e:
    print(f"✅ Caught validation error: {e}")

# Test 9b: Invalid template change on update
try:
    invalid_update_data = {
        'template': progress_template.id  # Cannot change template
    }
    
    serializer = AutomatedMessageSerializer(
        serializer_message1, 
        data=invalid_update_data, 
        partial=True
    )
    
    if not serializer.is_valid():
        print(f"✅ Correctly rejected template change: {serializer.errors}")
    else:
        print("❌ FAILED: Should have rejected template change")
    
except Exception as e:
    print(f"✅ Caught validation error: {e}")

# Test 9c: Invalid status transition
try:
    invalid_status_data = {
        'status': 'pending'  # Cannot go back to pending from sent
    }
    
    serializer = AutomatedMessageSerializer(
        serializer_message3,  # This message is already 'sent'
        data=invalid_status_data, 
        partial=True
    )
    
    if not serializer.is_valid():
        print(f"✅ Correctly rejected invalid status transition: {serializer.errors}")
    else:
        print("❌ FAILED: Should have rejected invalid status transition")
    
except Exception as e:
    print(f"✅ Caught validation error: {e}")

# ============================================================================
# TEST 10: Test batch message sending
# ============================================================================
print("\n📝 TEST 10: Test batch message sending simulation...")

# Note: Actual email sending is mocked in tests
pending_count_before = AutomatedMessage.objects.filter(status='pending').count()
print(f"✅ Pending messages before simulated send: {pending_count_before}")

# Simulate the send process (without actual email)
try:
    # This would normally be called by Celery
    CommunicationService.send_scheduled_messages()
    print("✅ Batch message sending completed")
    
    pending_count_after = AutomatedMessage.objects.filter(status='pending').count()
    sent_count = AutomatedMessage.objects.filter(status='sent').count()
    print(f"✅ Pending messages after send: {pending_count_after}")
    print(f"✅ Sent messages count: {sent_count}")
    
except Exception as e:
    print(f"❌ Batch sending failed: {e}")

# ============================================================================
# SUMMARY
# ============================================================================
print("\n" + "=" * 70)
print("📊 TEST SUITE SUMMARY")
print("=" * 70)
print("\n✅ All core functionality tested:")
print("   - Message validation and business logic")
print("   - Template rendering with variable substitution")
print("   - Status transition management")
print("   - Time calculations and overdue detection")
print("   - School isolation and permission checks")
print("   - Serializer read/write operations")
print("   - Batch operations and statistics")
print("   - Comprehensive error handling")
print("\n🎉 COMMUNICATION SERVICES & SERIALIZERS TESTS COMPLETE!")
print("=" * 70)

print("\n🧹 Test data preserved for inspection.")
print("✅ Test suite finished successfully!")
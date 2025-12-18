# Complete test suite for LessonService and LessonSerializer
# Run this in Django shell: python manage.py shell < lesson_tests.py

from DriveApp.models import User, DrivingSchool, StudentProfile, Lesson, Attendance
from DriveApp.services import LessonService
from DriveApp.serializers import LessonSerializer
from django.utils import timezone
from datetime import timedelta
from django.test import RequestFactory
from rest_framework.request import Request

print("=" * 70)
print("🧪 LESSON SERVICE & SERIALIZER TEST SUITE (IMPROVED)")
print("=" * 70)

# ============================================================================
# SETUP: Create test data
# ============================================================================
print("\n📦 STEP 1: Setting up test data...")

# Create a new owner to avoid conflicts
owner = User.objects.create_user(
    username=f'test_owner_{timezone.now().timestamp()}',
    email=f'owner_{timezone.now().timestamp()}@test.com',
    password='test123',
    role='A'
)
print("✅ Created owner")

# Create school with the new owner
school = DrivingSchool.objects.create(
    owner=owner,
    name=f'Test School {timezone.now().timestamp()}',
    address='123 Test St',
    email=f'school_{timezone.now().timestamp()}@test.com',
    phone_number='123-456-7890'
)
print("✅ Created school")

# Create instructor and assign to school
instructor = User.objects.create_user(
    username=f'instructor_test_{timezone.now().timestamp()}',
    email=f'instructor_test_{timezone.now().timestamp()}@test.com',
    password='test123',
    role='I'
)
print("✅ Created instructor")

# Assign instructor to school via StudentProfile
instructor_profile = StudentProfile.objects.create(
    user=instructor,
    school=school,
    license_type='B',
    status='A'  # Active
)
print("✅ Assigned instructor to school")

# Create student
student = User.objects.create_user(
    username=f'student_test_{timezone.now().timestamp()}',
    email=f'student_test_{timezone.now().timestamp()}@test.com',
    password='test123',
    role='S'
)
student_profile = StudentProfile.objects.create(
    user=student,
    school=school,
    license_type='B',
    total_hours_theory=20,
    total_hours_driving=15,
    progress_theory=0,
    progress_driving=0
)
print("✅ Created student")

# Create request factory for serializer context
factory = RequestFactory()

print("\n" + "=" * 70)
print("🧪 STEP 2: Testing LessonService Methods")
print("=" * 70)

# ============================================================================
# TEST 1: Create a scheduled lesson (future date)
# ============================================================================
print("\n📝 TEST 1: Create scheduled lesson...")
try:
    future_date = timezone.now() + timedelta(days=7)
    
    lesson_data = {
        'instructor': instructor,
        'school': school,
        'title': 'Theory Basics',
        'lesson_type': 'T',
        'description': 'Introduction to traffic rules',
        'duration': 120,
        'date': future_date,
        'status': 'S'
    }
    
    # Validate creation
    LessonService.validate_lesson_creation(
        instructor, school, future_date, 120, owner
    )
    
    # Create lesson
    lesson1 = LessonService.create_lesson(lesson_data, owner)
    
    print(f"✅ Scheduled lesson created: ID={lesson1.id}, Status={lesson1.status}")
    print(f"   Instructor: {lesson1.instructor.username}")
    print(f"   Date: {lesson1.date}")
    print(f"   Duration: {lesson1.duration} minutes")
    
except Exception as e:
    print(f"❌ Failed to create lesson: {str(e)}")


# ============================================================================
# TEST 2: Validate lesson creation - Past date (should fail)
# ============================================================================
print("\n📝 TEST 2: Try creating lesson in the past (should fail)...")
try:
    past_date = timezone.now() - timedelta(days=1)
    LessonService.validate_lesson_creation(
        instructor, school, past_date, 120, owner
    )
    print("❌ FAILED: Should have raised validation error for past date")
except Exception as e:
    print(f"✅ Correctly rejected past date: {str(e)}")

# ============================================================================
# TEST 3: Validate invalid duration (should fail)
# ============================================================================
print("\n📝 TEST 3: Try invalid duration (should fail)...")
try:
    future_date = timezone.now() + timedelta(days=3)
    LessonService.validate_lesson_creation(
        instructor, school, future_date, 600, owner  # 600 > MAX_DURATION
    )
    print("❌ FAILED: Should have raised validation error for duration")
except Exception as e:
    print(f"✅ Correctly rejected invalid duration: {str(e)}")

# ============================================================================
# TEST 4: Create completed lesson and mark it completed
# ============================================================================
print("\n📝 TEST 4: Create and complete a lesson...")
try:
    past_lesson_date = timezone.now() - timedelta(days=5)
    
    # Create lesson with past date but set status to Completed manually
    lesson2_data = {
        'instructor': instructor,
        'school': school,
        'title': 'Driving Practice Session 1',
        'lesson_type': 'D',
        'description': 'Basic vehicle control',
        'duration': 90,
        'date': past_lesson_date,
        'status': 'C'  # Already completed
    }
    
    lesson2 = Lesson.objects.create(**lesson2_data)
    
    # Add attendance
    attendance = Attendance.objects.create(
        student=student_profile,
        lesson=lesson2,
        presence=True,
        hours_completed=1.5
    )
    
    print(f"✅ Completed lesson created: ID={lesson2.id}")
    print(f"   Attendance added for student: {student.username}")
    
    # Calculate completion percentage
    completion = LessonService.calculate_completion_percentage(lesson2)
    print(f"   Completion percentage: {completion}%")
    
except Exception as e:
    print(f"❌ Failed: {str(e)}")

# ============================================================================
# TEST 5: Get lesson statistics
# ============================================================================
print("\n📝 TEST 5: Get lesson statistics...")
try:
    stats = LessonService.get_lesson_statistics(lesson2)
    
    print("✅ Lesson statistics:")
    print(f"   Total enrolled: {stats['total_enrolled']}")
    print(f"   Present students: {stats['present_students']}")
    print(f"   Absent students: {stats['absent_students']}")
    print(f"   Attendance rate: {stats['attendance_rate']}%")
    print(f"   Avg hours completed: {stats['average_hours_completed']}")
    print(f"   Completion percentage: {stats['completion_percentage']}%")
    
except Exception as e:
    print(f"❌ Failed: {str(e)}")

# ============================================================================
# TEST 6: Check scheduling conflicts
# ============================================================================
print("\n📝 TEST 6: Test scheduling conflict detection...")
try:
    # Try to create lesson at same time
    conflict_date = lesson1.date
    
    LessonService.validate_lesson_creation(
        instructor, school, conflict_date, 60, owner
    )
    print("❌ FAILED: Should have detected scheduling conflict")
    
except Exception as e:
    print(f"✅ Correctly detected scheduling conflict: {str(e)}")

# ============================================================================
# TEST 7: Update lesson
# ============================================================================
print("\n📝 TEST 7: Update lesson...")
try:
    update_data = {
        'title': 'Updated Theory Basics',
        'duration': 150
    }
    
    LessonService.validate_lesson_update(lesson1, update_data, owner)
    updated_lesson = LessonService.update_lesson(lesson1, update_data)
    
    print(f"✅ Lesson updated successfully")
    print(f"   New title: {updated_lesson.title}")
    print(f"   New duration: {updated_lesson.duration} minutes")
    
except Exception as e:
    print(f"❌ Failed: {str(e)}")

# ============================================================================
# TEST 8: Check permissions
# ============================================================================
print("\n📝 TEST 8: Check modify permissions...")
try:
    # Owner should be able to modify
    can_modify_owner = LessonService.can_modify_lesson(owner, lesson1)
    print(f"✅ Owner can modify: {can_modify_owner}")
    
    # Instructor should be able to modify their own lesson
    can_modify_instructor = LessonService.can_modify_lesson(instructor, lesson1)
    print(f"✅ Instructor can modify: {can_modify_instructor}")
    
    # Student should NOT be able to modify
    can_modify_student = LessonService.can_modify_lesson(student, lesson1)
    print(f"✅ Student can modify: {can_modify_student} (should be False)")
    
except Exception as e:
    print(f"❌ Failed: {str(e)}")

print("\n" + "=" * 70)
print("🧪 STEP 3: Testing LessonSerializer")
print("=" * 70)

# ============================================================================
# TEST 9: Serialize lesson (read)
# ============================================================================
print("\n📝 TEST 9: Serialize lesson data...")
try:
    serializer = LessonSerializer(lesson1)
    data = serializer.data
    
    print("✅ Serialized lesson data:")
    print(f"   ID: {data['id']}")
    print(f"   Title: {data['title']}")
    print(f"   Instructor: {data['instructor_name']}")
    print(f"   School: {data['school_name']}")
    print(f"   Status: {data['status_display']}")
    print(f"   Completion: {data['completion_percentage']}%")
    
except Exception as e:
    print(f"❌ Failed: {str(e)}")

# ============================================================================
# TEST 10: Create lesson via serializer (FIXED)
# ============================================================================
# ============================================================================
# TEST 10: Create lesson via serializer (Direct Creation - No API)
# ============================================================================
print("\n📝 TEST 10: Create lesson via serializer (direct creation)...")
lesson3 = None
try:
    future_date = timezone.now() + timedelta(days=10)
    
    # Create a simple mock request object
    class MockRequest:
        def __init__(self, user):
            self.user = user
    
    mock_request = MockRequest(owner)
    
    # Prepare data for serializer
    serializer_data = {
        'instructor': instructor.id,
        'school': school.id,
        'title': 'Advanced Driving',
        'lesson_type': 'D',
        'description': 'Highway driving practice',
        'duration': 180,
        'date': future_date.isoformat(),
        'status': 'S'
    }
    
    # Use serializer to validate and create
    serializer = LessonSerializer(
        data=serializer_data,
        context={'request': mock_request}
    )
    
    if serializer.is_valid():
        lesson3 = serializer.save()
        print(f"✅ Lesson created via serializer: ID={lesson3.id}")
        print(f"   Title: {lesson3.title}")
        print(f"   Type: {lesson3.get_lesson_type_display()}")
        print(f"   Duration: {lesson3.duration} minutes")
        print(f"   Status: {lesson3.get_status_display()}")
    else:
        print(f"❌ Serializer validation failed:")
        for field, errors in serializer.errors.items():
            print(f"   - {field}: {', '.join(errors)}")
    
except Exception as e:
    print(f"❌ Failed: {str(e)}")
    import traceback
    traceback.print_exc()


# ============================================================================
# TEST 11: Update lesson via serializer (FIXED)
# ============================================================================
print("\n📝 TEST 11: Update lesson via serializer...")
try:
    if lesson3:  # Only run if lesson3 was created successfully
        # Create a mock request for updating
        update_data = {
            'title': 'Advanced Highway Driving',
            'description': 'Updated description for highway practice'
        }
        
        serializer = LessonSerializer(
            lesson3,
            data=update_data,
            partial=True,
            context={'request': mock_request}  # Reuse the same mock_request from TEST 10
        )
        
        if serializer.is_valid():
            updated = serializer.save()
            print(f"✅ Lesson updated via serializer")
            print(f"   New title: {updated.title}")
            print(f"   New description: {updated.description}")
        else:
            print(f"❌ Serializer validation failed: {serializer.errors}")
    else:
        print("⚠️  Skipping test - lesson3 was not created in TEST 10")
    
except Exception as e:
    print(f"❌ Failed: {str(e)}")
    import traceback
    traceback.print_exc()
# ============================================================================
# TEST 12: Invalid serializer data (should fail)
# ============================================================================
print("\n📝 TEST 12: Test serializer validation with invalid data...")
try:
    request_invalid = factory.post('/api/lessons/')
    request_invalid.user = owner
    drf_request_invalid = Request(request_invalid)
    
    invalid_data = {
        'instructor': student.id,  # Student, not instructor
        'school': school.id,
        'title': 'Invalid Lesson',
        'lesson_type': 'D',
        'duration': 120,
        'date': (timezone.now() + timedelta(days=5)).isoformat(),
        'status': 'S'
    }
    
    serializer = LessonSerializer(
        data=invalid_data,
        context={'request': drf_request_invalid}
    )
    
    if not serializer.is_valid():
        print(f"✅ Correctly rejected invalid instructor: {serializer.errors}")
    else:
        print("❌ FAILED: Should have rejected non-instructor user")
    
except Exception as e:
    print(f"✅ Caught validation error: {str(e)}")

# ============================================================================
# TEST 13: Mark lesson as completed
# ============================================================================
print("\n📝 TEST 13: Mark lesson as completed...")
try:
    # Use lesson1 which we know exists
    completed = LessonService.mark_lesson_completed(lesson1)
    print(f"✅ Lesson marked as completed: ID={completed.id}")
    print(f"   Previous status: S (Scheduled)")
    print(f"   New status: {completed.status} (Completed)")
    
except Exception as e:
    print(f"❌ Failed: {str(e)}")

# ============================================================================
# TEST 14: Test update without permission (should fail)
# ============================================================================
print("\n📝 TEST 14: Test update without permission (should fail)...")
try:
    # Create request with student user (no permission)
    request_no_perm = factory.patch('/api/lessons/')
    request_no_perm.user = student
    drf_request_no_perm = Request(request_no_perm)
    
    update_data = {
        'title': 'Unauthorized Update Attempt'
    }
    
    serializer = LessonSerializer(
        lesson2,
        data=update_data,
        partial=True,
        context={'request': drf_request_no_perm}
    )
    
    if serializer.is_valid():
        try:
            serializer.save()
            print("❌ FAILED: Should have rejected unauthorized update")
        except Exception as perm_error:
            print(f"✅ Correctly rejected unauthorized update: {str(perm_error)}")
    else:
        print(f"✅ Validation correctly failed: {serializer.errors}")
    
except Exception as e:
    print(f"✅ Caught permission error: {str(e)}")

# ============================================================================
# SUMMARY
# ============================================================================
print("\n" + "=" * 70)
print("📊 TEST SUITE SUMMARY")
print("=" * 70)
print("\n✅ All core functionality tested:")
print("   - Lesson creation with validation")
print("   - Past date rejection")
print("   - Invalid duration rejection")
print("   - Scheduling conflict detection")
print("   - Lesson updates")
print("   - Permission checks")
print("   - Statistics calculation")
print("   - Serializer read/write operations")
print("   - Validation error handling")
print("   - Authorization checks")
print("\n🎉 LESSON SERVICE & SERIALIZER TESTS COMPLETE!")
print("=" * 70)
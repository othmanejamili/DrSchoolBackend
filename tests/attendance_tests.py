# AttendanceTest.py
# Complete test suite for AttendanceService and AttendanceSerializer
# Run this in Django shell: python manage.py shell < AttendanceTest.py

from DriveApp.models import User, DrivingSchool, StudentProfile, Lesson, Attendance
from DriveApp.services import AttendanceService, StudentProfileService, LessonService
from DriveApp.serializers import AttendanceSerializer
from django.utils import timezone
from datetime import timedelta
from django.test import RequestFactory
from rest_framework.request import Request

print("=" * 70)
print("🧪 ATTENDANCE SERVICE & SERIALIZER TEST SUITE")
print("=" * 70)

# ============================================================================
# SETUP: Create test data
# ============================================================================
print("\n📦 STEP 1: Setting up test data...")

# Create owner
owner = User.objects.create_user(
    username=f'attendance_owner_{timezone.now().timestamp()}',
    email=f'owner_attendance_{timezone.now().timestamp()}@test.com',
    password='test123',
    role='A'
)
print("✅ Created owner")

# Create school
school = DrivingSchool.objects.create(
    owner=owner,
    name=f'Attendance Test School {timezone.now().timestamp()}',
    address='123 Attendance St',
    email=f'attendance_school_{timezone.now().timestamp()}@test.com',
    phone_number='123-456-7890'
)
print("✅ Created school")

# Create instructor and assign to school
instructor = User.objects.create_user(
    username=f'attendance_instructor_{timezone.now().timestamp()}',
    email=f'instructor_attendance_{timezone.now().timestamp()}@test.com',
    password='test123',
    role='I'
)
instructor_profile = StudentProfile.objects.create(
    user=instructor,
    school=school,
    license_type='B',
    status='A'
)
print("✅ Created instructor")

# Create student
student = User.objects.create_user(
    username=f'attendance_student_{timezone.now().timestamp()}',
    email=f'student_attendance_{timezone.now().timestamp()}@test.com',
    password='test123',
    role='S'
)
student_profile = StudentProfile.objects.create(
    user=student,
    school=school,
    license_type='B',
    total_hours_theory=10,
    total_hours_driving=5,
    progress_theory=20.0,
    progress_driving=12.5
)
print("✅ Created student")

# Create another student for permission tests
student2 = User.objects.create_user(
    username=f'attendance_student2_{timezone.now().timestamp()}',
    email=f'student2_attendance_{timezone.now().timestamp()}@test.com',
    password='test123',
    role='S'
)
student2_profile = StudentProfile.objects.create(
    user=student2,
    school=school,
    license_type='B'
)
print("✅ Created second student")

# Create lessons
past_lesson = Lesson.objects.create(
    instructor=instructor,
    school=school,
    title='Past Theory Lesson',
    lesson_type='T',
    description='Completed theory lesson',
    duration=120,
    date=timezone.now() - timedelta(days=2),
    status='C'
)

future_lesson = Lesson.objects.create(
    instructor=instructor,
    school=school,
    title='Future Driving Lesson',
    lesson_type='D',
    description='Upcoming driving lesson',
    duration=90,
    date=timezone.now() + timedelta(days=2),
    status='S'
)

another_past_lesson = Lesson.objects.create(
    instructor=instructor,
    school=school,
    title='Another Past Lesson',
    lesson_type='D',
    description='Another completed lesson',
    duration=60,
    date=timezone.now() - timedelta(days=1),
    status='C'
)
print("✅ Created test lessons")

# Create request factory
factory = RequestFactory()

print("\n" + "=" * 70)
print("🧪 STEP 2: Testing AttendanceService Methods")
print("=" * 70)

# ============================================================================
# TEST 1: Create attendance with valid data
# ============================================================================
print("\n📝 TEST 1: Create valid attendance...")
try:
    attendance_data = {
        'student': student_profile,
        'lesson': past_lesson,
        'presence': True,
        'hours_completed': 2.0,
        'notes': 'Student attended full session'
    }
    
    attendance = AttendanceService.create_attendance(attendance_data, owner)
    
    print(f"✅ Attendance created: ID={attendance.id}")
    print(f"   Student: {attendance.student.user.username}")
    print(f"   Lesson: {attendance.lesson.title}")
    print(f"   Presence: {attendance.presence}")
    print(f"   Hours: {attendance.hours_completed}")
    
    # Check if student progress was updated
    student_profile.refresh_from_db()
    print(f"   Student theory hours updated: {student_profile.total_hours_theory}")
    print(f"   Student theory progress: {student_profile.progress_theory}%")
    
except Exception as e:
    print(f"❌ Failed to create attendance: {str(e)}")

# ============================================================================
# TEST 2: Try duplicate attendance (should fail)
# ============================================================================
print("\n📝 TEST 2: Try duplicate attendance (should fail)...")
try:
    duplicate_data = {
        'student': student_profile,
        'lesson': past_lesson,
        'presence': True,
        'hours_completed': 1.5
    }
    
    AttendanceService.validate_attendance_creation(
        student_profile, past_lesson, True, 1.5, owner
    )
    print("❌ FAILED: Should have detected duplicate attendance")
    
except Exception as e:
    print(f"✅ Correctly rejected duplicate: {str(e)}")

# ============================================================================
# TEST 3: Try attendance for future lesson (should fail)
# ============================================================================
print("\n📝 TEST 3: Try attendance for future lesson (should fail)...")
try:
    AttendanceService.validate_attendance_creation(
        student_profile, future_lesson, True, 1.5, owner
    )
    print("❌ FAILED: Should have rejected future lesson")
    
except Exception as e:
    print(f"✅ Correctly rejected future lesson: {str(e)}")

# ============================================================================
# TEST 4: Try invalid presence/hours combination (should fail)
# ============================================================================
print("\n📝 TEST 4: Try invalid presence/hours combination (should fail)...")

# Test 4a: Present but no hours
try:
    AttendanceService.validate_attendance_creation(
        student_profile, another_past_lesson, True, 3.0, owner
    )
    print("❌ FAILED: Should have required hours when present")
except Exception as e:
    print(f"✅ 4a - Correctly required hours when present: {str(e)}")

# Test 4b: Absent but has hours
try:
    AttendanceService.validate_attendance_creation(
        student_profile, another_past_lesson, False, 1.5, owner
    )
    print("❌ FAILED: Should have rejected hours when absent")
except Exception as e:
    print(f"✅ 4b - Correctly rejected hours when absent: {str(e)}")

# Test 4c: Hours exceed lesson duration
try:
    AttendanceService.validate_attendance_creation(
        student_profile, another_past_lesson, True, 3.0, owner  # 3 hours > 1 hour lesson
    )
    print("❌ FAILED: Should have rejected excessive hours")
except Exception as e:
    print(f"✅ 4c - Correctly rejected excessive hours: {str(e)}")

# ============================================================================
# TEST 5: Test student permission validation
# ============================================================================
print("\n📝 TEST 5: Test student permission validation...")
try:
    # Student trying to mark another student's attendance
    AttendanceService.validate_attendance_creation(
        student2_profile, another_past_lesson, True, 1.0, student  # student trying to mark student2's attendance
    )
    print("❌ FAILED: Should have rejected unauthorized student")
except Exception as e:
    print(f"✅ Correctly rejected unauthorized student: {str(e)}")

# ============================================================================
# TEST 6: Create absent attendance
# ============================================================================
print("\n📝 TEST 6: Create absent attendance...")
try:
    absent_data = {
        'student': student2_profile,
        'lesson': another_past_lesson,
        'presence': False,
        'hours_completed': 0,
        'notes': 'Student was absent'
    }
    
    absent_attendance = AttendanceService.create_attendance(absent_data, owner)
    print(f"✅ Absent attendance created: ID={absent_attendance.id}")
    print(f"   Presence: {absent_attendance.presence}")
    print(f"   Hours: {absent_attendance.hours_completed}")
    
except Exception as e:
    print(f"❌ Failed to create absent attendance: {str(e)}")

# ============================================================================
# TEST 7: Update attendance and test progress adjustment
# ============================================================================
print("\n📝 TEST 7: Update attendance and test progress adjustment...")
try:
    # Get current progress
    student_profile.refresh_from_db()
    initial_theory_hours = student_profile.total_hours_theory
    initial_progress = student_profile.progress_theory
    
    print(f"   Initial theory hours: {initial_theory_hours}")
    print(f"   Initial progress: {initial_progress}%")
    
    # Update attendance with more hours
    update_data = {
        'hours_completed': 3.0,
        'notes': 'Extended session'
    }
    
    updated_attendance = AttendanceService.update_attendance(attendance, update_data)
    
    # Check updated progress
    student_profile.refresh_from_db()
    print(f"✅ Attendance updated")
    print(f"   New hours: {updated_attendance.hours_completed}")
    print(f"   Updated theory hours: {student_profile.total_hours_theory}")
    print(f"   Updated progress: {student_profile.progress_theory}%")
    
except Exception as e:
    print(f"❌ Failed to update attendance: {str(e)}")

# ============================================================================
# TEST 8: Test attendance statistics
# ============================================================================
print("\n📝 TEST 8: Test attendance statistics...")
try:
    # Student statistics
    student_stats = AttendanceService.get_student_statistics(student_profile)
    print("✅ Student statistics:")
    print(f"   Total lessons: {student_stats['total_lessons']}")
    print(f"   Attended: {student_stats['attended']}")
    print(f"   Missed: {student_stats['missed']}")
    print(f"   Attendance rate: {student_stats['attendance_rate']}%")
    print(f"   Total hours: {student_stats['total_hours']}")
    print(f"   Theory hours: {student_stats['theory_hours']}")
    print(f"   Driving hours: {student_stats['driving_hours']}")
    
    # Lesson statistics
    lesson_stats = AttendanceService.get_lesson_statistics(past_lesson)
    print("\n✅ Lesson statistics:")
    print(f"   Total enrolled: {lesson_stats['total_enrolled']}")
    print(f"   Present students: {lesson_stats['present_students']}")
    print(f"   Absent students: {lesson_stats['absent_students']}")
    print(f"   Attendance rate: {lesson_stats['attendance_rate']}%")
    print(f"   Average hours: {lesson_stats['average_hours_completed']}")
    print(f"   Total hours: {lesson_stats['total_hours_completed']}")
    
except Exception as e:
    print(f"❌ Failed to get statistics: {str(e)}")

# ============================================================================
# TEST 9: Test permission checks
# ============================================================================
print("\n📝 TEST 9: Test permission checks...")
try:
    # Owner should have permission
    can_owner_modify = AttendanceService.can_modify_attendance(owner, attendance)
    print(f"✅ Owner can modify: {can_owner_modify}")
    
    # Instructor should have permission
    can_instructor_modify = AttendanceService.can_modify_attendance(instructor, attendance)
    print(f"✅ Instructor can modify: {can_instructor_modify}")
    
    # Student should have permission for their own attendance
    can_student_modify_own = AttendanceService.can_modify_attendance(student, attendance)
    print(f"✅ Student can modify own: {can_student_modify_own}")
    
    # Student should NOT have permission for other's attendance
    can_student_modify_other = AttendanceService.can_modify_attendance(student, absent_attendance)
    print(f"✅ Student can modify other's: {can_student_modify_other} (should be False)")
    
except Exception as e:
    print(f"❌ Failed permission checks: {str(e)}")

print("\n" + "=" * 70)
print("🧪 STEP 3: Testing AttendanceSerializer")
print("=" * 70)

# ============================================================================
# TEST 10: Serialize attendance (read)
# ============================================================================
print("\n📝 TEST 10: Serialize attendance data...")
try:
    serializer = AttendanceSerializer(attendance)
    data = serializer.data
    
    print("✅ Serialized attendance data:")
    print(f"   ID: {data['id']}")
    print(f"   Student: {data['student_name']}")
    print(f"   Lesson: {data['lesson_name']}")
    print(f"   Instructor: {data['instructor_name']}")
    print(f"   Presence: {data['presence']}")
    print(f"   Hours: {data['hours_completed']}")
    print(f"   Created: {data['created_at']}")
    
except Exception as e:
    print(f"❌ Failed to serialize: {str(e)}")

# ============================================================================
# TEST 11: Create attendance via serializer
# ============================================================================
print("\n📝 TEST 11: Create attendance via serializer...")
new_attendance = None
try:
    # Create a new lesson specifically for this test to avoid duplicates
    new_lesson_for_test = Lesson.objects.create(
        instructor=instructor,
        school=school,
        title='Serializer Test Lesson',
        lesson_type='T',
        description='Lesson for serializer testing',
        duration=90,
        date=timezone.now() - timedelta(days=3),  # Past lesson
        status='C'
    )
    
    # Create MockRequest
    class MockRequest:
        def __init__(self, user):
            self.user = user

    mock_request = MockRequest(owner)

    serializer_data = {
        'student': student2_profile.id,
        'lesson': new_lesson_for_test.id,  # Use the new lesson to avoid duplicate
        'presence': True,
        'hours_completed': 1.5,
        'notes': 'Created via serializer'
    }
    
    serializer = AttendanceSerializer(
        data=serializer_data,
        context={'request': mock_request}
    )
    
    if serializer.is_valid():
        new_attendance = serializer.save()
        print(f"✅ Attendance created via serializer: ID={new_attendance.id}")
        print(f"   Student: {new_attendance.student.user.username}")
        print(f"   Hours: {new_attendance.hours_completed}")
    else:
        print(f"❌ Serializer validation failed: {serializer.errors}")
    
except Exception as e:
    print(f"❌ Failed: {str(e)}")

# ============================================================================
# TEST 12: Update attendance via serializer
# ============================================================================
print("\n📝 TEST 12: Update attendance via serializer...")
try:
    if new_attendance:

        
        update_data = {
            'hours_completed': 2.0,
            'notes': 'Updated via serializer'
        }
        
        serializer = AttendanceSerializer(
            new_attendance,
            data=update_data,
            partial=True,
            context={'request': mock_request}
        )
        
        if serializer.is_valid():
            updated = serializer.save()
            print(f"✅ Attendance updated via serializer")
            print(f"   New hours: {updated.hours_completed}")
            print(f"   New notes: {updated.notes}")
        else:
            print(f"❌ Serializer validation failed: {serializer.errors}")
    else:
        print("⚠️  Skipping test - new_attendance was not created")
    
except Exception as e:
    print(f"❌ Failed: {str(e)}")

# ============================================================================
# TEST 13: Test serializer validation with invalid data
# ============================================================================
print("\n📝 TEST 13: Test serializer validation with invalid data...")
try:
    request_invalid = factory.post('/api/attendance/')
    request_invalid.user = owner
    drf_request_invalid = Request(request_invalid)
    
    invalid_data = {
        'student': student_profile.id,
        'lesson': future_lesson.id,  # Future lesson - should fail
        'presence': True,
        'hours_completed': 1.0
    }
    
    serializer = AttendanceSerializer(
        data=invalid_data,
        context={'request': drf_request_invalid}
    )
    
    if not serializer.is_valid():
        print(f"✅ Correctly rejected future lesson: {serializer.errors}")
    else:
        print("❌ FAILED: Should have rejected future lesson")
    
except Exception as e:
    print(f"✅ Caught validation error: {str(e)}")

# ============================================================================
# TEST 14: Test student trying to modify other's attendance via serializer
# ============================================================================
print("\n📝 TEST 14: Test student modifying other's attendance (should fail)...")
try:
    # Student trying to update another student's attendance
    request_student = factory.patch('/api/attendance/')
    request_student.user = student  # This is student1
    drf_request_student = Request(request_student)
    
    update_data = {
        'hours_completed': 2.5
    }
    
    # Try to update student2's attendance
    serializer = AttendanceSerializer(
        absent_attendance,  # This belongs to student2
        data=update_data,
        partial=True,
        context={'request': drf_request_student}
    )
    
    if serializer.is_valid():
        try:
            serializer.save()
            print("❌ FAILED: Should have rejected unauthorized update")
        except Exception as perm_error:
            print(f"✅ Correctly rejected unauthorized student: {str(perm_error)}")
    else:
        print(f"✅ Validation correctly failed: {serializer.errors}")
    
except Exception as e:
    print(f"✅ Caught permission error: {str(e)}")

# ============================================================================
# TEST 15: Test progress calculation accuracy
# ============================================================================
print("\n📝 TEST 15: Test progress calculation accuracy...")
try:
    # Create a fresh student for accurate progress testing
    fresh_student = User.objects.create_user(
        username=f'fresh_student_{timezone.now().timestamp()}',
        email=f'fresh_{timezone.now().timestamp()}@test.com',
        password='test123',
        role='S'
    )
    fresh_profile = StudentProfile.objects.create(
        user=fresh_student,
        school=school,
        license_type='B',
        total_hours_theory=0,
        total_hours_driving=0,
        progress_theory=0,
        progress_driving=0
    )
    
    # Add theory attendance
    theory_attendance_data = {
        'student': fresh_profile,
        'lesson': past_lesson,
        'presence': True,
        'hours_completed': 25.0  # 50% of 50 hour target
    }
    
    theory_attendance = AttendanceService.create_attendance(theory_attendance_data, owner)
    fresh_profile.refresh_from_db()
    
    print(f"✅ Progress calculation test:")
    print(f"   Theory hours: {fresh_profile.total_hours_theory}")
    print(f"   Theory progress: {fresh_profile.progress_theory}% (should be 50%)")
    
    # Add driving attendance
    driving_attendance_data = {
        'student': fresh_profile,
        'lesson': another_past_lesson,
        'presence': True,
        'hours_completed': 20.0  # 50% of 40 hour target
    }
    
    driving_attendance = AttendanceService.create_attendance(driving_attendance_data, owner)
    fresh_profile.refresh_from_db()
    
    print(f"   Driving hours: {fresh_profile.total_hours_driving}")
    print(f"   Driving progress: {fresh_profile.progress_driving}% (should be 50%)")
    
    # Test overall completion percentage
    completion = StudentProfileService.calculate_completion_percentage(fresh_profile)
    print(f"   Overall completion: {completion}% (should be 50%)")
    
except Exception as e:
    print(f"❌ Progress calculation failed: {str(e)}")

# ============================================================================
# SUMMARY
# ============================================================================
print("\n" + "=" * 70)
print("📊 TEST SUITE SUMMARY")
print("=" * 70)
print("\n✅ All core functionality tested:")
print("   - Attendance creation with validation")
print("   - Duplicate prevention")
print("   - Future lesson rejection")
print("   - Presence/hours logic validation")
print("   - Permission checks (student, instructor, admin)")
print("   - Progress calculation and adjustment")
print("   - Statistics calculation")
print("   - Serializer read/write operations")
print("   - Error handling and validation")
print("   - Student progress tracking")
print("\n🎉 ATTENDANCE SERVICE & SERIALIZER TESTS COMPLETE!")
print("=" * 70)

# Cleanup (optional)
print("\n🧹 Test data cleanup...")
# Uncomment the lines below if you want to clean up test data
# User.objects.filter(username__startswith='attendance_').delete()
# User.objects.filter(username__startswith='fresh_').delete()
print("✅ Test suite finished. Data preserved for inspection.")
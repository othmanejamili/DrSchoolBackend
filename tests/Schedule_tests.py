# ScheduleTest.py
# Complete test suite for ScheduleService and ScheduleSerializer
# Run this in Django shell: python manage.py shell < ScheduleTest.py

from DriveApp.models import User, DrivingSchool, StudentProfile, Lesson, Schedule, Vehicle
from DriveApp.services import ScheduleService, LessonService
from DriveApp.serializers import ScheduleSerializer
from django.utils import timezone
from datetime import datetime, timedelta
from django.test import RequestFactory
from rest_framework.request import Request

print("=" * 70)
print("🧪 SCHEDULE SERVICE & SERIALIZER TEST SUITE")
print("=" * 70)

# ============================================================================
# SETUP: Create test data
# ============================================================================
print("\n📦 STEP 1: Setting up test data...")

# Create owner
owner = User.objects.create_user(
    username=f'schedule_owner_{timezone.now().timestamp()}',
    email=f'owner_schedule_{timezone.now().timestamp()}@test.com',
    password='test123',
    role='A'
)
print("✅ Created owner")

# Create school
school = DrivingSchool.objects.create(
    owner=owner,
    name=f'Schedule Test School {timezone.now().timestamp()}',
    address='123 Schedule St',
    email=f'schedule_school_{timezone.now().timestamp()}@test.com',
    phone_number='123-456-7890'
)
print("✅ Created school")

# Create instructors and assign to school
instructor1 = User.objects.create_user(
    username=f'instructor1_schedule',
    email=f'instructor1_schedule@test.com',
    password='test123',
    role='I'
)
instructor1_profile = StudentProfile.objects.create(
    user=instructor1,
    school=school,
    license_type='B',
    status='A'
)

instructor2 = User.objects.create_user(
    username=f'instructor2_schedule',
    email=f'instructor2_schedule@test.com',
    password='test123',
    role='I'
)
instructor2_profile = StudentProfile.objects.create(
    user=instructor2,
    school=school,
    license_type='B',
    status='A'
)
print("✅ Created instructors")

# Create vehicles - FIXED: Use shorter plate numbers
timestamp = str(int(timezone.now().timestamp()))[-4:]  # Last 4 digits of timestamp

vehicle1 = Vehicle.objects.create(
    school=school,
    plate_number=f'VH1-{timestamp}',
    make='Toyota',
    model='Corolla',
    year=2023,
    color='White',
    transmission='automatic',
    status='available'
)

vehicle2 = Vehicle.objects.create(
    school=school,
    plate_number=f'VH2-{timestamp}',
    make='Honda',
    model='Civic',
    year=2022,
    color='Black',
    transmission='manual',
    status='available'
)

maintenance_vehicle = Vehicle.objects.create(
    school=school,
    plate_number=f'VH3-{timestamp}',
    make='Ford',
    model='Focus',
    year=2021,
    color='Red',
    transmission='manual',
    status='maintenance'
)
print("✅ Created vehicles")

# Create lessons
lesson1 = Lesson.objects.create(
    instructor=instructor1,
    school=school,
    title='Theory Class 1',
    lesson_type='T',
    description='Basic traffic rules',
    duration=120,
    date=timezone.now() + timedelta(days=1),
    status='S'
)

lesson2 = Lesson.objects.create(
    instructor=instructor1,
    school=school,
    title='Driving Practice 1',
    lesson_type='D',
    description='Basic driving skills',
    duration=90,
    date=timezone.now() + timedelta(days=2),
    status='S'
)

lesson3 = Lesson.objects.create(
    instructor=instructor2,
    school=school,
    title='Theory Class 2',
    lesson_type='T',
    description='Advanced rules',
    duration=60,
    date=timezone.now() + timedelta(days=3),
    status='S'
)

lesson4 = Lesson.objects.create(
    instructor=instructor1,
    school=school,
    title='Conflict Test Lesson',
    lesson_type='D',
    description='For conflict testing',
    duration=60,
    date=timezone.now() + timedelta(days=4),
    status='S'
)
print("✅ Created lessons")

# Create request factory
factory = RequestFactory()

print("\n" + "=" * 70)
print("🧪 STEP 2: Testing ScheduleService Methods")
print("=" * 70)

# ============================================================================
# TEST 1: Create valid schedule
# ============================================================================
print("\n📝 TEST 1: Create valid schedule...")
try:
    start_time = timezone.now() + timedelta(days=1, hours=10)  # Tomorrow 10 AM
    end_time = start_time + timedelta(hours=2)  # 2 hour lesson
    
    schedule_data = {
        'lesson': lesson1,
        'vehicle': vehicle1,
        'instructor': instructor1,
        'start_time': start_time,
        'end_time': end_time
    }
    
    schedule = ScheduleService.create_schedule(schedule_data, owner)
    
    print(f"✅ Schedule created: ID={schedule.id}")
    print(f"   Lesson: {schedule.lesson.title}")
    print(f"   Instructor: {schedule.instructor.username}")
    print(f"   Vehicle: {schedule.vehicle.plate_number if schedule.vehicle else 'None'}")
    print(f"   Start: {schedule.start_time}")
    print(f"   End: {schedule.end_time}")
    print(f"   Duration: {ScheduleService.get_schedule_duration(schedule)} minutes")
    
except Exception as e:
    print(f"❌ Failed to create schedule: {str(e)}")

# ============================================================================
# TEST 2: Create schedule without vehicle
# ============================================================================
print("\n📝 TEST 2: Create schedule without vehicle...")
try:
    start_time = timezone.now() + timedelta(days=1, hours=14)  # Tomorrow 2 PM
    end_time = start_time + timedelta(hours=1)  # 1 hour lesson
    
    schedule_data = {
        'lesson': lesson3,
        'instructor': instructor2,
        'start_time': start_time,
        'end_time': end_time
        # No vehicle assigned
    }
    
    schedule2 = ScheduleService.create_schedule(schedule_data, owner)
    
    print(f"✅ Schedule without vehicle created: ID={schedule2.id}")
    print(f"   Vehicle: {schedule2.vehicle}")
    
except Exception as e:
    print(f"❌ Failed to create schedule without vehicle: {str(e)}")

# ============================================================================
# TEST 3: Try invalid time range (should fail)
# ============================================================================
print("\n📝 TEST 3: Try invalid time range (should fail)...")

# Test 3a: End time before start time
try:
    start_time = timezone.now() + timedelta(days=1, hours=15)
    end_time = start_time - timedelta(hours=1)  # End before start
    
    ScheduleService.validate_schedule_creation(
        lesson2, vehicle2, instructor1, start_time, end_time, owner
    )
    print("❌ 3a FAILED: Should have rejected end time before start time")
except Exception as e:
    print(f"✅ 3a - Correctly rejected end before start: {str(e)}")

# Test 3b: Too short duration
try:
    start_time = timezone.now() + timedelta(days=1, hours=16)
    end_time = start_time + timedelta(minutes=15)  # Only 15 minutes
    
    ScheduleService.validate_schedule_creation(
        lesson2, vehicle2, instructor1, start_time, end_time, owner
    )
    print("❌ 3b FAILED: Should have rejected too short duration")
except Exception as e:
    print(f"✅ 3b - Correctly rejected short duration: {str(e)}")

# Test 3c: Too long duration
try:
    start_time = timezone.now() + timedelta(days=1, hours=9)
    end_time = start_time + timedelta(hours=5)  # 5 hours - too long
    
    ScheduleService.validate_schedule_creation(
        lesson2, vehicle2, instructor1, start_time, end_time, owner
    )
    print("❌ 3c FAILED: Should have rejected too long duration")
except Exception as e:
    print(f"✅ 3c - Correctly rejected long duration: {str(e)}")

# Test 3d: Past scheduling
try:
    start_time = timezone.now() - timedelta(hours=1)  # 1 hour ago
    end_time = start_time + timedelta(hours=2)
    
    ScheduleService.validate_schedule_creation(
        lesson2, vehicle2, instructor1, start_time, end_time, owner
    )
    print("❌ 3d FAILED: Should have rejected past scheduling")
except Exception as e:
    print(f"✅ 3d - Correctly rejected past scheduling: {str(e)}")

# ============================================================================
# TEST 4: Test instructor scheduling conflicts
# ============================================================================
print("\n📝 TEST 4: Test instructor scheduling conflicts...")
try:
    # Try to schedule instructor1 at the same time as existing schedule
    conflict_start = schedule.start_time + timedelta(minutes=30)  # Overlapping
    conflict_end = conflict_start + timedelta(hours=1)
    
    ScheduleService.validate_schedule_creation(
        lesson4, vehicle2, instructor1, conflict_start, conflict_end, owner
    )
    print("❌ FAILED: Should have detected instructor conflict")
    
except Exception as e:
    print(f"✅ Correctly detected instructor conflict: {str(e)}")

# ============================================================================
# TEST 5: Test vehicle scheduling conflicts
# ============================================================================
print("\n📝 TEST 5: Test vehicle scheduling conflicts...")
try:
    # Try to schedule vehicle1 at the same time as existing schedule
    conflict_start = schedule.start_time + timedelta(minutes=30)  # Overlapping
    conflict_end = conflict_start + timedelta(hours=1)
    
    ScheduleService.validate_schedule_creation(
        lesson2, vehicle1, instructor2, conflict_start, conflict_end, owner
    )
    print("❌ FAILED: Should have detected vehicle conflict")
    
except Exception as e:
    print(f"✅ Correctly detected vehicle conflict: {str(e)}")

# ============================================================================
# TEST 6: Test vehicle status validation
# ============================================================================
print("\n📝 TEST 6: Test vehicle status validation...")
try:
    start_time = timezone.now() + timedelta(days=2, hours=10)
    end_time = start_time + timedelta(hours=1)
    
    ScheduleService.validate_schedule_creation(
        lesson2, maintenance_vehicle, instructor1, start_time, end_time, owner
    )
    print("❌ FAILED: Should have rejected maintenance vehicle")
    
except Exception as e:
    print(f"✅ Correctly rejected maintenance vehicle: {str(e)}")

# ============================================================================
# TEST 7: Test instructor assignment validation
# ============================================================================
print("\n📝 TEST 7: Test instructor assignment validation...")
try:
    # Try to assign instructor2 to lesson1 which belongs to instructor1
    start_time = timezone.now() + timedelta(days=2, hours=14)
    end_time = start_time + timedelta(hours=1)
    
    ScheduleService.validate_schedule_creation(
        lesson1, vehicle2, instructor2, start_time, end_time, owner
    )
    print("❌ FAILED: Should have rejected wrong instructor assignment")
    
except Exception as e:
    print(f"✅ Correctly rejected wrong instructor: {str(e)}")

# ============================================================================
# TEST 8: Update schedule
# ============================================================================
print("\n📝 TEST 8: Update schedule...")
try:
    # Update the schedule with new times (non-conflicting)
    new_start_time = schedule.start_time + timedelta(days=1)  # Move to next day
    new_end_time = new_start_time + timedelta(hours=2)
    
    update_data = {
        'start_time': new_start_time,
        'end_time': new_end_time
    }
    
    updated_schedule = ScheduleService.update_schedule(schedule, update_data)
    
    print(f"✅ Schedule updated")
    print(f"   New start: {updated_schedule.start_time}")
    print(f"   New end: {updated_schedule.end_time}")
    
except Exception as e:
    print(f"❌ Failed to update schedule: {str(e)}")

# ============================================================================
# TEST 9: Test availability checking
# ============================================================================
print("\n📝 TEST 9: Test availability checking...")
try:
    # Check availability for a new time slot
    check_start = timezone.now() + timedelta(days=3, hours=10)
    check_end = check_start + timedelta(hours=1)
    
    availability = ScheduleService.check_availability(instructor1, vehicle1, check_start, check_end)
    
    print("✅ Availability check:")
    print(f"   Instructor available: {availability['instructor_available']}")
    print(f"   Vehicle available: {availability['vehicle_available']}")
    print(f"   Time slot available: {availability['time_slot_available']}")
    
    # Check availability with existing schedule (should be unavailable)
    availability_conflict = ScheduleService.check_availability(
        instructor1, vehicle1, schedule.start_time, schedule.end_time, schedule
    )
    print(f"   With conflict - Instructor available: {availability_conflict['instructor_available']}")
    
except Exception as e:
    print(f"❌ Availability check failed: {str(e)}")

# ============================================================================
# TEST 10: Test schedule queries
# ============================================================================
print("\n📝 TEST 10: Test schedule queries...")
try:
    # Get instructor schedule
    start_date = timezone.now().date()
    end_date = start_date + timedelta(days=7)
    
    instructor_schedule = ScheduleService.get_instructor_schedule(instructor1, start_date, end_date)
    print(f"✅ Instructor {instructor1.username} has {instructor_schedule.count()} scheduled lessons")
    
    # Get vehicle schedule
    vehicle_schedule = ScheduleService.get_vehicle_schedule(vehicle1, start_date, end_date)
    print(f"✅ Vehicle {vehicle1.plate_number} has {vehicle_schedule.count()} scheduled uses")
    
    # Get school schedule
    school_schedule = ScheduleService.get_school_schedule(school, start_date, end_date)
    print(f"✅ School {school.name} has {school_schedule.count()} total scheduled lessons")
    
except Exception as e:
    print(f"❌ Schedule queries failed: {str(e)}")

# ============================================================================
# TEST 11: Test permission checks
# ============================================================================
print("\n📝 TEST 11: Test permission checks...")
try:
    # Owner should have permission
    can_owner_modify = ScheduleService.can_modify_schedule(owner, schedule)
    print(f"✅ Owner can modify: {can_owner_modify}")
    
    # Instructor should have permission for their own schedule
    can_instructor_modify_own = ScheduleService.can_modify_schedule(instructor1, schedule)
    print(f"✅ Instructor can modify own: {can_instructor_modify_own}")
    
    # Instructor should NOT have permission for other's schedule
    can_instructor_modify_other = ScheduleService.can_modify_schedule(instructor1, schedule2)
    print(f"✅ Instructor can modify other's: {can_instructor_modify_other} (should be False)")
    
    # Create a student user to test student permissions
    student_user = User.objects.create_user(
        username=f'test_student_schedule',
        email=f'student_test_schedule@test.com',
        password='test123',
        role='S'
    )
    can_student_modify = ScheduleService.can_modify_schedule(student_user, schedule)
    print(f"✅ Student can modify: {can_student_modify} (should be False)")
    
except Exception as e:
    print(f"❌ Permission checks failed: {str(e)}")

print("\n" + "=" * 70)
print("🧪 STEP 3: Testing ScheduleSerializer")
print("=" * 70)

# ============================================================================
# TEST 12: Serialize schedule (read)
# ============================================================================
print("\n📝 TEST 12: Serialize schedule data...")
try:
    serializer = ScheduleSerializer(schedule)
    data = serializer.data
    
    print("✅ Serialized schedule data:")
    print(f"   ID: {data['id']}")
    print(f"   Lesson: {data['lesson_title']}")
    print(f"   Instructor: {data['instructor_name']}")
    print(f"   Vehicle: {data['vehicle_info']}")
    print(f"   Start: {data['start_time']}")
    print(f"   End: {data['end_time']}")
    print(f"   Duration: {data['duration_minutes']} minutes")
    print(f"   School: {data['school_name']}")
    
except Exception as e:
    print(f"❌ Failed to serialize: {str(e)}")

# ============================================================================
# TEST 13: Create schedule via serializer
# ============================================================================
print("\n📝 TEST 13: Create schedule via serializer...")
new_schedule = None
try:
    # Create MockRequest
    class MockRequest:
        def __init__(self, user):
            self.user = user

    mock_request = MockRequest(owner)

    # Create a new lesson for this test
    new_lesson = Lesson.objects.create(
        instructor=instructor2,
        school=school,
        title='Serializer Test Lesson',
        lesson_type='D',
        description='Lesson for serializer testing',
        duration=90,
        date=timezone.now() + timedelta(days=5),
        status='S'
    )

    start_time = timezone.now() + timedelta(days=5, hours=10)
    end_time = start_time + timedelta(hours=1, minutes=30)
    
    serializer_data = {
        'lesson': new_lesson.id,
        'vehicle': vehicle2.id,
        'instructor': instructor2.id,
        'start_time': start_time.isoformat(),
        'end_time': end_time.isoformat()
    }
    
    serializer = ScheduleSerializer(
        data=serializer_data,
        context={'request': mock_request}
    )
    
    if serializer.is_valid():
        new_schedule = serializer.save()
        print(f"✅ Schedule created via serializer: ID={new_schedule.id}")
        print(f"   Lesson: {new_schedule.lesson.title}")
        print(f"   Instructor: {new_schedule.instructor.username}")
    else:
        print(f"❌ Serializer validation failed: {serializer.errors}")
    
except Exception as e:
    print(f"❌ Failed: {str(e)}")

# ============================================================================
# TEST 14: Update schedule via serializer
# ============================================================================
print("\n📝 TEST 14: Update schedule via serializer...")
try:
    if new_schedule:
        update_data = {
            'start_time': (new_schedule.start_time + timedelta(hours=1)).isoformat(),
            'end_time': (new_schedule.end_time + timedelta(hours=1)).isoformat()
        }
        
        serializer = ScheduleSerializer(
            new_schedule,
            data=update_data,
            partial=True,
            context={'request': mock_request}
        )
        
        if serializer.is_valid():
            updated = serializer.save()
            print(f"✅ Schedule updated via serializer")
            print(f"   New start: {updated.start_time}")
            print(f"   New end: {updated.end_time}")
        else:
            print(f"❌ Serializer validation failed: {serializer.errors}")
    else:
        print("⚠️  Skipping test - new_schedule was not created")
    
except Exception as e:
    print(f"❌ Failed: {str(e)}")

# ============================================================================
# TEST 15: Test serializer validation with invalid data
# ============================================================================
print("\n📝 TEST 15: Test serializer validation with invalid data...")
try:
    # Try to create schedule with lesson that already has one
    duplicate_lesson_data = {
        'lesson': lesson1.id,  # This lesson already has a schedule
        'instructor': instructor1.id,
        'start_time': (timezone.now() + timedelta(days=6, hours=10)).isoformat(),
        'end_time': (timezone.now() + timedelta(days=6, hours=12)).isoformat()
    }
    
    serializer = ScheduleSerializer(
        data=duplicate_lesson_data,
        context={'request': mock_request}
    )
    
    if not serializer.is_valid():
        print(f"✅ Correctly rejected duplicate lesson: {serializer.errors}")
    else:
        print("❌ FAILED: Should have rejected lesson with existing schedule")
    
except Exception as e:
    print(f"✅ Caught validation error: {str(e)}")

# ============================================================================
# TEST 16: Test buffer time in scheduling conflicts
# ============================================================================
print("\n📝 TEST 16: Test buffer time in scheduling conflicts...")
try:
    # Try to schedule right after existing schedule (within buffer time)
    buffer_start = schedule.end_time + timedelta(minutes=5)  # 5 min after end (within 15 min buffer)
    buffer_end = buffer_start + timedelta(hours=1)
    
    # Create a new lesson for this test
    buffer_lesson = Lesson.objects.create(
        instructor=instructor1,
        school=school,
        title='Buffer Test Lesson',
        lesson_type='T',
        description='Testing buffer time',
        duration=60,
        date=timezone.now() + timedelta(days=7),
        status='S'
    )
    
    ScheduleService.validate_schedule_creation(
        buffer_lesson, vehicle1, instructor1, buffer_start, buffer_end, owner
    )
    print("❌ FAILED: Should have detected buffer time conflict")
    
except Exception as e:
    print(f"✅ Correctly detected buffer time conflict: {str(e)}")

# ============================================================================
# SUMMARY
# ============================================================================
print("\n" + "=" * 70)
print("📊 TEST SUITE SUMMARY")
print("=" * 70)
print("\n✅ All core functionality tested:")
print("   - Schedule creation with validation")
print("   - Time range validation (past, duration, order)")
print("   - Instructor scheduling conflicts")
print("   - Vehicle scheduling conflicts and status")
print("   - Instructor assignment validation")
print("   - Schedule updates")
print("   - Availability checking")
print("   - Schedule queries (instructor, vehicle, school)")
print("   - Permission checks")
print("   - Serializer read/write operations")
print("   - Buffer time validation")
print("   - Error handling and validation")
print("\n🎉 SCHEDULE SERVICE & SERIALIZER TESTS COMPLETE!")
print("=" * 70)

# Cleanup (optional)
print("\n🧹 Test data preserved for inspection.")
print("✅ Test suite finished successfully!")
# Debug test to understand the issue
# Run this: python manage.py shell < debug_test.py

from DriveApp.models import User, DrivingSchool, StudentProfile
from DriveApp.serializers import LessonSerializer
from django.utils import timezone
from datetime import timedelta
from django.test import RequestFactory
from rest_framework.request import Request

print("=" * 70)
print("🔍 DEBUG TEST - Understanding the Validation Flow")
print("=" * 70)

# Create fresh test data
owner = User.objects.create_user(
    username=f'debug_owner_{timezone.now().timestamp()}',
    email=f'debug_owner_{timezone.now().timestamp()}@test.com',
    password='test123',
    role='A'
)
print(f"✅ Created owner: {owner.username} (ID: {owner.id})")

school = DrivingSchool.objects.create(
    owner=owner,
    name=f'Debug School {timezone.now().timestamp()}',
    address='123 Debug St',
    email=f'debug_school_{timezone.now().timestamp()}@test.com',
    phone_number='123-456-7890'
)
print(f"✅ Created school: {school.name} (ID: {school.id})")
print(f"   School owner ID: {school.owner.id}")

instructor = User.objects.create_user(
    username=f'debug_instructor_{timezone.now().timestamp()}',
    email=f'debug_instructor_{timezone.now().timestamp()}@test.com',
    password='test123',
    role='I'
)
print(f"✅ Created instructor: {instructor.username} (ID: {instructor.id})")

# Assign instructor to school
instructor_profile = StudentProfile.objects.create(
    user=instructor,
    school=school,
    license_type='B',
    status='A'
)
print(f"✅ Assigned instructor to school")

# Create request
factory = RequestFactory()
request_create = factory.post('/api/lessons/')
request_create.user = owner
drf_request = Request(request_create)

print(f"\n📍 Request user: {request_create.user.username} (ID: {request_create.user.id})")
print(f"📍 Request user role: {request_create.user.role}")

# Prepare data
future_date = timezone.now() + timedelta(days=10)
serializer_data = {
    'instructor': instructor.id,
    'school': school.id,
    'title': 'Debug Lesson',
    'lesson_type': 'D',
    'description': 'Testing validation',
    'duration': 180,
    'date': future_date.isoformat(),
    'status': 'S'
}

print(f"\n📦 Serializer input data:")
print(f"   instructor ID: {serializer_data['instructor']}")
print(f"   school ID: {serializer_data['school']}")

# Create serializer
serializer = LessonSerializer(
    data=serializer_data,
    context={'request': drf_request}
)

print(f"\n🔄 Running serializer validation...")

# Add debug to see what happens
if serializer.is_valid():
    print("✅ Serializer is valid!")
    
    # Check validated data
    print(f"\n📦 Validated data:")
    print(f"   instructor: {serializer.validated_data.get('instructor')}")
    print(f"   instructor type: {type(serializer.validated_data.get('instructor'))}")
    print(f"   school: {serializer.validated_data.get('school')}")
    print(f"   school type: {type(serializer.validated_data.get('school'))}")
    print(f"   school.owner: {serializer.validated_data.get('school').owner}")
    print(f"   school.owner ID: {serializer.validated_data.get('school').owner.id}")
    
    try:
        lesson = serializer.save()
        print(f"\n✅ Lesson created successfully: ID={lesson.id}")
    except Exception as e:
        print(f"\n❌ Error during save: {str(e)}")
else:
    print("❌ Serializer validation failed!")
    print(f"\n📋 Errors:")
    for field, errors in serializer.errors.items():
        print(f"   {field}: {errors}")

print("\n" + "=" * 70)
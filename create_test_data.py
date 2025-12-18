# Test/simple_data.py
import os
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Drive.settings')
django.setup()

from DriveApp.models import User, DrivingSchool, StudentProfile
from django.utils import timezone
from datetime import timedelta

def create_simple_data():
    print("📝 Creating simple test data...")
    
    # Calculate dates (2 weeks ago)
    two_weeks_ago = timezone.now() - timedelta(days=14)
    one_week_ago = timezone.now() - timedelta(days=7)
    
    # 1. Create admin
    admin = User.objects.create_user(
        username='admin3',
        email='admin3@school.com',
        password='admin1243',
        role='A',
        first_name='Admin',
        last_name='User'
    )
    print("✅ Created admin")
    
    # 2. Create instructor
    instructor = User.objects.create_user(
        username='instructor4',
        email='instructor4@school.com',
        password='instructor123',
        role='I',
        first_name='Ahmed',
        last_name='Instructor'
    )
    print("✅ Created instructor")
    
    # 3. Create Othmane (your email) - enrolled 2 weeks ago
    othmane1 = User.objects.create_user(
        username='othmane3',
        email='othmanejamili0@gmail.com',
        password='student123',
        role='S',
        first_name='Othmane',
        last_name='Jamili'
    )
    print("✅ Created Othmane (enrolled 2 weeks ago)")
    
    # 4. Create school
    school1 = DrivingSchool.objects.create(
        owner=admin,
        name='Casablanca Driving School',
        address='123 Main Street, Casablanca',
        email='contact3@casablanca-school.ma',
        phone_number='+212522000001'
    )
    print("✅ Created school")
    
    # 5. Create student profile for Othmane with 2-week progress
    student_profile = StudentProfile.objects.create(
        user=othmane1,
        school=school1,
        license_type='C',
        progress_theory=65.0,  # Good progress after 2 weeks
        progress_driving=40.0, # Started driving 1 week ago
        total_hours_theory=18, # About 9 hours per week
        total_hours_driving=8, # Started driving practice later
        status='A',
        theory_start_date=two_weeks_ago.date(),  # Started 2 weeks ago
        driving_start_date=one_week_ago.date()   # Started driving 1 week ago
    )
    print("✅ Created student profile with 2-week progress")
    
    # 6. Print summary
    print(f"\n🎉 Data created successfully!")
    print(f"👥 Total users: {User.objects.count()}")
    print(f"🏫 Total schools: {DrivingSchool.objects.count()}")
    print(f"🎓 Total students: {StudentProfile.objects.count()}")
    
    print(f"\n📅 Othmane's enrollment details:")
    print(f"   Enrolled: {two_weeks_ago.strftime('%Y-%m-%d')} (2 weeks ago)")
    print(f"   Started driving: {one_week_ago.strftime('%Y-%m-%d')} (1 week ago)")
    print(f"   Theory progress: 65%")
    print(f"   Driving progress: 40%")
    
    print(f"\n🔑 Login as Othmane:")
    print(f"   Email: jamiliothmane5@gmail.com")
    print(f"   Password: student123")

if __name__ == '__main__':
    create_simple_data()
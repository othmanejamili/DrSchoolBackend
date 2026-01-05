# tests/test_dashboard_views.py

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from datetime import datetime, timedelta, date
import json

from DriveApp.models import (
    User, DrivingSchool, StudentProfile, Lesson, 
    Attendance, Feedback, SchoolAnalytics, Achievement,
    Vehicle, Schedule, CommunicationTemplate, AutomatedMessage
)


class DashboardViewSetTestCase(APITestCase):
    """Comprehensive tests for DashboardViewSet"""

    def setUp(self):
        """Set up test data for dashboard tests"""
        
        # Create users with different roles
        self.platform_admin = User.objects.create_user(
            username='platform_admin',
            email='admin@platform.com',
            password='AdminPass123!',
            role='A',
            is_staff=True,
            first_name='Platform',
            last_name='Admin'
        )
        
        self.school_owner1 = User.objects.create_user(
            username='school_owner1',
            email='owner1@school.com',
            password='testpass123',
            role='A',
            first_name='School',
            last_name='Owner'
        )
        
        self.school_owner2 = User.objects.create_user(
            username='school_owner2',
            email='owner2@school.com',
            password='testpass123',
            role='A',
        )
        
        self.instructor1 = User.objects.create_user(
            username='instructor1',
            email='instructor1@school.com',
            password='testpass123',
            role='I',
            first_name='John',
            last_name='Instructor'
        )
        
        self.instructor2 = User.objects.create_user(
            username='instructor2',
            email='instructor2@school.com',
            password='testpass123',
            role='I',
        )
        
        self.student1 = User.objects.create_user(
            username='student1',
            email='student1@school.com',
            password='testpass123',
            role='S',
            first_name='Alice',
            last_name='Student'
        )
        
        self.student2 = User.objects.create_user(
            username='student2',
            email='student2@school.com',
            password='testpass123',
            role='S',
            first_name='Bob',
            last_name='Learner'
        )
        
        # Create driving schools
        self.school1 = DrivingSchool.objects.create(
            owner=self.school_owner1,
            name='Drive Safe Academy',
            email='school1@test.com',
            address='123 Main St, City',
            phone_number='+1234567890',
            created_at=timezone.now() - timedelta(days=60)
        )
        
        self.school2 = DrivingSchool.objects.create(
            owner=self.school_owner2,
            name='Pro Driving School',
            email='school2@test.com',
            address='456 Oak Ave, Town',
            phone_number='+9876543210',
            created_at=timezone.now() - timedelta(days=45)
        )
        
        # Create student profiles
        self.instructor1_profile = StudentProfile.objects.create(
            user=self.instructor1,
            school=self.school1,
            status='A',
            joined_at=timezone.now() - timedelta(days=30)
        )
        
        self.instructor2_profile = StudentProfile.objects.create(
            user=self.instructor2,
            school=self.school1,
            status='A',
            joined_at=timezone.now() - timedelta(days=25)
        )
        
        self.student1_profile = StudentProfile.objects.create(
            user=self.student1,
            school=self.school1,
            status='A',
            joined_at=timezone.now() - timedelta(days=15),
            progress_theory=75.0,
            progress_driving=60.0,
            total_hours_theory=30.0,
            total_hours_driving=20.0,
            license_type='C'
        )
        
        self.student2_profile = StudentProfile.objects.create(
            user=self.student2,
            school=self.school1,
            status='C',  # Completed
            joined_at=timezone.now() - timedelta(days=90),
            completion_date=timezone.now().date() - timedelta(days=10),
            progress_theory=100.0,
            progress_driving=100.0,
            total_hours_theory=50.0,
            total_hours_driving=40.0,
            license_type='C'
        )
        
        self.student3_profile = StudentProfile.objects.create(
            user=User.objects.create_user(
                username='student3',
                email='student3@school.com',
                password='testpass123',
                role='S'
            ),
            school=self.school2,
            status='A',
            joined_at=timezone.now() - timedelta(days=20),
            progress_theory=40.0,
            progress_driving=30.0
        )
        
        # Create lessons
        self.today = timezone.now().date()
        self.now = timezone.now()
        
        # Past lessons
        self.lesson1 = Lesson.objects.create(
            title='Basic Driving Lesson',
            instructor=self.instructor1,
            school=self.school1,
            lesson_type='D',
            description='Basic driving techniques',
            duration=60,
            date=timezone.make_aware(datetime.combine(self.today - timedelta(days=5), datetime.min.time().replace(hour=10))),
            status='C'  # Completed
        )
        
        self.lesson2 = Lesson.objects.create(
            title='Theory Class',
            instructor=self.instructor1,
            school=self.school1,
            lesson_type='T',
            description='Traffic rules and regulations',
            duration=90,
            date=timezone.make_aware(datetime.combine(self.today - timedelta(days=3), datetime.min.time().replace(hour=14))),
            status='C'
        )
        
        self.lesson3 = Lesson.objects.create(
            title='Advanced Driving',
            instructor=self.instructor2,
            school=self.school1,
            lesson_type='D',
            duration=120,
            date=timezone.make_aware(datetime.combine(self.today - timedelta(days=2), datetime.min.time().replace(hour=9))),
            status='C'
        )
        
        self.lesson4 = Lesson.objects.create(
            title='School 2 Lesson',
            instructor=self.instructor2,
            school=self.school2,
            lesson_type='D',
            duration=60,
            date=timezone.make_aware(datetime.combine(self.today - timedelta(days=1), datetime.min.time().replace(hour=11))),
            status='C'
        )
        
        # Today's lessons
        self.lesson5 = Lesson.objects.create(
            title='Morning Lesson Today',
            instructor=self.instructor1,
            school=self.school1,
            lesson_type='D',
            duration=60,
            date=timezone.make_aware(datetime.combine(self.today, datetime.min.time().replace(hour=9))),
            status='C'
        )
        
        self.lesson6 = Lesson.objects.create(
            title='Afternoon Lesson Today',
            instructor=self.instructor1,
            school=self.school1,
            lesson_type='T',
            duration=90,
            date=timezone.make_aware(datetime.combine(self.today, datetime.min.time().replace(hour=14))),
            status='S'  # Scheduled
        )
        
        # Future lesson
        self.lesson7 = Lesson.objects.create(
            title='Future Lesson',
            instructor=self.instructor1,
            school=self.school1,
            lesson_type='D',
            duration=60,
            date=self.now + timedelta(days=1),
            status='S'  # Scheduled
        )
        
        # Create attendance records
        self.attendance1 = Attendance.objects.create(
            student=self.student1_profile,
            lesson=self.lesson1,
            presence=True,
            hours_completed=1.0,
            notes='Good progress',
            created_at=timezone.now() - timedelta(days=5)
        )
        
        self.attendance2 = Attendance.objects.create(
            student=self.student1_profile,
            lesson=self.lesson2,
            presence=True,
            hours_completed=1.5,
            notes='Excellent participation',
            created_at=timezone.now() - timedelta(days=3)
        )
        
        self.attendance3 = Attendance.objects.create(
            student=self.student1_profile,
            lesson=self.lesson3,
            presence=False,
            hours_completed=0,
            notes='Absent',
            created_at=timezone.now() - timedelta(days=2)
        )
        
        self.attendance4 = Attendance.objects.create(
            student=self.student1_profile,
            lesson=self.lesson5,
            presence=True,
            hours_completed=1.0,
            notes='Attended',
            created_at=self.now - timedelta(hours=3)
        )
        
        self.attendance5 = Attendance.objects.create(
            student=self.student2_profile,
            lesson=self.lesson1,
            presence=True,
            hours_completed=1.0,
            notes='Completed',
            created_at=timezone.now() - timedelta(days=5)
        )
        
        # Create feedback
        self.feedback1 = Feedback.objects.create(
            student=self.student1_profile,
            lesson=self.lesson1,
            rating=5,
            comment='Great lesson! The instructor was very patient.',
            created_at=timezone.now() - timedelta(days=5)
        )
        
        self.feedback2 = Feedback.objects.create(
            student=self.student1_profile,
            lesson=self.lesson2,
            rating=4,
            comment='Very informative, learned a lot about traffic rules.',
            created_at=timezone.now() - timedelta(days=3)
        )
        
        self.feedback3 = Feedback.objects.create(
            student=self.student2_profile,
            lesson=self.lesson1,
            rating=5,
            comment='Excellent instructor, very clear explanations.',
            created_at=timezone.now() - timedelta(days=5)
        )
        
        self.feedback4 = Feedback.objects.create(
            student=self.student3_profile,
            lesson=self.lesson4,
            rating=3,
            comment='Average lesson, could be more engaging.',
            created_at=timezone.now() - timedelta(days=1)
        )
        
        # Create achievements
        self.achievement1 = Achievement.objects.create(
            student=self.student1_profile,
            type='first_lesson',
            title='First Lesson Completed',
            description='Completed your first driving lesson',
            icon='🎯',
            points=10,
            earned_at=timezone.now() - timedelta(days=5)
        )
        
        self.achievement2 = Achievement.objects.create(
            student=self.student1_profile,
            type='theory_master',
            title='Theory Master',
            description='Completed 30 hours of theory',
            icon='📚',
            points=20,
            earned_at=timezone.now() - timedelta(days=2)
        )
        
        self.achievement3 = Achievement.objects.create(
            student=self.student2_profile,
            type='theory_master',
            title='Theory Master',
            description='Completed 50 hours of theory',
            icon='📚',
            points=25,
            earned_at=timezone.now() - timedelta(days=20)
        )
        
        # Create school analytics records
        self.yesterday = self.today - timedelta(days=1)
        self.last_week = self.today - timedelta(days=7)
        self.last_month = self.today - timedelta(days=30)
        
        # School1 analytics
        self.analytics_today_s1 = SchoolAnalytics.objects.create(
            school=self.school1,
            date=self.today,
            total_students=12,
            active_students=10,
            new_students=2,
            completion_rate=75.5,
            revenue=2500.00,
            average_rating=4.5,
            lessons_completed=45,
            instructor_utilization=85.0
        )
        
        self.analytics_yesterday_s1 = SchoolAnalytics.objects.create(
            school=self.school1,
            date=self.yesterday,
            total_students=11,
            active_students=9,
            new_students=1,
            completion_rate=74.0,
            revenue=2000.00,
            average_rating=4.3,
            lessons_completed=42,
            instructor_utilization=80.0
        )
        
        self.analytics_last_week_s1 = SchoolAnalytics.objects.create(
            school=self.school1,
            date=self.last_week,
            total_students=10,
            active_students=8,
            new_students=0,
            completion_rate=70.0,
            revenue=1500.00,
            average_rating=4.0,
            lessons_completed=35,
            instructor_utilization=75.0
        )
        
        self.analytics_last_month_s1 = SchoolAnalytics.objects.create(
            school=self.school1,
            date=self.last_month,
            total_students=8,
            active_students=6,
            new_students=1,
            completion_rate=65.0,
            revenue=1000.00,
            average_rating=3.8,
            lessons_completed=25,
            instructor_utilization=70.0
        )
        
        # School2 analytics
        self.analytics_today_s2 = SchoolAnalytics.objects.create(
            school=self.school2,
            date=self.today,
            total_students=5,
            active_students=4,
            new_students=1,
            completion_rate=60.0,
            revenue=1200.00,
            average_rating=3.8,
            lessons_completed=20,
            instructor_utilization=65.0
        )
        
        # Create vehicle
        self.vehicle = Vehicle.objects.create(
            school=self.school1,
            plate_number='ABC123',
            make='Toyota',
            model='Corolla',
            year=2022,
            transmission='automatic',
            status='available'
        )
        
        # Create schedule
        self.schedule = Schedule.objects.create(
            lesson=self.lesson1,
            vehicle=self.vehicle,
            instructor=self.instructor1,
            start_time=self.lesson1.date,
            end_time=self.lesson1.date + timedelta(hours=1)
        )
        
        # Create communication template
        self.template = CommunicationTemplate.objects.create(
            school=self.school1,
            name='Progress Update',
            template_type='progress_update',
            subject='Your progress update',
            body='Hello {student_name}, your progress is {progress}%',
            is_active=True
        )
        
        # Create automated messages
        self.message_pending = AutomatedMessage.objects.create(
            student=self.student1_profile,
            template=self.template,
            scheduled_for=self.now - timedelta(hours=1),  # Overdue
            status='pending'
        )
        
        self.message_sent = AutomatedMessage.objects.create(
            student=self.student1_profile,
            template=self.template,
            scheduled_for=self.now - timedelta(days=1),
            sent_at=self.now - timedelta(days=1),
            status='sent'
        )
        
        self.message_failed = AutomatedMessage.objects.create(
            student=self.student1_profile,
            template=self.template,
            scheduled_for=self.now - timedelta(days=2),
            sent_at=self.now - timedelta(days=2),
            status='failed',
            delivery_error='Network error'
        )
        
        # API client
        self.client = APIClient()
        
        # URLs
        self.overview_url = reverse('dashboard-overview')
        self.platform_admin_url = reverse('dashboard-platform_admin')
        self.school_owner_url = reverse('dashboard-school_owner')
        self.instructor_url = reverse('dashboard-instructor')
        self.student_url = reverse('dashboard-student')
        self.quick_stats_url = reverse('dashboard-quick_stats')
        self.notifications_url = reverse('dashboard-notifications')

    def tearDown(self):
        """Clean up test data"""
        AutomatedMessage.objects.all().delete()
        CommunicationTemplate.objects.all().delete()
        Schedule.objects.all().delete()
        Vehicle.objects.all().delete()
        SchoolAnalytics.objects.all().delete()
        Achievement.objects.all().delete()
        Feedback.objects.all().delete()
        Attendance.objects.all().delete()
        Lesson.objects.all().delete()
        StudentProfile.objects.all().delete()
        DrivingSchool.objects.all().delete()
        User.objects.all().delete()

    # ==================== AUTHENTICATION TESTS ====================

    def test_unauthenticated_access_denied(self):
        """Test that unauthenticated users cannot access dashboard"""
        for url in [self.overview_url, self.platform_admin_url, self.school_owner_url, 
                   self.instructor_url, self.student_url, self.quick_stats_url, 
                   self.notifications_url]:
            response = self.client.get(url)
            self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    # ==================== OVERVIEW ENDPOINT TESTS ====================

    def test_overview_platform_admin(self):
        """Test overview endpoint for platform admin"""
        self.client.force_authenticate(user=self.platform_admin)
        
        response = self.client.get(self.overview_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['dashboard_type'], 'platform_admin')
        self.assertIn('system_overview', response.data)
        self.assertIn('user', response.data)
        self.assertEqual(response.data['user']['role'], 'Platform Administrator')

    def test_overview_school_owner(self):
        """Test overview endpoint for school owner"""
        self.client.force_authenticate(user=self.school_owner1)
        
        response = self.client.get(self.overview_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['dashboard_type'], 'school_owner')
        self.assertEqual(response.data['user']['role'], 'School Owner')
        self.assertIn('overview', response.data)
        self.assertIn('schools', response.data)

    def test_overview_instructor(self):
        """Test overview endpoint for instructor"""
        self.client.force_authenticate(user=self.instructor1)
        
        response = self.client.get(self.overview_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['dashboard_type'], 'instructor')
        self.assertEqual(response.data['user']['role'], 'Instructor')
        self.assertIn('school', response.data)
        self.assertIn('today', response.data)

    def test_overview_student(self):
        """Test overview endpoint for student"""
        self.client.force_authenticate(user=self.student1)
        
        response = self.client.get(self.overview_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['dashboard_type'], 'student')
        self.assertEqual(response.data['user']['role'], 'Student')
        self.assertIn('progress_summary', response.data)
        self.assertIn('attendance', response.data)

    # ==================== PLATFORM ADMIN DASHBOARD TESTS ====================

    def test_platform_admin_dashboard_access(self):
        """Test platform admin dashboard access"""
        self.client.force_authenticate(user=self.platform_admin)
        
        response = self.client.get(self.platform_admin_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['dashboard_type'], 'platform_admin')
        
        # Check system overview
        overview = response.data['system_overview']
        self.assertIn('total_schools', overview)
        self.assertEqual(overview['total_schools'], 2)
        self.assertIn('total_students', overview)
        self.assertIn('active_students', overview)
        self.assertIn('total_instructors', overview)
        
        # Check today's snapshot
        today_snapshot = response.data['today_snapshot']
        self.assertIn('total_lessons', today_snapshot)
        self.assertIn('completed_lessons', today_snapshot)
        self.assertIn('completion_rate', today_snapshot)
        
        # Check this week stats
        this_week = response.data['this_week']
        self.assertIn('total_lessons', this_week)
        self.assertIn('completed_lessons', this_week)
        self.assertIn('completion_rate', this_week)
        self.assertIn('total_revenue', this_week)
        
        # Check top performing schools
        self.assertIn('top_performing_schools', response.data)
        
        # Check platform metrics
        platform_metrics = response.data['platform_metrics']
        self.assertIn('average_rating', platform_metrics)
        self.assertIn('pending_messages', platform_metrics)
        self.assertIn('failed_messages', platform_metrics)
        
        # Check recent feedback
        self.assertIn('recent_feedback', response.data)

    def test_platform_admin_dashboard_wrong_role(self):
        """Test that non-platform admins cannot access platform admin dashboard"""
        # School owner
        self.client.force_authenticate(user=self.school_owner1)
        response = self.client.get(self.platform_admin_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        
        # Instructor
        self.client.force_authenticate(user=self.instructor1)
        response = self.client.get(self.platform_admin_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        
        # Student
        self.client.force_authenticate(user=self.student1)
        response = self.client.get(self.platform_admin_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    # ==================== SCHOOL OWNER DASHBOARD TESTS ====================

    def test_school_owner_dashboard_all_schools(self):
        """Test school owner dashboard showing all schools"""
        self.client.force_authenticate(user=self.school_owner1)
        
        response = self.client.get(self.school_owner_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['dashboard_type'], 'school_owner')
        
        # Check overview
        overview = response.data['overview']
        self.assertIn('total_schools', overview)
        self.assertEqual(overview['total_schools'], 1)  # Only school1
        self.assertIn('total_students', overview)
        self.assertIn('active_students', overview)
        self.assertIn('total_instructors', overview)
        
        # Check this week performance
        performance = response.data['this_week_performance']
        self.assertIn('total_lessons', performance)
        self.assertIn('completed_lessons', performance)
        self.assertIn('completion_rate', performance)
        self.assertIn('total_revenue', performance)
        self.assertIn('avg_completion_rate', performance)
        
        # Check today's stats
        self.assertIn('today', response.data)
        
        # Check schools list
        schools = response.data['schools']
        self.assertEqual(len(schools), 1)
        self.assertEqual(schools[0]['school_name'], 'Drive Safe Academy')
        
        # Check best performing school
        self.assertIn('best_performing_school', response.data)

    def test_school_owner_dashboard_single_school(self):
        """Test school owner dashboard for specific school"""
        self.client.force_authenticate(user=self.school_owner1)
        
        response = self.client.get(
            self.school_owner_url,
            {'school_id': self.school1.id}
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['dashboard_type'], 'single_school')
        self.assertEqual(response.data['school']['id'], self.school1.id)
        
        # Check current metrics
        metrics = response.data['current_metrics']
        self.assertIn('total_students', metrics)
        self.assertIn('active_students', metrics)
        self.assertIn('completed_students', metrics)
        self.assertIn('total_instructors', metrics)
        self.assertIn('completion_rate', metrics)
        self.assertIn('average_rating', metrics)
        
        # Check this week stats
        self.assertIn('this_week', response.data)
        
        # Check this month stats
        self.assertIn('this_month', response.data)
        
        # Check top students
        self.assertIn('top_students', response.data)
        
        # Check instructor performance
        self.assertIn('instructor_performance', response.data)

    def test_school_owner_dashboard_wrong_school(self):
        """Test school owner cannot access dashboard for another owner's school"""
        self.client.force_authenticate(user=self.school_owner1)
        
        response = self.client.get(
            self.school_owner_url,
            {'school_id': self.school2.id}
        )
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_school_owner_dashboard_wrong_role(self):
        """Test that non-school owners cannot access school owner dashboard"""
        # Instructor
        self.client.force_authenticate(user=self.instructor1)
        response = self.client.get(self.school_owner_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        
        # Student
        self.client.force_authenticate(user=self.student1)
        response = self.client.get(self.school_owner_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    # ==================== INSTRUCTOR DASHBOARD TESTS ====================

    def test_instructor_dashboard(self):
        """Test instructor dashboard"""
        self.client.force_authenticate(user=self.instructor1)
        
        response = self.client.get(self.instructor_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['dashboard_type'], 'instructor')
        
        # Check user info
        self.assertEqual(response.data['user']['name'], 'John Instructor')
        self.assertEqual(response.data['user']['role'], 'Instructor')
        
        # Check school info
        self.assertEqual(response.data['school']['id'], self.school1.id)
        self.assertEqual(response.data['school']['name'], 'Drive Safe Academy')
        
        # Check today's lessons
        today = response.data['today']
        self.assertIn('total_lessons', today)
        self.assertIn('completed', today)
        self.assertIn('upcoming', today)
        self.assertIn('lessons', today)
        
        # Check this week performance
        performance = response.data['this_week_performance']
        self.assertIn('total_lessons', performance)
        self.assertIn('completed_lessons', performance)
        self.assertIn('completion_rate', performance)
        self.assertIn('students_taught', performance)
        
        # Check upcoming lessons
        self.assertIn('upcoming_lessons', response.data)
        
        # Check performance metrics
        metrics = response.data['performance_metrics']
        self.assertIn('average_rating', metrics)
        self.assertIn('total_feedback', metrics)
        self.assertIn('attendance_rate', metrics)
        self.assertIn('total_students_taught', metrics)
        
        # Check recent feedback
        self.assertIn('recent_feedback', response.data)

    def test_instructor_dashboard_no_profile(self):
        """Test instructor dashboard without active profile"""
        # Create instructor without profile
        instructor_no_profile = User.objects.create_user(
            username='instructor_no_profile',
            email='no_profile@test.com',
            password='testpass123',
            role='I'
        )
        
        self.client.force_authenticate(user=instructor_no_profile)
        
        response = self.client.get(self.instructor_url)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)

    def test_instructor_dashboard_wrong_role(self):
        """Test that non-instructors cannot access instructor dashboard"""
        # Platform admin
        self.client.force_authenticate(user=self.platform_admin)
        response = self.client.get(self.instructor_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        
        # School owner
        self.client.force_authenticate(user=self.school_owner1)
        response = self.client.get(self.instructor_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        
        # Student
        self.client.force_authenticate(user=self.student1)
        response = self.client.get(self.instructor_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    # ==================== STUDENT DASHBOARD TESTS ====================

    def test_student_dashboard(self):
        """Test student dashboard"""
        self.client.force_authenticate(user=self.student1)
        
        response = self.client.get(self.student_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['dashboard_type'], 'student')
        
        # Check user info
        self.assertEqual(response.data['user']['name'], 'Alice Student')
        self.assertEqual(response.data['user']['role'], 'Student')
        
        # Check school info
        self.assertEqual(response.data['school']['id'], self.school1.id)
        self.assertEqual(response.data['school']['name'], 'Drive Safe Academy')
        
        # Check progress summary
        progress = response.data['progress_summary']
        self.assertIn('theory', progress)
        self.assertIn('driving', progress)
        self.assertIn('overall', progress)
        self.assertIn('completion_date', progress)
        self.assertIn('days_enrolled', progress)
        
        # Theory progress
        theory = progress['theory']
        self.assertEqual(theory['progress'], 75.0)
        self.assertEqual(theory['hours'], 30.0)
        self.assertEqual(theory['status'], 'In Progress')
        
        # Driving progress
        driving = progress['driving']
        self.assertEqual(driving['progress'], 60.0)
        self.assertEqual(driving['hours'], 20.0)
        self.assertEqual(driving['status'], 'In Progress')
        
        # Overall progress
        overall = progress['overall']
        self.assertEqual(overall['progress'], 67.5)  # (75 + 60) / 2
        self.assertEqual(overall['total_hours'], 50.0)  # 30 + 20
        self.assertEqual(overall['status'], 'Active')
        
        # Check attendance
        attendance = response.data['attendance']
        self.assertIn('total_lessons', attendance)
        self.assertIn('present', attendance)
        self.assertIn('absent', attendance)
        self.assertIn('attendance_rate', attendance)
        self.assertIn('recent_attendance', attendance)
        
        # Check achievements
        achievements = response.data['achievements']
        self.assertIn('total', achievements)
        self.assertIn('recent', achievements)
        self.assertEqual(achievements['total'], 2)
        
        # Check upcoming lessons
        self.assertIn('upcoming_lessons', response.data)
        
        # Check recent feedback
        self.assertIn('recent_feedback', response.data)
        
        # Check messages
        self.assertIn('messages', response.data)
        
        # Check milestones
        self.assertIn('milestones', response.data)
        
        # Check class position
        self.assertIn('class_position', response.data)
        
        # Check recommendations
        self.assertIn('recommendations', response.data)
        
        # Check quick actions
        self.assertIn('quick_actions', response.data)

    def test_student_dashboard_no_profile(self):
        """Test student dashboard without active profile"""
        # Create student without profile
        student_no_profile = User.objects.create_user(
            username='student_no_profile',
            email='no_profile@test.com',
            password='testpass123',
            role='S'
        )
        
        self.client.force_authenticate(user=student_no_profile)
        
        response = self.client.get(self.student_url)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)

    def test_student_dashboard_wrong_role(self):
        """Test that non-students cannot access student dashboard"""
        # Platform admin
        self.client.force_authenticate(user=self.platform_admin)
        response = self.client.get(self.student_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        
        # School owner
        self.client.force_authenticate(user=self.school_owner1)
        response = self.client.get(self.student_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        
        # Instructor
        self.client.force_authenticate(user=self.instructor1)
        response = self.client.get(self.student_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    # ==================== QUICK STATS TESTS ====================

    def test_quick_stats_platform_admin(self):
        """Test quick stats for platform admin"""
        self.client.force_authenticate(user=self.platform_admin)
        
        response = self.client.get(self.quick_stats_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['user_role'], 'A')
        
        stats = response.data['stats']
        self.assertIn('total_schools', stats)
        self.assertEqual(stats['total_schools'], 2)
        self.assertIn('total_students', stats)
        self.assertIn('total_instructors', stats)
        self.assertIn('active_lessons_today', stats)

    def test_quick_stats_school_owner(self):
        """Test quick stats for school owner"""
        self.client.force_authenticate(user=self.school_owner1)
        
        response = self.client.get(self.quick_stats_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['user_role'], 'A')
        
        stats = response.data['stats']
        self.assertIn('my_schools', stats)
        self.assertEqual(stats['my_schools'], 1)
        self.assertIn('total_students', stats)
        self.assertIn('active_students', stats)
        self.assertIn('today_lessons', stats)

    def test_quick_stats_instructor(self):
        """Test quick stats for instructor"""
        self.client.force_authenticate(user=self.instructor1)
        
        response = self.client.get(self.quick_stats_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['user_role'], 'I')
        
        stats = response.data['stats']
        self.assertIn('today_lessons', stats)
        self.assertIn('today_completed', stats)
        self.assertIn('this_week_lessons', stats)
        self.assertIn('average_rating', stats)

    def test_quick_stats_instructor_no_profile(self):
        """Test quick stats for instructor without active profile"""
        instructor_no_profile = User.objects.create_user(
            username='instructor_no_profile2',
            email='no_profile2@test.com',
            password='testpass123',
            role='I'
        )
        
        self.client.force_authenticate(user=instructor_no_profile)
        
        response = self.client.get(self.quick_stats_url)
        
        print("#"*100)
        print(response.data)
        print(response)
        print("#"*100)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


    def test_quick_stats_student(self):
        """Test quick stats for student"""
        self.client.force_authenticate(user=self.student1)
        
        response = self.client.get(self.quick_stats_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['user_role'], 'S')
        
        stats = response.data['stats']
        self.assertEqual(stats['theory_progress'], 75.0)
        self.assertEqual(stats['driving_progress'], 60.0)
        self.assertEqual(stats['total_hours'], 50.0)
        self.assertEqual(stats['achievements'], 2)

    def test_quick_stats_student_no_profile(self):
        """Test quick stats for student without active profile"""
        student_no_profile = User.objects.create_user(
            username='student_no_profile2',
            email='no_profile2@test.com',
            password='testpass123',
            role='S'
        )
        
        self.client.force_authenticate(user=student_no_profile)
        
        response = self.client.get(self.quick_stats_url)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)

    # ==================== NOTIFICATIONS TESTS ====================

    def test_notifications_platform_admin(self):
        """Test notifications for platform admin"""
        self.client.force_authenticate(user=self.platform_admin)
        
        response = self.client.get(self.notifications_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['user_role'], 'A')
        
        # Should have notifications for pending and failed messages
        self.assertGreater(response.data['total_notifications'], 0)
        
        notifications = response.data['notifications']
        if notifications:
            notification = notifications[0]
            self.assertIn('type', notification)
            self.assertIn('title', notification)
            self.assertIn('message', notification)
            self.assertIn('priority', notification)
            self.assertIn('timestamp', notification)

    def test_notifications_school_owner(self):
        """Test notifications for school owner"""
        self.client.force_authenticate(user=self.school_owner1)
        
        response = self.client.get(self.notifications_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['user_role'], 'A')
        
        # School owner should have notifications for their schools
        notifications = response.data['notifications']
        
        # Should have notification for low completion rate (< 80%) and at-risk students
        has_completion_notification = any(
            'completion' in n.get('title', '').lower() for n in notifications
        )
        has_risk_notification = any(
            'risk' in n.get('title', '').lower() for n in notifications
        )
        
        # Either should be present
        self.assertTrue(has_completion_notification or has_risk_notification)

    def test_notifications_instructor(self):
        """Test notifications for instructor"""
        self.client.force_authenticate(user=self.instructor1)
        
        response = self.client.get(self.notifications_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['user_role'], 'I')
        
        notifications = response.data['notifications']
        
        # Should have notifications for today's lessons
        has_today_lesson = any(
            'upcoming' in n.get('title', '').lower() for n in notifications
        )
        
        # Should have pending feedback notification
        has_pending_feedback = any(
            'feedback' in n.get('title', '').lower() for n in notifications
        )
        
        # At least one should be present
        self.assertTrue(has_today_lesson or has_pending_feedback)

    def test_notifications_student(self):
        """Test notifications for student"""
        self.client.force_authenticate(user=self.student1)
        
        response = self.client.get(self.notifications_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['user_role'], 'S')
        
        notifications = response.data['notifications']
        
        # Should have notifications for upcoming lessons
        has_upcoming_lesson = any(
            'upcoming' in n.get('title', '').lower() for n in notifications
        )
        
        # Should have message notification
        has_message_notification = any(
            'message' in n.get('title', '').lower() for n in notifications
        )
        
        # At least one should be present
        self.assertTrue(has_upcoming_lesson or has_message_notification)

    def test_notifications_with_limit(self):
        """Test notifications with limit parameter"""
        self.client.force_authenticate(user=self.platform_admin)
        
        response = self.client.get(
            self.notifications_url,
            {'limit': 2}
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertLessEqual(len(response.data['notifications']), 2)

    def test_notifications_invalid_limit(self):
        """Test notifications with invalid limit parameter"""
        self.client.force_authenticate(user=self.platform_admin)
        
        # Test with very high limit (should be capped at 50)
        response = self.client.get(
            self.notifications_url,
            {'limit': 100}
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertLessEqual(len(response.data['notifications']), 50)

    # ==================== EDGE CASES & ERROR HANDLING ====================

    def test_dashboard_with_no_schools_owner(self):
        """Test school owner dashboard when owner has no schools"""
        # Create school owner with no schools
        owner_no_schools = User.objects.create_user(
            username='owner_no_schools',
            email='no_schools@test.com',
            password='testpass123',
            role='A'
        )
        
        self.client.force_authenticate(user=owner_no_schools)
        
        response = self.client.get(self.school_owner_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['message'], 'You do not own any schools yet')
        self.assertEqual(response.data['schools'], [])

    def test_dashboard_with_minimal_data(self):
        """Test dashboard with minimal data"""
        # Create minimal data
        minimal_user = User.objects.create_user(
            username='minimal',
            email='minimal@test.com',
            password='testpass123',
            role='S'
        )
        
        minimal_school = DrivingSchool.objects.create(
            owner=self.school_owner1,
            name='Minimal School',
            email='minimal@test.com',
            address='Minimal Address'
        )
        
        minimal_profile = StudentProfile.objects.create(
            user=minimal_user,
            school=minimal_school,
            status='A',
            joined_at=timezone.now()
        )
        
        self.client.force_authenticate(user=minimal_user)
        
        response = self.client.get(self.student_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Should still return valid dashboard with default values
        self.assertEqual(response.data['dashboard_type'], 'student')
        self.assertIn('progress_summary', response.data)
        self.assertIn('attendance', response.data)

    def test_dashboard_performance_with_large_data(self):
        """Test dashboard performance with simulated large dataset"""
        # Create additional data to simulate larger dataset
        for i in range(5):
            student = User.objects.create_user(
                username=f'performance_student_{i}',
                email=f'performance_{i}@test.com',
                password='testpass123',
                role='S'
            )
            
            StudentProfile.objects.create(
                user=student,
                school=self.school1,
                status='A',
                progress_theory=i * 20,
                progress_driving=i * 15
            )
            
            # Create lessons
            lesson = Lesson.objects.create(
                title=f'Performance Lesson {i}',
                instructor=self.instructor1,
                school=self.school1,
                lesson_type='D',
                duration=60,
                date=timezone.now() - timedelta(days=i),
                status='C'
            )
            
            # Create feedback
            Feedback.objects.create(
                student=self.student1_profile,
                lesson=lesson,
                rating=4,
                comment=f'Performance feedback {i}'
            )
        
        self.client.force_authenticate(user=self.platform_admin)
        
        # Time the request
        import time
        start_time = time.time()
        
        response = self.client.get(self.platform_admin_url)
        
        end_time = time.time()
        response_time = end_time - start_time
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Response should be under 2 seconds even with additional data
        self.assertLess(response_time, 2.0)
        
        # Log performance for reference
        print(f"\nDashboard response time with additional data: {response_time:.3f}s")

    # ==================== INTEGRATION TESTS ====================

    def test_end_to_end_role_based_access(self):
        """Test end-to-end role-based access control"""
        users = [
            (self.platform_admin, 'platform_admin', status.HTTP_200_OK),
            (self.school_owner1, 'school_owner', status.HTTP_200_OK),
            (self.instructor1, 'instructor', status.HTTP_200_OK),
            (self.student1, 'student', status.HTTP_200_OK),
        ]
        
        for user, dashboard_type, expected_status in users:
            self.client.force_authenticate(user=user)
            
            # Test specific dashboard endpoint
            if dashboard_type == 'platform_admin':
                url = self.platform_admin_url
            elif dashboard_type == 'school_owner':
                url = self.school_owner_url
            elif dashboard_type == 'instructor':
                url = self.instructor_url
            else:  # student
                url = self.student_url
            
            response = self.client.get(url)
            
            self.assertEqual(
                response.status_code,
                expected_status,
                f"Failed for {user.username} accessing {dashboard_type}"
            )
            
            if expected_status == status.HTTP_200_OK:
                self.assertEqual(
                    response.data['dashboard_type'],
                    dashboard_type,
                    f"Wrong dashboard type for {user.username}"
                )

    def test_dashboard_data_consistency(self):
        """Test that dashboard data is consistent with database"""
        self.client.force_authenticate(user=self.platform_admin)
        
        response = self.client.get(self.platform_admin_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify data matches database
        overview = response.data['system_overview']
        
        # Check school count
        db_school_count = DrivingSchool.objects.count()
        self.assertEqual(overview['total_schools'], db_school_count)
        
        # Check student count
        db_student_count = StudentProfile.objects.filter(user__role='S').count()
        self.assertEqual(overview['total_students'], db_student_count)
        
        # Check active students count
        db_active_students = StudentProfile.objects.filter(
            user__role='S',
            status='A'
        ).count()
        self.assertEqual(overview['active_students'], db_active_students)
        
        # Check instructor count
        db_instructor_count = User.objects.filter(role='I').count()
        self.assertEqual(overview['total_instructors'], db_instructor_count)

    # ==================== CLEANUP TESTS ====================

    def test_teardown_cleans_up_properly(self):
        """Test that tearDown method properly cleans up test data"""
        # Verify initial state
        initial_user_count = User.objects.count()
        initial_school_count = DrivingSchool.objects.count()
        
        self.assertGreater(initial_user_count, 0)
        self.assertGreater(initial_school_count, 0)
        
        # Run teardown
        self.tearDown()
        
        # Verify cleanup
        self.assertEqual(User.objects.count(), 0)
        self.assertEqual(DrivingSchool.objects.count(), 0)
        self.assertEqual(StudentProfile.objects.count(), 0)
        self.assertEqual(Lesson.objects.count(), 0)
        self.assertEqual(SchoolAnalytics.objects.count(), 0)

    # ==================== ADDITIONAL VALIDATION TESTS ====================

    def test_dashboard_timestamps(self):
        """Test that dashboard includes proper timestamps"""
        self.client.force_authenticate(user=self.platform_admin)
        
        response = self.client.get(self.platform_admin_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Check for timestamp field
        self.assertIn('timestamp', response.data)
        
        # Verify timestamp is valid ISO format
        from datetime import datetime
        try:
            datetime.fromisoformat(response.data['timestamp'].replace('Z', '+00:00'))
            timestamp_valid = True
        except ValueError:
            timestamp_valid = False
        
        self.assertTrue(timestamp_valid, "Timestamp should be valid ISO format")

    def test_dashboard_error_handling(self):
        """Test dashboard error handling for edge cases"""
        # Test with invalid user (no role)
        invalid_user = User.objects.create_user(
            username='invalid_user',
            email='invalid@test.com',
            password='testpass123'
        )
        # No role assigned
        
        self.client.force_authenticate(user=invalid_user)
        
        response = self.client.get(self.overview_url)
        
        print('#'*100)
        print(response.data)
        print(response)
        print("#"*100)

        # Should either return 403 or handle gracefully
        self.assertIn(response.status_code, [status.HTTP_400_BAD_REQUEST, status.HTTP_200_OK])

    def test_dashboard_query_optimization(self):
        """Test that dashboard queries are optimized"""
        self.client.force_authenticate(user=self.platform_admin)
        
        # Count database queries
        from django.db import connection
        from django.test.utils import CaptureQueriesContext
        
        with CaptureQueriesContext(connection) as context:
            response = self.client.get(self.platform_admin_url)
        
        query_count = len(context)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Query count should be reasonable (not too many N+1 queries)
        # Platform admin dashboard might have more queries due to aggregations
        # Let's set a reasonable upper bound
        self.assertLess(query_count, 50, f"Too many queries: {query_count}")
        
        # Log query count for reference
        print(f"\nPlatform admin dashboard query count: {query_count}")
        
        # Also check for N+1 patterns by looking for similar queries
        query_types = {}
        for query in context:
            sql = query['sql']
            # Count by operation type
            if 'SELECT' in sql:
                key = 'SELECT'
            elif 'INSERT' in sql:
                key = 'INSERT'
            elif 'UPDATE' in sql:
                key = 'UPDATE'
            elif 'DELETE' in sql:
                key = 'DELETE'
            else:
                key = 'OTHER'
            
            query_types[key] = query_types.get(key, 0) + 1
        
        # Should be mostly SELECT queries
        self.assertGreater(query_types.get('SELECT', 0), 0)
        
        print(f"Query types: {query_types}")


if __name__ == '__main__':
    import unittest
    unittest.main()
# tests/test_report_views.py

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from datetime import datetime, timedelta, date
import json
import csv
from io import StringIO

from DriveApp.models import (
    User, DrivingSchool, StudentProfile, Lesson, 
    Attendance, Feedback, SchoolAnalytics, Achievement,
    Schedule, Vehicle, CommunicationTemplate, AutomatedMessage
)
from DriveApp.services import ReportService
from decimal import Decimal


class ReportViewSetTestCase(APITestCase):
    """Comprehensive tests for ReportViewSet"""

    def setUp(self):
        """Set up test data"""
        
        # Create users with different roles
        self.platform_admin = User.objects.create_user(
            username='platform_admin',
            email='admin@platform.com',
            password='AdminPass123!',
            role='A',
            is_staff=True
        )
        
        self.school_owner1 = User.objects.create_user(
            username='school_owner1',
            email='owner1@school.com',
            password='testpass123',
            role='A',
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
            role='I'
        )
        
        self.instructor2 = User.objects.create_user(
            username='instructor2',
            email='instructor2@school.com',
            password='testpass123',
            role='I'
        )
        
        self.student = User.objects.create_user(
            username='student',
            email='student@school.com',
            password='testpass123',
            role='S'
        )
        
        # Create driving schools
        self.school1 = DrivingSchool.objects.create(
            owner=self.school_owner1,
            name='Drive Safe Academy',
            email='school1@test.com',
            address='123 Main St',
            created_at=timezone.now() - timedelta(days=60)
        )
        
        self.school2 = DrivingSchool.objects.create(
            owner=self.school_owner2,
            name='Pro Driving School',
            email='school2@test.com',
            address='456 Oak Ave',
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
            user=self.student,
            school=self.school1,
            status='A',
            joined_at=timezone.now() - timedelta(days=15),
            progress_theory=75.0,
            progress_driving=60.0,
            total_hours_theory=30.0,
            total_hours_driving=20.0
        )
        
        self.student2_profile = StudentProfile.objects.create(
            user=User.objects.create_user(
                username='student2',
                email='student2@school.com',
                password='testpass123',
                role='S'
            ),
            school=self.school1,
            status='C',  # Completed
            joined_at=timezone.now() - timedelta(days=90),
            completion_date=timezone.now().date() - timedelta(days=10),
            progress_theory=100.0,
            progress_driving=100.0,
            total_hours_theory=50.0,
            total_hours_driving=40.0
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
            joined_at=timezone.now() - timedelta(days=20)
        )
        
        # Create lessons
        self.today = timezone.now().date()
        
        self.lesson1 = Lesson.objects.create(
            title='Basic Driving Lesson',
            instructor=self.instructor1,
            school=self.school1,
            lesson_type='D',
            description='Basic driving techniques',
            duration=60,
            date=timezone.make_aware(datetime.combine(self.today - timedelta(days=5), datetime.min.time())),
            status='C'  # Completed
        )
        
        self.lesson2 = Lesson.objects.create(
            title='Theory Class',
            instructor=self.instructor1,
            school=self.school1,
            lesson_type='T',
            description='Traffic rules and regulations',
            duration=90,
            date=timezone.make_aware(datetime.combine(self.today - timedelta(days=3), datetime.min.time())),
            status='C'
        )
        
        self.lesson3 = Lesson.objects.create(
            title='Advanced Driving',
            instructor=self.instructor2,
            school=self.school1,
            lesson_type='D',
            duration=120,
            date=timezone.make_aware(datetime.combine(self.today - timedelta(days=2), datetime.min.time())),
            status='C'
        )
        
        self.lesson4 = Lesson.objects.create(
            title='School 2 Lesson',
            instructor=self.instructor2,
            school=self.school2,
            lesson_type='D',
            duration=60,
            date=timezone.make_aware(datetime.combine(self.today - timedelta(days=1), datetime.min.time())),
            status='C'
        )
        
        self.lesson5 = Lesson.objects.create(
            title='Future Lesson',
            instructor=self.instructor1,
            school=self.school1,
            lesson_type='D',
            duration=60,
            date=timezone.now() + timedelta(days=1),
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
            student=self.student2_profile,
            lesson=self.lesson1,
            presence=True,
            hours_completed=1.0,
            notes='Completed',
            created_at=timezone.now() - timedelta(days=5)
        )
        
        self.attendance4 = Attendance.objects.create(
            student=self.student1_profile,
            lesson=self.lesson3,
            presence=False,
            hours_completed=0,
            notes='Absent',
            created_at=timezone.now() - timedelta(days=2)
        )
        
        # Create feedback
        self.feedback1 = Feedback.objects.create(
            student=self.student1_profile,
            lesson=self.lesson1,
            rating=5,
            comment='Great lesson!',
            created_at=timezone.now() - timedelta(days=5)
        )
        
        self.feedback2 = Feedback.objects.create(
            student=self.student1_profile,
            lesson=self.lesson2,
            rating=4,
            comment='Very informative',
            created_at=timezone.now() - timedelta(days=3)
        )
        
        self.feedback3 = Feedback.objects.create(
            student=self.student2_profile,
            lesson=self.lesson1,
            rating=5,
            comment='Excellent instructor',
            created_at=timezone.now() - timedelta(days=5)
        )
        
        self.feedback4 = Feedback.objects.create(
            student=self.student3_profile,
            lesson=self.lesson4,
            rating=3,
            comment='Average',
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
        
        # Create analytics for school1
        self.analytics_today = SchoolAnalytics.objects.create(
            school=self.school1,
            date=self.today,
            total_students=10,
            active_students=8,
            new_students=2,
            completion_rate=75.5,
            revenue=2500.00,
            average_rating=4.5,
            lessons_completed=45,
            instructor_utilization=85.0
        )
        
        self.analytics_yesterday = SchoolAnalytics.objects.create(
            school=self.school1,
            date=self.yesterday,
            total_students=9,
            active_students=7,
            new_students=1,
            completion_rate=74.0,
            revenue=2000.00,
            average_rating=4.3,
            lessons_completed=42,
            instructor_utilization=80.0
        )
        
        self.analytics_last_week = SchoolAnalytics.objects.create(
            school=self.school1,
            date=self.last_week,
            total_students=8,
            active_students=6,
            new_students=0,
            completion_rate=70.0,
            revenue=1500.00,
            average_rating=4.0,
            lessons_completed=35,
            instructor_utilization=75.0
        )
        
        # Create analytics for school2
        self.analytics_school2 = SchoolAnalytics.objects.create(
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
            start_time=timezone.now() - timedelta(days=5, hours=2),
            end_time=timezone.now() - timedelta(days=5, hours=3)
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
        
        # Create automated message
        self.message = AutomatedMessage.objects.create(
            student=self.student1_profile,
            template=self.template,
            scheduled_for=timezone.now() + timedelta(days=1),
            status='pending'
        )
        
        # API client
        self.client = APIClient()
        
        # URLs
        self.weekly_report_url = reverse('report-report-weekly')  
        self.monthly_report_url = reverse('report-report-monthly')
        self.send_weekly_report_url = reverse('report-report-send-weekly')
        self.instructor_performance_url = reverse('report-instructor-performance')
        self.student_progress_url = reverse('report-student-progress')
        self.financial_summary_url = reverse('report-financial-summary')
        self.export_url = '/report/export/'


    def tearDown(self):
        """Clean up after tests"""
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



    def test_export_debug(self):
        """Debug test to see what's happening"""
        self.client.force_authenticate(user=self.platform_admin)
        
        # First, verify the URL is correct
        print(f"\nExport URL: {self.export_url}")
        
        # Try to get the export
        response = self.client.get(
            self.export_url,
            {
                'school_id': self.school1.id,
                'report_type': 'weekly',
                'format': 'json'
            }
        )
        
        print(f"\nStatus Code: {response.status_code}")
        print(f"Response Data: {response.data}")
        
        # If 404, let's check if the endpoint exists
        if response.status_code == 404:
            # Try accessing it directly
            from django.urls import reverse
            print(f"\nTrying URL: /api/report/export/")
            
            response2 = self.client.get(
                '/api/report/export/',
                {
                    'school_id': self.school1.id,
                    'report_type': 'weekly',
                    'format': 'json'
                }
            )
            print(f"Direct URL Status: {response2.status_code}")
            print(f"Direct URL Data: {response2.data}")
        
        # Also check if ReportService works directly
        from DriveApp.services import ReportService
        try:
            report = ReportService.generate_weekly_report(
                school_id=self.school1.id,
                end_date=None,
                user=self.platform_admin
            )
            print(f"\nDirect service call successful!")
            print(f"Report keys: {report.keys()}")
        except Exception as e:
            print(f"\nDirect service call failed: {e}")
            import traceback
            traceback.print_exc()



    # ==================== AUTHENTICATION & PERMISSIONS TESTS ====================

    def test_unauthenticated_access_denied(self):
        """✅ Test that unauthenticated users cannot access reports"""
        response = self.client.get(self.weekly_report_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_student_access_denied(self):
        """✅ Students cannot access reports"""
        self.client.force_authenticate(user=self.student)
        response = self.client.get(self.weekly_report_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    # ==================== WEEKLY REPORT TESTS ====================

    def test_weekly_report_as_platform_admin(self):
        """✅ Platform admin can generate weekly report for any school"""
        self.client.force_authenticate(user=self.platform_admin)
        
        response = self.client.get(
            self.weekly_report_url, 
            {'school_id': self.school1.id}
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['report_type'], 'weekly')
        self.assertEqual(response.data['school']['id'], self.school1.id)
        self.assertEqual(response.data['period']['days'], 7)
        
        # Check required fields
        self.assertIn('summary_metrics', response.data)
        self.assertIn('daily_breakdown', response.data)
        self.assertIn('lessons', response.data)
        self.assertIn('attendance', response.data)
        self.assertIn('feedback', response.data)
        self.assertIn('top_students', response.data)
        self.assertIn('instructor_performance', response.data)
        self.assertIn('comparison_with_previous_week', response.data)
        
        # Check summary metrics
        summary = response.data['summary_metrics']
        self.assertIn('total_students', summary)
        self.assertIn('avg_active_students', summary)
        self.assertIn('total_new_students', summary)
        self.assertIn('avg_completion_rate', summary)
        self.assertIn('total_revenue', summary)
        self.assertIn('avg_rating', summary)
        self.assertIn('total_lessons', summary)
        self.assertIn('avg_instructor_utilization', summary)

    def test_weekly_report_as_school_owner(self):
        """✅ School owner can generate weekly report for their school"""
        self.client.force_authenticate(user=self.school_owner1)
        
        response = self.client.get(
            self.weekly_report_url, 
            {'school_id': self.school1.id}
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['school']['id'], self.school1.id)
        self.assertEqual(response.data['school']['owner'], 'school_owner1')

    def test_weekly_report_as_instructor(self):
        """✅ Instructor cannot generate weekly report"""
        self.client.force_authenticate(user=self.instructor1)
        
        response = self.client.get(
            self.weekly_report_url, 
            {'school_id': self.school1.id}
        )
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_weekly_report_missing_school_id(self):
        """✅ Cannot generate weekly report without school_id"""
        self.client.force_authenticate(user=self.platform_admin)
        
        response = self.client.get(self.weekly_report_url)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('school_id', response.data['error'])

    def test_weekly_report_school_owner_wrong_school(self):
        """✅ School owner cannot generate report for another school"""
        self.client.force_authenticate(user=self.school_owner1)
        
        response = self.client.get(
            self.weekly_report_url, 
            {'school_id': self.school2.id}
        )
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_weekly_report_with_custom_date(self):
        """✅ Test weekly report with custom date parameter"""
        self.client.force_authenticate(user=self.platform_admin)
        
        custom_date = (self.today - timedelta(days=3)).isoformat()
        response = self.client.get(
            self.weekly_report_url, 
            {
                'school_id': self.school1.id,
                'date': custom_date
            }
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # The report should cover 7 days ending at custom_date
        end_date = datetime.fromisoformat(custom_date).date()
        start_date = end_date - timedelta(days=6)
        
        self.assertEqual(response.data['period']['end_date'].isoformat(), end_date.isoformat())
        self.assertEqual(response.data['period']['start_date'].isoformat(), start_date.isoformat())

    def test_weekly_report_no_analytics_data(self):
        """✅ Weekly report should handle no analytics data gracefully"""
        # Delete all analytics for school1
        SchoolAnalytics.objects.filter(school=self.school1).delete()
        
        self.client.force_authenticate(user=self.platform_admin)
        
        response = self.client.get(
            self.weekly_report_url, 
            {'school_id': self.school1.id}
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['message'], 'No analytics data available for this week')

    # ==================== MONTHLY REPORT TESTS ====================

    def test_monthly_report_as_platform_admin(self):
        """✅ Platform admin can generate monthly report for any school"""
        self.client.force_authenticate(user=self.platform_admin)
        
        response = self.client.get(
            self.monthly_report_url, 
            {'school_id': self.school1.id}
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['report_type'], 'monthly')
        self.assertIn('month', response.data['period'])
        self.assertIn('start_date', response.data['period'])
        self.assertIn('end_date', response.data['period'])
        
        # Check required fields
        self.assertIn('executive_summary', response.data)
        self.assertIn('student_metrics', response.data)
        self.assertIn('financial_metrics', response.data)
        self.assertIn('performance_metrics', response.data)
        self.assertIn('lesson_metrics', response.data)
        self.assertIn('weekly_breakdown', response.data)
        self.assertIn('instructor_performance', response.data)
        self.assertIn('achievements', response.data)
        self.assertIn('attendance', response.data)
        self.assertIn('comparison_with_previous_month', response.data)

    def test_monthly_report_as_school_owner(self):
        """✅ School owner can generate monthly report for their school"""
        self.client.force_authenticate(user=self.school_owner1)
        
        response = self.client.get(
            self.monthly_report_url, 
            {'school_id': self.school1.id}
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['school']['owner'], 'school_owner1')

    def test_monthly_report_as_instructor(self):
        """✅ Instructor cannot generate monthly report"""
        self.client.force_authenticate(user=self.instructor1)
        
        response = self.client.get(
            self.monthly_report_url, 
            {'school_id': self.school1.id}
        )
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_monthly_report_missing_school_id(self):
        """✅ Cannot generate monthly report without school_id"""
        self.client.force_authenticate(user=self.platform_admin)
        
        response = self.client.get(self.monthly_report_url)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('school_id', response.data['error'])

    def test_monthly_report_with_custom_month(self):
        """✅ Test monthly report with custom month parameter"""
        self.client.force_authenticate(user=self.platform_admin)
        
        # Create analytics for previous month
        last_month = (self.today.replace(day=1) - timedelta(days=1)).replace(day=1)
        SchoolAnalytics.objects.create(
            school=self.school1,
            date=last_month,
            total_students=7,
            active_students=5,
            revenue=1800.00
        )
        
        custom_month = last_month.strftime('%Y-%m')
        response = self.client.get(
            self.monthly_report_url, 
            {
                'school_id': self.school1.id,
                'month': custom_month
            }
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['period']['month'], last_month.strftime('%B %Y'))

    def test_monthly_report_future_month_denied(self):
        """✅ Cannot generate monthly report for future months"""
        self.client.force_authenticate(user=self.platform_admin)
        
        future_date = self.today + timedelta(days=32)
        future_month = future_date.strftime('%Y-%m')
        
        response = self.client.get(
            self.monthly_report_url, 
            {
                'school_id': self.school1.id,
                'month': future_month
            }
        )
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('future', response.data['error'].lower())

    # ==================== SEND WEEKLY REPORT TESTS ====================

    def test_send_weekly_report_as_platform_admin(self):
        """✅ Platform admin can send weekly report via email"""
        self.client.force_authenticate(user=self.platform_admin)
        
        data = {'school_id': self.school1.id}
        response = self.client.post(self.send_weekly_report_url, data, format='json')
        
        # Note: In test environment, email might not be sent, but endpoint should work
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('sent successfully', response.data['message'])
        self.assertEqual(response.data['recipient'], self.school_owner1.email)
        self.assertEqual(response.data['school'], self.school1.name)
        self.assertIn('period', response.data)
        self.assertIn('sent_at', response.data)

    def test_send_weekly_report_as_school_owner(self):
        """✅ School owner can send weekly report for their school"""
        self.client.force_authenticate(user=self.school_owner1)
        
        data = {'school_id': self.school1.id}
        response = self.client.post(self.send_weekly_report_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['recipient'], self.school_owner1.email)

    def test_send_weekly_report_as_instructor_denied(self):
        """✅ Instructor cannot send weekly report"""
        self.client.force_authenticate(user=self.instructor1)
        
        data = {'school_id': self.school1.id}
        response = self.client.post(self.send_weekly_report_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_send_weekly_report_missing_school_id(self):
        """✅ Cannot send weekly report without school_id"""
        self.client.force_authenticate(user=self.platform_admin)
        
        response = self.client.post(self.send_weekly_report_url, {}, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('school_id', response.data['error'])

    def test_send_weekly_report_school_owner_wrong_school(self):
        """✅ School owner cannot send report for another school"""
        self.client.force_authenticate(user=self.school_owner1)
        
        data = {'school_id': self.school2.id}
        response = self.client.post(self.send_weekly_report_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_send_weekly_report_with_custom_date(self):
        """✅ Test sending weekly report with custom date"""
        self.client.force_authenticate(user=self.platform_admin)
        
        custom_date = (self.today - timedelta(days=3)).isoformat()
        data = {
            'school_id': self.school1.id,
            'date': custom_date
        }
        
        response = self.client.post(self.send_weekly_report_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    # ==================== INSTRUCTOR PERFORMANCE REPORT TESTS ====================

    def test_instructor_performance_as_platform_admin(self):
        """✅ Platform admin can generate instructor performance report"""
        self.client.force_authenticate(user=self.platform_admin)
        
        response = self.client.get(
            self.instructor_performance_url,
            {'school_id': self.school1.id}
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['report_type'], 'instructor_performance')
        self.assertEqual(response.data['school']['id'], self.school1.id)
        
        # Check required fields
        self.assertIn('overall_statistics', response.data)
        self.assertIn('instructor_reports', response.data)
        self.assertIn('top_performers', response.data)
        
        # Check instructor reports structure
        if response.data['instructor_reports']:
            instructor_report = response.data['instructor_reports'][0]
            self.assertIn('instructor', instructor_report)
            self.assertIn('lesson_metrics', instructor_report)
            self.assertIn('student_metrics', instructor_report)
            self.assertIn('feedback_metrics', instructor_report)
            self.assertIn('performance_score', instructor_report)
            
            # Check instructor details
            self.assertIn('id', instructor_report['instructor'])
            self.assertIn('name', instructor_report['instructor'])
            self.assertIn('email', instructor_report['instructor'])

    def test_instructor_performance_as_school_owner(self):
        """✅ School owner can generate instructor performance report"""
        self.client.force_authenticate(user=self.school_owner1)
        
        response = self.client.get(
            self.instructor_performance_url,
            {'school_id': self.school1.id}
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_instructor_performance_as_instructor(self):
        """✅ Instructor can view instructor performance report for their school"""
        self.client.force_authenticate(user=self.instructor1)
        
        response = self.client.get(
            self.instructor_performance_url,
            {'school_id': self.school1.id}
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_instructor_performance_missing_school_id(self):
        """✅ Cannot generate instructor performance report without school_id"""
        self.client.force_authenticate(user=self.platform_admin)
        
        response = self.client.get(self.instructor_performance_url)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('school_id', response.data['error'])

    def test_instructor_performance_with_specific_instructor(self):
        """✅ Test instructor performance report for specific instructor"""
        self.client.force_authenticate(user=self.platform_admin)
        
        response = self.client.get(
            self.instructor_performance_url,
            {
                'school_id': self.school1.id,
                'instructor_id': self.instructor1.id
            }
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['instructor_reports']), 1)
        self.assertEqual(response.data['instructor_reports'][0]['instructor']['id'], self.instructor1.id)

    def test_instructor_performance_with_custom_date_range(self):
        """✅ Test instructor performance report with custom date range"""
        self.client.force_authenticate(user=self.platform_admin)
        
        start_date = (self.today - timedelta(days=10)).isoformat()
        end_date = self.today.isoformat()
        
        response = self.client.get(
            self.instructor_performance_url,
            {
                'school_id': self.school1.id,
                'start_date': start_date,
                'end_date': end_date
            }
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['period']['days'], 11)  # inclusive

    def test_instructor_performance_school_owner_wrong_school(self):
        """✅ School owner cannot view instructor performance for another school"""
        self.client.force_authenticate(user=self.school_owner1)
        
        response = self.client.get(
            self.instructor_performance_url,
            {'school_id': self.school2.id}
        )
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_instructor_performance_instructor_wrong_school(self):
        """✅ Instructor cannot view instructor performance for another school"""
        self.client.force_authenticate(user=self.instructor1)
        
        response = self.client.get(
            self.instructor_performance_url,
            {'school_id': self.school2.id}
        )
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    # ==================== STUDENT PROGRESS REPORT TESTS ====================

    def test_student_progress_as_platform_admin(self):
        """✅ Platform admin can generate student progress report"""
        self.client.force_authenticate(user=self.platform_admin)
        
        response = self.client.get(
            self.student_progress_url,
            {'school_id': self.school1.id}
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['report_type'], 'student_progress')
        self.assertEqual(response.data['school']['id'], self.school1.id)
        
        # Check required fields
        self.assertIn('summary', response.data)
        self.assertIn('students', response.data)
        self.assertIn('categorized', response.data)
        
        # Check summary
        summary = response.data['summary']
        self.assertIn('total_students', summary)
        self.assertIn('at_risk', summary)
        self.assertIn('on_track', summary)
        self.assertIn('excelling', summary)
        self.assertIn('avg_progress', summary)
        
        # Check student structure
        if response.data['students']:
            student = response.data['students'][0]
            self.assertIn('student', student)
            self.assertIn('status', student)
            self.assertIn('progress', student)
            self.assertIn('hours', student)
            self.assertIn('attendance', student)
            self.assertIn('engagement', student)
            self.assertIn('dates', student)

    def test_student_progress_as_school_owner(self):
        """✅ School owner can generate student progress report"""
        self.client.force_authenticate(user=self.school_owner1)
        
        response = self.client.get(
            self.student_progress_url,
            {'school_id': self.school1.id}
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_student_progress_as_instructor(self):
        """✅ Instructor can view student progress report for their school"""
        self.client.force_authenticate(user=self.instructor1)
        
        response = self.client.get(
            self.student_progress_url,
            {'school_id': self.school1.id}
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_student_progress_missing_school_id(self):
        """✅ Cannot generate student progress report without school_id"""
        self.client.force_authenticate(user=self.platform_admin)
        
        response = self.client.get(self.student_progress_url)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('school_id', response.data['error'])

    def test_student_progress_with_status_filter(self):
        """✅ Test student progress report with status filter"""
        self.client.force_authenticate(user=self.platform_admin)
        
        response = self.client.get(
            self.student_progress_url,
            {
                'school_id': self.school1.id,
                'status': 'A'  # Active students only
            }
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Check that all returned students have status 'A'
        for student in response.data['students']:
            self.assertEqual(student['status'], 'Active')

    def test_student_progress_with_min_progress_filter(self):
        """✅ Test student progress report with min_progress filter"""
        self.client.force_authenticate(user=self.platform_admin)
        
        response = self.client.get(
            self.student_progress_url,
            {
                'school_id': self.school1.id,
                'min_progress': '50'  # Students with at least 50% average progress
            }
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Check that all returned students have at least 50% progress
        for student in response.data['students']:
            self.assertGreaterEqual(student['progress']['average'], 50)

    def test_student_progress_categorization(self):
        """✅ Test student categorization in progress report"""
        self.client.force_authenticate(user=self.platform_admin)
        
        response = self.client.get(
            self.student_progress_url,
            {'school_id': self.school1.id}
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Check categorization
        categorized = response.data['categorized']
        self.assertIn('at_risk', categorized)
        self.assertIn('on_track', categorized)
        self.assertIn('excelling', categorized)
        
        # Verify categorization logic
        for student in categorized['at_risk']:
            self.assertLess(student['progress']['average'], 20)
        
        for student in categorized['on_track']:
            self.assertGreaterEqual(student['progress']['average'], 20)
            self.assertLess(student['progress']['average'], 80)
        
        for student in categorized['excelling']:
            self.assertGreaterEqual(student['progress']['average'], 80)

    # ==================== FINANCIAL SUMMARY REPORT TESTS ====================

    def test_financial_summary_as_platform_admin(self):
        """✅ Platform admin can generate financial summary report"""
        self.client.force_authenticate(user=self.platform_admin)
        
        response = self.client.get(
            self.financial_summary_url,
            {'school_id': self.school1.id}
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['report_type'], 'financial_summary')
        self.assertEqual(response.data['school']['id'], self.school1.id)
        
        # Check required fields
        self.assertIn('period', response.data)
        self.assertIn('financial_summary', response.data)
        self.assertIn('daily_revenue', response.data)
        
        # Check financial summary
        summary = response.data['financial_summary']
        self.assertIn('total_revenue', summary)
        self.assertIn('avg_daily_revenue', summary)
        self.assertIn('highest_revenue_day', summary)
        self.assertIn('lowest_revenue_day', summary)
        
        # Check daily revenue structure
        if response.data['daily_revenue']:
            day = response.data['daily_revenue'][0]
            self.assertIn('date', day)
            self.assertIn('revenue', day)

    def test_financial_summary_as_school_owner(self):
        """✅ School owner can generate financial summary report"""
        self.client.force_authenticate(user=self.school_owner1)
        
        response = self.client.get(
            self.financial_summary_url,
            {'school_id': self.school1.id}
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_financial_summary_as_instructor(self):
        """✅ Instructor can view financial summary report for their school"""
        self.client.force_authenticate(user=self.instructor1)
        
        response = self.client.get(
            self.financial_summary_url,
            {'school_id': self.school1.id}
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_financial_summary_missing_school_id(self):
        """✅ Cannot generate financial summary report without school_id"""
        self.client.force_authenticate(user=self.platform_admin)
        
        response = self.client.get(self.financial_summary_url)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('school_id', response.data['error'])

    def test_financial_summary_with_custom_date_range(self):
        """✅ Test financial summary report with custom date range"""
        self.client.force_authenticate(user=self.platform_admin)
        
        start_date = (self.today - timedelta(days=15)).isoformat()
        end_date = self.today.isoformat()
        
        response = self.client.get(
            self.financial_summary_url,
            {
                'school_id': self.school1.id,
                'start_date': start_date,
                'end_date': end_date
            }
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['period']['days'], 16)  # inclusive

    def test_financial_summary_with_monthly_breakdown(self):
        """✅ Test financial summary report monthly breakdown for longer periods"""
        # Create analytics for previous months
        two_months_ago = (self.today.replace(day=1) - timedelta(days=1)).replace(day=1)
        three_months_ago = (two_months_ago - timedelta(days=1)).replace(day=1)
        
        SchoolAnalytics.objects.create(
            school=self.school1,
            date=two_months_ago,
            revenue=3000.00
        )
        
        SchoolAnalytics.objects.create(
            school=self.school1,
            date=three_months_ago,
            revenue=2800.00
        )
        
        self.client.force_authenticate(user=self.platform_admin)
        
        start_date = three_months_ago
        end_date = self.today
        
        response = self.client.get(
            self.financial_summary_url,
            {
                'school_id': self.school1.id,
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat()
            }
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Should have monthly breakdown since period > 30 days
        self.assertIn('monthly_breakdown', response.data)
        self.assertGreater(len(response.data['monthly_breakdown']), 0)

    # ==================== EXPORT REPORT TESTS ====================

    def test_export_report_csv_as_platform_admin(self):
        """✅ Platform admin can export report as CSV"""
        self.client.force_authenticate(user=self.platform_admin)
        
        response = self.client.get(
            '/report/export/',
            {
                'school_id': self.school1.id,
                'report_type': 'weekly',
                'export_format': 'csv'
            }
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response['Content-Type'], 'text/csv')
        self.assertIn('attachment', response['Content-Disposition'])
        
        # Check CSV content
        content = response.content.decode('utf-8')
        csv_reader = csv.reader(StringIO(content))
        rows = list(csv_reader)
        
        self.assertGreater(len(rows), 0)  # Should have multiple rows
        


    def test_export_report_json_as_platform_admin(self):
        """✅ Platform admin can export report as JSON"""
        self.client.force_authenticate(user=self.platform_admin)
        
        response = self.client.get(
            '/report/export/',
            {
                'school_id': self.school1.id,
                'report_type': 'weekly',
                'export_format': 'json'
            }
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response['Content-Type'], 'application/json')
        
        # Check JSON content
        data = response.json()
        self.assertIn('report_type', data)
        self.assertIn('school', data)
        self.assertIn('period', data)
        self.assertIn('summary_metrics', data)

    def test_export_report_as_school_owner(self):
        """✅ School owner can export report for their school"""
        self.client.force_authenticate(user=self.school_owner1)
        
        response = self.client.get(
            '/report/export/',
            {
                'school_id': self.school1.id,
                'report_type': 'weekly',
                'exportt_format': 'csv'
            }
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_export_report_as_instructor_denied(self):
        """✅ Instructor cannot export reports"""
        self.client.force_authenticate(user=self.instructor1)
        
        response = self.client.get(
            '/report/export/',
            {
                'school_id': self.school1.id,
                'report_type': 'weekly',
                'export_format': 'csv'
            }
        )
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_export_report_missing_school_id(self):
        """✅ Cannot export report without school_id"""
        self.client.force_authenticate(user=self.platform_admin)
        
        response = self.client.get(
            '/report/export/',
            {'report_type': 'weekly', 
             'export_format': 'csv'}
        )
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_export_report_invalid_format(self):
        """✅ Cannot export report with invalid format"""
        self.client.force_authenticate(user=self.platform_admin)
        
        response = self.client.get(
            '/report/export/',
            {
                'school_id': self.school1.id,
                'report_type': 'weekly',
                'export_format': 'invalid'
            }
        )
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_export_report_invalid_report_type(self):
        """✅ Cannot export report with invalid report type"""
        self.client.force_authenticate(user=self.platform_admin)
        
        response = self.client.get(
            '/report/export/',
            {
                'school_id': self.school1.id,
                'report_type': 'invalid',
                'export_format': 'csv'
            }
        )
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_export_report_school_owner_wrong_school(self):
        """✅ School owner cannot export report for another school"""
        self.client.force_authenticate(user=self.school_owner1)
        
        response = self.client.get(
            '/report/export/',
            {
                'school_id': self.school2.id,
                'report_type': 'weekly',
                'export_format': 'csv'
            }
        )
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_export_monthly_report_csv(self):
        """✅ Test exporting monthly report as CSV"""
        self.client.force_authenticate(user=self.platform_admin)
        
        response = self.client.get(
            '/report/export/',
            {
                'school_id': self.school1.id,
                'report_type': 'monthly',
                'export_format': 'csv'
            }
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response['Content-Type'], 'text/csv')
        
        # Check CSV contains monthly data
        content = response.content.decode('utf-8')
        self.assertIn('MONTHLY', content.upper())

    def test_export_report_with_custom_dates(self):
        """✅ Test exporting report with custom date range"""
        self.client.force_authenticate(user=self.platform_admin)
        
        start_date = (self.today - timedelta(days=10)).isoformat()
        end_date = self.today.isoformat()
        
        response = self.client.get(
            '/report/export/',
            {
                'school_id': self.school1.id,
                'report_type': 'weekly',
                'format': 'json',
                'start_date': start_date,
                'end_date': end_date
            }
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    # ==================== EDGE CASES & ERROR HANDLING TESTS ====================

    def test_report_no_data_available(self):
        """✅ Report should handle no data gracefully"""
        # Delete all analytics
        SchoolAnalytics.objects.all().delete()
        
        self.client.force_authenticate(user=self.platform_admin)
        
        response = self.client.get(
            self.weekly_report_url,
            {'school_id': self.school1.id}
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('No analytics data available', response.data['message'])

    def test_report_school_not_found(self):
        """✅ Report should handle non-existent school"""
        self.client.force_authenticate(user=self.platform_admin)
        
        response = self.client.get(
            self.weekly_report_url,
            {'school_id': 99999}
        )
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_report_service_error_handling(self):
        """✅ Report should handle service errors gracefully"""
        self.client.force_authenticate(user=self.platform_admin)
        
        # Test with invalid date format
        response = self.client.get(
            self.weekly_report_url,
            {
                'school_id': self.school1.id,
                'date': 'invalid-date'
            }
        )
        
        # Might return 400 or handle gracefully
        self.assertIn(response.status_code, [status.HTTP_400_BAD_REQUEST, status.HTTP_200_OK])

    # ==================== INTEGRATION TESTS ====================

    def test_weekly_report_integration(self):
        """✅ Test complete weekly report integration"""
        self.client.force_authenticate(user=self.platform_admin)
        
        # Generate weekly report
        response = self.client.get(
            self.weekly_report_url,
            {'school_id': self.school1.id}
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify all expected data is present
        report = response.data
        
        print("#"*100)
        print(response.data)
        print(response)
        print("#"*100)
        
        # Check school info
        self.assertEqual(report['school']['id'], self.school1.id)
        self.assertEqual(report['school']['name'], 'Drive Safe Academy')
        
        # Check period
        self.assertEqual(report['period']['days'], 7)
        
        # Check metrics
        self.assertIsInstance(report['summary_metrics']['total_students'], int)
        self.assertIsInstance(report['summary_metrics']['avg_completion_rate'], (int, Decimal))
        self.assertIsInstance(report['summary_metrics']['total_revenue'], (int, float))
        
        # Check instructor performance
        self.assertIsInstance(report['instructor_performance'], list)
        
        # Check comparison data
        self.assertIn('comparison_with_previous_week', report)



    def test_export_all_formats_integration(self):
        """✅ Test exporting reports in all formats"""
        self.client.force_authenticate(user=self.platform_admin)
        
        formats = ['csv', 'json']
        report_types = ['weekly', 'monthly']
        
        for report_type in report_types:
            for fmt in formats:
                print(f"\n{'='*60}")
                print(f"Testing: {report_type} report in {fmt} format")
                print(f"URL: /report/export/")
                print(f"Params: school_id={self.school1.id}, report_type={report_type}, export_format={fmt}")  # ← Updated
                print(f"User: {self.platform_admin.username} (role={self.platform_admin.role}, is_staff={self.platform_admin.is_staff})")
                
                response = self.client.get(
                    '/report/export/',
                    {
                        'school_id': self.school1.id,
                        'report_type': report_type,
                        'export_format': fmt  # ← Changed from 'format' to 'export_format'
                    }
                )
                
                print(f"Status: {response.status_code}")
                if response.status_code != 200:
                    print(f"Response: {response.data}")
                    print(f"Content-Type: {response.get('Content-Type', 'N/A')}")
                print(f"{'='*60}")
                
                self.assertEqual(response.status_code, status.HTTP_200_OK,
                            f"Failed for {report_type} report in {fmt} format")
            
    def test_export_single_request(self):
        """Test a single export request"""
        self.client.force_authenticate(user=self.platform_admin)
        
        print(f"\nAuthenticated user: {self.platform_admin}")
        print(f"School ID: {self.school1.id}")
        
        # Test JSON
        response = self.client.get(
            '/report/export/',
            {
                'school_id': self.school1.id,
                'report_type': 'weekly',
                'export_format': 'json'  # ← Changed from 'format'
            }
        )
        
        print(f"JSON Response Status: {response.status_code}")
        if response.status_code != 200:
            print(f"JSON Response Data: {response.data}")
        
        self.assertEqual(response.status_code, 200)
        
        # Test CSV
        response = self.client.get(
            '/report/export/',
            {
                'school_id': self.school1.id,
                'report_type': 'weekly',
                'export_format': 'csv'  # ← Changed from 'format'
            }
        )
        
        print(f"CSV Response Status: {response.status_code}")
        if response.status_code != 200:
            print(f"CSV Response Data: {response.data}")
        else:
            print(f"CSV Content-Type: {response.get('Content-Type')}")
            print(f"CSV first 200 chars: {response.content[:200]}")
        
        self.assertEqual(response.status_code, 200)



    def test_debug_export(self):
        """Debug test to understand the 404 issue"""
        self.client.force_authenticate(user=self.platform_admin)
        
        print(f"\n{'='*60}")
        print("DEBUGGING EXPORT ENDPOINT")
        print(f"{'='*60}")
        
        # Test 1: Check if endpoint exists with JSON
        print("\n1. Testing JSON format (works):")
        response = self.client.get(
            '/report/export/',
            {'school_id': self.school1.id, 'format': 'json'}
        )
        print(f"   Status: {response.status_code}")
        print(f"   Content-Type: {response.get('Content-Type', 'N/A')}")
        
        # Test 2: Check with CSV format parameter
        print("\n2. Testing CSV format parameter:")
        response = self.client.get(
            '/report/export/',
            {'school_id': self.school1.id, 'format': 'csv'}
        )
        print(f"   Status: {response.status_code}")
        if response.status_code == 404:
            print(f"   Response data: {response.data}")
        print(f"   Content-Type: {response.get('Content-Type', 'N/A')}")
        
        # Test 3: Try with Accept header
        print("\n3. Testing with Accept header (text/csv):")
        response = self.client.get(
            '/report/export/',
            {'school_id': self.school1.id, 'format': 'csv'},
            HTTP_ACCEPT='text/csv'
        )
        print(f"   Status: {response.status_code}")
        if response.status_code == 404:
            print(f"   Response data: {response.data}")
        print(f"   Content-Type: {response.get('Content-Type', 'N/A')}")
        
        # Test 4: Check available routes
        print("\n4. Checking router registered routes:")
        from django.urls import get_resolver
        resolver = get_resolver()
        
        print("   Looking for 'report' related URLs:")
        for pattern in resolver.url_patterns:
            pattern_str = str(pattern.pattern)
            if 'report' in pattern_str.lower():
                print(f"   - {pattern_str}")
        
        # Test 5: Try without format parameter
        print("\n5. Testing without format parameter (default should be csv):")
        response = self.client.get(
            '/report/export/',
            {'school_id': self.school1.id}
        )
        print(f"   Status: {response.status_code}")
        if response.status_code == 404:
            print(f"   Response data: {response.data}")
        print(f"   Content-Type: {response.get('Content-Type', 'N/A')}")
        
        print(f"\n{'='*60}")
        print("END DEBUG")
        print(f"{'='*60}\n")
    # ==================== CLEANUP TESTS ====================

    def test_teardown_cleans_up_properly(self):
        """✅ Test that tearDown method properly cleans up test data"""
        # Verify initial state
        self.assertGreater(User.objects.count(), 0)
        self.assertGreater(DrivingSchool.objects.count(), 0)
        
        # Run teardown
        self.tearDown()
        
        # Verify cleanup
        self.assertEqual(User.objects.count(), 0)
        self.assertEqual(DrivingSchool.objects.count(), 0)
        self.assertEqual(SchoolAnalytics.objects.count(), 0)
        # Add more assertions as needed


if __name__ == '__main__':
    # Allow running tests directly
    import unittest
    unittest.main()
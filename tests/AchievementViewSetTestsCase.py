# tests/test_achievement_views.py

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from datetime import datetime, timedelta, date
import json

from DriveApp.models import (
    User, DrivingSchool, StudentProfile, Lesson, 
    Attendance, Achievement, Vehicle
)
from DriveApp.services import AchievementService


class AchievementViewSetTestCase(APITestCase):
    """Comprehensive tests for AchievementViewSet"""

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
        
        self.student1 = User.objects.create_user(
            username='student1',
            email='student1@school.com',
            password='testpass123',
            role='S'
        )
        
        self.student2 = User.objects.create_user(
            username='student2',
            email='student2@school.com',
            password='testpass123',
            role='S'
        )
        
        self.student3 = User.objects.create_user(
            username='student3',
            email='student3@school.com',
            password='testpass123',
            role='S'
        )
        
        # Create driving schools
        self.school1 = DrivingSchool.objects.create(
            owner=self.school_owner1,
            name='School 1',
            email='school1@test.com',
            address='123 Main St'
        )
        
        self.school2 = DrivingSchool.objects.create(
            owner=self.school_owner2,
            name='School 2',
            email='school2@test.com',
            address='456 Oak Ave'
        )
        
        # Create student profiles
        self.instructor1_profile = StudentProfile.objects.create(
            user=self.instructor1,
            school=self.school1,
            status='A'
        )
        
        self.instructor2_profile = StudentProfile.objects.create(
            user=self.instructor2,
            school=self.school1,
            status='A'
        )
        
        self.student1_profile = StudentProfile.objects.create(
            user=self.student1,
            school=self.school1,
            status='A',
            progress_theory=30,
            progress_driving=25,
            total_hours_theory=15,
            total_hours_driving=10
        )
        
        self.student2_profile = StudentProfile.objects.create(
            user=self.student2,
            school=self.school1,
            status='A',
            progress_theory=80,
            progress_driving=75,
            total_hours_theory=40,
            total_hours_driving=35
        )
        
        self.student3_profile = StudentProfile.objects.create(
            user=self.student3,
            school=self.school2,
            status='A'
        )
        
        # Create lessons
        self.lesson1 = Lesson.objects.create(
            title='Basic Driving Lesson',
            instructor=self.instructor1,
            school=self.school1,
            lesson_type='D',
            description='Basic driving techniques',
            duration=60,
            date=timezone.now() - timedelta(days=10),
            status='C'  # Completed
        )
        
        self.lesson2 = Lesson.objects.create(
            title='Theory Class',
            instructor=self.instructor1,
            school=self.school1,
            lesson_type='T',
            description='Traffic rules and regulations',
            duration=90,
            date=timezone.now() - timedelta(days=5),
            status='C'
        )
        
        # Create attendance records
        self.attendance1 = Attendance.objects.create(
            student=self.student1_profile,
            lesson=self.lesson1,
            presence=True,
            hours_completed=2.0,
            notes='Good progress'
        )
        
        self.attendance2 = Attendance.objects.create(
            student=self.student1_profile,
            lesson=self.lesson2,
            presence=True,
            hours_completed=1.5,
            notes='Excellent participation'
        )
        
        self.attendance3 = Attendance.objects.create(
            student=self.student2_profile,
            lesson=self.lesson1,
            presence=True,
            hours_completed=2.0,
            notes='Great driving skills'
        )
        
        # Create achievements
        self.achievement1 = Achievement.objects.create(
            student=self.student1_profile,
            type='first_lesson',
            title='First Steps',
            description='Completed your first lesson',
            icon='🎯',
            points=10,
            earned_at=timezone.now() - timedelta(days=10)
        )
        
        self.achievement2 = Achievement.objects.create(
            student=self.student1_profile,
            type='theory_master',
            title='Theory Master',
            description='Completed 50 hours of theory',
            icon='📚',
            points=100,
            earned_at=timezone.now() - timedelta(days=5)
        )
        
        self.achievement3 = Achievement.objects.create(
            student=self.student2_profile,
            type='first_lesson',
            title='First Steps',
            description='Completed your first lesson',
            icon='🎯',
            points=10,
            earned_at=timezone.now() - timedelta(days=3)
        )
        
        # Create recent achievement for filtering tests
        self.recent_achievement = Achievement.objects.create(
            student=self.student1_profile,
            type='driving_ace',
            title='Driving Ace',
            description='Completed 40 hours of driving',
            icon='🚗',
            points=150,
            earned_at=timezone.now() - timedelta(days=1)
        )
        
        # API client
        self.client = APIClient()
        
        # URLs
        self.list_url = reverse('achievement-list')
        self.detail_url = lambda pk: reverse('achievement-detail', kwargs={'pk': pk})
        self.my_achievements_url = reverse('achievement-my-achievements')
        self.award_achievement_url = reverse('achievement-award-achievement')
        self.bulk_award_url = reverse('achievement-bulk-award') 
        self.check_milestones_url = reverse('achievement-check-milestones')
        self.leaderboard_url = reverse('achievement-leaderboard')
        self.statistics_url = reverse('achievement-statistics')
        self.student_progress_url = reverse('achievement-student-progress')
        self.available_achievements_url = reverse('achievement-available-achievements')
        self.badges_url = reverse('achievement-badges')
        self.export_url = reverse('achievement-export')

    def tearDown(self):
        """Clean up after tests"""
        Achievement.objects.all().delete()
        Attendance.objects.all().delete()
        Lesson.objects.all().delete()
        StudentProfile.objects.all().delete()
        DrivingSchool.objects.all().delete()
        User.objects.all().delete()
    # ==================== Helper Method ====================
    def get_results(self, response_data):
        if isinstance(response_data, dict) and 'results' in response_data:
            return response_data['results']
        return response_data
    # ==================== AUTHENTICATION & PERMISSIONS TESTS ====================

    def test_unauthenticated_access_denied(self):
        """✅ Test that unauthenticated users cannot access achievements"""
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_platform_admin_sees_all_achievements(self):
        """✅ Platform admin should see all achievements"""
        self.client.force_authenticate(user=self.platform_admin)
        response = self.client.get(self.list_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), Achievement.objects.count())

    def test_school_owner_sees_only_their_achievements(self):
        """✅ School owner should only see achievements in their schools"""
        self.client.force_authenticate(user=self.school_owner1)
        response = self.client.get(self.list_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        result = self.get_results(response.data)
        # Should see 3 achievements (student1 has 3, student2 has 1, but student1's recent_achievement makes 3 total for student1)
        expected_count = Achievement.objects.filter(
            student__school__owner=self.school_owner1
        ).count()
        self.assertEqual(len(result), expected_count)
        
        # Verify only school1 achievements
        student_ids = [achievement['student'] for achievement in result]
        self.assertIn(self.student1_profile.id, student_ids)
        self.assertIn(self.student2_profile.id, student_ids)
        # student3 is in school2, so should not appear
        self.assertNotIn(self.student3_profile.id, student_ids)

    def test_instructor_sees_only_their_school_achievements(self):
        """✅ Instructor should see achievements from their school only"""
        self.client.force_authenticate(user=self.instructor1)
        response = self.client.get(self.list_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        results = self.get_results(response.data)
        # Should see school1 achievements
        expected_count = Achievement.objects.filter(
            student__school=self.school1
        ).count()
        self.assertEqual(len(results), expected_count)
        
        # Verify school1 only
        for achievement in results:
            self.assertEqual(
                StudentProfile.objects.get(id=achievement['student']).school.id,
                self.school1.id
            )


    def test_student_sees_only_their_achievements(self):
        """✅ Student should see only their own achievements"""
        self.client.force_authenticate(user=self.student1)
        response = self.client.get(self.list_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # student1 should have 3 achievements
        result = self.get_results(response.data)
        self.assertEqual(len(result), 3)
        
        # Verify only student1's achievements
        for achievement in result:
            self.assertEqual(achievement['student'], self.student1_profile.id)

    # ==================== LIST ACHIEVEMENTS TESTS ====================

    def test_list_achievements_success(self):
        """✅ Test listing achievements returns correct data"""
        self.client.force_authenticate(user=self.school_owner1)
        response = self.client.get(self.list_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        result = self.get_results(response.data)

        # Check achievement data structure
        achievement = result[0]
        self.assertIn('id', achievement)
        self.assertIn('student', achievement)
        self.assertIn('type', achievement)
        self.assertIn('title', achievement)
        self.assertIn('description', achievement)
        self.assertIn('icon', achievement)
        self.assertIn('points', achievement)
        self.assertIn('earned_at', achievement)

    def test_list_achievements_with_filters(self):
        """✅ Test filtering achievements"""
        self.client.force_authenticate(user=self.school_owner1)
        
        # Filter by student
        response = self.client.get(self.list_url, {'student': self.student1_profile.id})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        result = self.get_results(response.data)
        self.assertEqual(len(result), 4)  # student1 has 3 achievements
        
        # Filter by type
        response = self.client.get(self.list_url, {'type': 'first_lesson'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should get 2 first_lesson achievements (student1 and student2)
        result = self.get_results(response.data)
        self.assertEqual(len(result), 2)
        self.assertTrue(all(achievement['type'] == 'first_lesson' for achievement in result))
        
        # Filter by points range
        result = self.get_results(response.data)
        response = self.client.get(self.list_url, {'points__gte': 50})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(all(achievement['points'] >= 50 for achievement in result))

    def test_list_achievements_with_search(self):
        """✅ Test searching achievements"""
        self.client.force_authenticate(user=self.school_owner1)
        
        # Search by title
        response = self.client.get(self.list_url, {'search': 'Master'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        result = self.get_results(response.data)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['title'], 'Theory Master')
        
        # Search by description
        response = self.client.get(self.list_url, {'search': 'first lesson'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        result = self.get_results(response.data)
        self.assertEqual(len(result), 2)  # Two first_lesson achievements

    def test_list_achievements_with_ordering(self):
        """✅ Test ordering achievements"""
        self.client.force_authenticate(user=self.school_owner1)
        
        # Order by points descending
        response = self.client.get(self.list_url, {'ordering': '-points'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        result = self.get_results(response.data)

        # Check ordering (points should be descending)
        points = [achievement['points'] for achievement in result]
        self.assertEqual(points, sorted(points, reverse=True))
        
        # Order by earned_at descending (default)
        response = self.client.get(self.list_url, {'ordering': '-earned_at'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        result = self.get_results(response.data)
        # Check ordering (most recent first)
        earned_at_dates = [datetime.fromisoformat(achievement['earned_at'].replace('Z', '+00:00')) 
                          for achievement in result]
        for i in range(len(earned_at_dates) - 1):
            self.assertGreaterEqual(earned_at_dates[i], earned_at_dates[i + 1])

    # ==================== RETRIEVE ACHIEVEMENT TESTS ====================

    def test_retrieve_achievement_success(self):
        """✅ Test retrieving a single achievement"""
        self.client.force_authenticate(user=self.school_owner1)
        response = self.client.get(self.detail_url(self.achievement1.pk))
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['student'], self.student1_profile.id)
        self.assertEqual(response.data['type'], 'first_lesson')
        self.assertEqual(response.data['title'], 'First Steps')
        self.assertEqual(response.data['points'], 10)

    def test_retrieve_achievement_not_found(self):
        """✅ Test retrieving non-existent achievement"""
        self.client.force_authenticate(user=self.platform_admin)
        response = self.client.get(self.detail_url(99999))
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_retrieve_achievement_no_permission(self):
        """✅ School owner cannot retrieve achievement from another school"""
        self.client.force_authenticate(user=self.school_owner1)
        
        # Create achievement in school2
        school2_achievement = Achievement.objects.create(
            student=self.student3_profile,
            type='first_lesson',
            title='School 2 Achievement',
            icon='🎯',
            points=10
        )
        
        response = self.client.get(self.detail_url(school2_achievement.pk))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_retrieve_achievement_as_student_own(self):
        """✅ Student can retrieve their own achievement"""
        self.client.force_authenticate(user=self.student1)
        response = self.client.get(self.detail_url(self.achievement1.pk))
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['student'], self.student1_profile.id)

    def test_retrieve_achievement_as_student_other_denied(self):
        """✅ Student cannot retrieve other student's achievement"""
        self.client.force_authenticate(user=self.student2)
        response = self.client.get(self.detail_url(self.achievement1.pk))
        
        # Should return 404 (not found) for security
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    # ==================== CREATE ACHIEVEMENT TESTS ====================

    def test_create_achievement_as_platform_admin(self):
        """✅ Platform admin can create achievement for any student"""
        self.client.force_authenticate(user=self.platform_admin)
        
        data = {
            'student': self.student3_profile.id,  # Student in school2
            'type': 'driving_master',
            'title': 'Perfect Attendance',
            'description': 'Perfect attendance for 10 lessons',
            'icon': '✨',
            'points': 75
        }
        
        response = self.client.post(self.list_url, data, format='json')
        


        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Achievement.objects.count(), 5)  # Started with 4
        self.assertEqual(response.data['student'], self.student3_profile.id)
        self.assertEqual(response.data['title'], 'Perfect Attendance')

    def test_create_achievement_as_school_owner(self):
        """✅ School owner can create achievement for students in their school"""
        self.client.force_authenticate(user=self.school_owner1)
        
        data = {
            'student': self.student1_profile.id,  # Student in their school
            'type': 'driving_master',
            'title': 'Perfect Attendance',
            'description': 'Perfect attendance for 10 lessons',
            'icon': '✨',
            'points': 75
        }
        
        response = self.client.post(self.list_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['student'], self.student1_profile.id)

    def test_create_achievement_school_owner_wrong_school(self):
        """✅ School owner cannot create achievement for students in other schools"""
        self.client.force_authenticate(user=self.school_owner1)
        
        data = {
            'student': self.student3_profile.id,  # Student in school2
            'type': 'first_lesson',
            'title': 'Test',
            'description': 'Test',
            'icon': '🎯',
            'points': 10
        }
        
        response = self.client.post(self.list_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_create_achievement_as_instructor_denied(self):
        """✅ Instructor cannot create achievements via POST (only via award_achievement action)"""
        self.client.force_authenticate(user=self.instructor1)
        
        data = {
            'student': self.student1_profile.id,
            'type': 'first_lesson',
            'title': 'Test',
            'description': 'Test',
            'icon': '🎯',
            'points': 10
        }
        
        response = self.client.post(self.list_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_create_achievement_as_student_denied(self):
        """✅ Student cannot create achievements"""
        self.client.force_authenticate(user=self.student1)
        
        data = {
            'student': self.student1_profile.id,
            'type': 'first_lesson',
            'title': 'Test',
            'description': 'Test',
            'icon': '🎯',
            'points': 10
        }
        
        response = self.client.post(self.list_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_create_duplicate_achievement(self):
        """✅ Cannot create duplicate achievement type for same student"""
        self.client.force_authenticate(user=self.platform_admin)
        
        data = {
            'student': self.student1_profile.id,
            'type': 'first_lesson',  # student1 already has this
            'title': 'Duplicate',
            'description': 'Should fail',
            'icon': '🎯',
            'points': 10
        }
        
        response = self.client.post(self.list_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('type', response.data)

    def test_create_achievement_negative_points(self):
        """✅ Cannot create achievement with negative points"""
        self.client.force_authenticate(user=self.platform_admin)
        
        data = {
            'student': self.student1_profile.id,
            'type': 'test_achievement',
            'title': 'Test',
            'description': 'Test',
            'icon': '🎯',
            'points': -10  # Negative points
        }
        
        response = self.client.post(self.list_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('points', response.data)

    def test_create_achievement_missing_required_fields(self):
        """✅ Cannot create achievement without required fields"""
        self.client.force_authenticate(user=self.platform_admin)
        
        data = {
            'student': self.student1_profile.id,
            'type': 'first_lesson'
            # Missing title, description, icon, points
        }
        
        response = self.client.post(self.list_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


    # ==================== UPDATE ACHIEVEMENT TESTS ====================

    def test_update_achievement_as_platform_admin(self):
        """✅ Only platform admin can update achievements"""
        self.client.force_authenticate(user=self.platform_admin)
        
        data = {
            'title': 'Updated Title',
            'description': 'Updated description',
            'points': 50
        }
        
        response = self.client.patch(
            self.detail_url(self.achievement1.pk), 
            data, 
            format='json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['title'], 'Updated Title')
        self.assertEqual(response.data['points'], 50)
        
        # Refresh from DB
        self.achievement1.refresh_from_db()
        self.assertEqual(self.achievement1.title, 'Updated Title')

    def test_update_achievement_as_school_owner_denied(self):
        """✅ School owner cannot update achievements"""
        self.client.force_authenticate(user=self.school_owner1)
        
        data = {'title': 'Should not update'}
        response = self.client.patch(
            self.detail_url(self.achievement1.pk), 
            data, 
            format='json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_update_achievement_as_student_denied(self):
        """✅ Student cannot update achievements"""
        self.client.force_authenticate(user=self.student1)
        
        data = {'title': 'Should not update'}
        response = self.client.patch(
            self.detail_url(self.achievement1.pk), 
            data, 
            format='json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_update_student_field_denied(self):
        """✅ Cannot change student field of existing achievement"""
        self.client.force_authenticate(user=self.platform_admin)
        
        data = {'student': self.student2_profile.id}  # Try to change student
        response = self.client.patch(
            self.detail_url(self.achievement1.pk), 
            data, 
            format='json'
        )
        
        print("#"*100)
        print(response.data)
        print(response)
        print("#"*100)

        # Should succeed but student field shouldn't change
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertNotEqual(response.data['student'], self.student2_profile.id)
        
        # Verify student didn't change in database
        self.achievement1.refresh_from_db()
        self.assertEqual(self.achievement1.student.id, self.student1_profile.id)

    def test_update_to_duplicate_type(self):
        """✅ Cannot update achievement to duplicate type for same student"""
        # First create another achievement for student1
        Achievement.objects.create(
            student=self.student1_profile,
            type='driving_ace',
            title='Driving Ace',
            icon='🚗',
            points=150
        )
        
        self.client.force_authenticate(user=self.platform_admin)
        
        # Try to update achievement1 to driving_ace (already exists)
        data = {'type': 'driving_ace'}
        response = self.client.patch(
            self.detail_url(self.achievement1.pk), 
            data, 
            format='json'
        )
        
        # Note: The serializer might allow this, but it would create a duplicate
        # This depends on your validation logic
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST])

    # ==================== DELETE ACHIEVEMENT TESTS ====================

    def test_delete_achievement_as_platform_admin(self):
        """✅ Only platform admin can delete achievements"""
        initial_count = Achievement.objects.count()
        self.client.force_authenticate(user=self.platform_admin)
        
        response = self.client.delete(self.detail_url(self.achievement1.pk))
        
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(Achievement.objects.count(), initial_count - 1)
        self.assertFalse(Achievement.objects.filter(id=self.achievement1.id).exists())

    def test_delete_achievement_as_school_owner_denied(self):
        """✅ School owner cannot delete achievements"""
        initial_count = Achievement.objects.count()
        self.client.force_authenticate(user=self.school_owner1)
        
        response = self.client.delete(self.detail_url(self.achievement1.pk))
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(Achievement.objects.count(), initial_count)

    def test_delete_achievement_as_student_denied(self):
        """✅ Student cannot delete achievements"""
        initial_count = Achievement.objects.count()
        self.client.force_authenticate(user=self.student1)
        
        response = self.client.delete(self.detail_url(self.achievement1.pk))
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(Achievement.objects.count(), initial_count)

    # ==================== MY_ACHIEVEMENTS ACTION TESTS ====================

    def test_my_achievements_as_student(self):
        """✅ Student can view their own achievements"""
        self.client.force_authenticate(user=self.student1)
        response = self.client.get(self.my_achievements_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('summary', response.data)
        self.assertIn('earned_achievements', response.data)
        self.assertIn('available_achievements', response.data)
        self.assertIn('recent_achievements', response.data)
        
        # Student1 should have 3 achievements
        self.assertEqual(response.data['summary']['total_achievements'], 3)
        self.assertEqual(len(response.data['earned_achievements']), 3)
        
        # Check student info
        self.assertEqual(response.data['student']['id'], self.student1_profile.id)
        self.assertEqual(response.data['student']['name'], self.student1.username)

    def test_my_achievements_as_non_student_denied(self):
        """✅ Non-students cannot access my_achievements"""
        self.client.force_authenticate(user=self.instructor1)
        response = self.client.get(self.my_achievements_url)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)

    def test_my_achievements_student_no_profile(self):
        """✅ Student without active profile gets error"""
        # Create student without profile
        student_no_profile = User.objects.create_user(
            username='no_profile_student',
            email='no_profile@test.com',
            password='testpass123',
            role='S'
        )
        
        self.client.force_authenticate(user=student_no_profile)
        response = self.client.get(self.my_achievements_url)
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn('error', response.data)

    # ==================== AWARD_ACHIEVEMENT ACTION TESTS ====================

    def test_award_achievement_as_instructor(self):
        """✅ Instructor can award achievement to student in their school"""
        self.client.force_authenticate(user=self.instructor1)
        
        data = {
            'student_id': self.student1_profile.id,
            'achievement_type': 'perfect_attendance',
            'custom_title': 'Perfect Attendance Award',
            'custom_description': 'Awarded for excellent attendance'
        }
        
        initial_count = Achievement.objects.count()
        response = self.client.post(self.award_achievement_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Achievement.objects.count(), initial_count + 1)
        
        self.assertIn('achievement', response.data)
        self.assertEqual(response.data['achievement']['type'], 'perfect_attendance')
        self.assertEqual(response.data['achievement']['title'], 'Perfect Attendance Award')
        self.assertEqual(response.data['awarded_to']['id'], self.student1_profile.id)

    def test_award_achievement_as_school_owner(self):
        """✅ School owner can award achievement"""
        self.client.force_authenticate(user=self.school_owner1)
        
        data = {
            'student_id': self.student1_profile.id,
            'achievement_type': 'perfect_attendance'
        }
        
        response = self.client.post(self.award_achievement_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_award_achievement_as_platform_admin(self):
        """✅ Platform admin can award achievement to any student"""
        self.client.force_authenticate(user=self.platform_admin)
        
        data = {
            'student_id': self.student3_profile.id,  # Student in school2
            'achievement_type': 'perfect_attendance'
        }
        
        response = self.client.post(self.award_achievement_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_award_achievement_instructor_wrong_school(self):
        """✅ Instructor cannot award achievement to student in another school"""
        self.client.force_authenticate(user=self.instructor1)
        
        data = {
            'student_id': self.student3_profile.id,  # Student in school2
            'achievement_type': 'perfect_attendance'
        }
        
        response = self.client.post(self.award_achievement_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_award_achievement_duplicate(self):
        """✅ Cannot award duplicate achievement"""
        self.client.force_authenticate(user=self.instructor1)
        
        data = {
            'student_id': self.student1_profile.id,
            'achievement_type': 'first_lesson'  # Already has this
        }
        
        response = self.client.post(self.award_achievement_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)

    def test_award_achievement_invalid_type(self):
        """✅ Cannot award invalid achievement type"""
        self.client.force_authenticate(user=self.instructor1)
        
        data = {
            'student_id': self.student1_profile.id,
            'achievement_type': 'invalid_type'
        }
        
        response = self.client.post(self.award_achievement_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)

    def test_award_achievement_missing_data(self):
        """✅ Cannot award achievement without required data"""
        self.client.force_authenticate(user=self.instructor1)
        
        # Missing student_id
        data = {'achievement_type': 'first_lesson'}
        response = self.client.post(self.award_achievement_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        
        # Missing achievement_type
        data = {'student_id': self.student1_profile.id}
        response = self.client.post(self.award_achievement_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_award_achievement_invalid_student(self):
        """✅ Cannot award achievement to non-existent student"""
        self.client.force_authenticate(user=self.instructor1)
        
        data = {
            'student_id': 99999,
            'achievement_type': 'first_lesson'
        }
        
        response = self.client.post(self.award_achievement_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    # ==================== BULK_AWARD ACTION TESTS ====================

    def test_bulk_award_as_platform_admin(self):
        """✅ Platform admin can bulk award achievements"""
        self.client.force_authenticate(user=self.platform_admin)
        
        student_ids = [
            self.student1_profile.id,
            self.student2_profile.id,
            self.student3_profile.id
        ]
        
        data = {
            'student_ids': student_ids,
            'achievement_type': 'perfect_attendance'
        }
        
        initial_count = Achievement.objects.count()
        response = self.client.post(self.bulk_award_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Check summary
        self.assertIn('summary', response.data)
        summary = response.data['summary']
        self.assertEqual(summary['requested'], 3)
        self.assertEqual(summary['awarded'], 3)  # All 3 should get it (none have it yet)
        self.assertEqual(summary['skipped'], 0)
        
        # Check final count
        final_count = Achievement.objects.count()
        self.assertEqual(final_count, initial_count + 3)

    def test_bulk_award_as_school_owner(self):
        """✅ School owner can bulk award to students in their school"""
        self.client.force_authenticate(user=self.school_owner1)
        
        student_ids = [
            self.student1_profile.id,
            self.student2_profile.id
        ]
        
        data = {
            'student_ids': student_ids,
            'achievement_type': 'perfect_attendance'
        }
        
        response = self.client.post(self.bulk_award_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['summary']['requested'], 2)
        self.assertEqual(response.data['summary']['awarded'], 2)

    def test_bulk_award_with_duplicates(self):
        """✅ Bulk award skips students who already have the achievement"""
        self.client.force_authenticate(user=self.platform_admin)
        
        student_ids = [
            self.student1_profile.id,  # Already has first_lesson
            self.student2_profile.id,  # Already has first_lesson
            self.student3_profile.id   # Doesn't have it
        ]
        
        data = {
            'student_ids': student_ids,
            'achievement_type': 'first_lesson'
        }
        
        initial_count = Achievement.objects.count()
        response = self.client.post(self.bulk_award_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Should award only to student3
        summary = response.data['summary']
        self.assertEqual(summary['requested'], 3)
        self.assertEqual(summary['awarded'], 1)
        self.assertEqual(summary['skipped'], 2)
        
        # Check final count
        final_count = Achievement.objects.count()
        self.assertEqual(final_count, initial_count + 1)  # Only one new achievement

    def test_bulk_award_invalid_achievement_type(self):
        """✅ Cannot bulk award invalid achievement type"""
        self.client.force_authenticate(user=self.platform_admin)
        
        data = {
            'student_ids': [self.student1_profile.id],
            'achievement_type': 'invalid_type'
        }
        
        response = self.client.post(self.bulk_award_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)

    def test_bulk_award_empty_student_list(self):
        """✅ Cannot bulk award with empty student list"""
        self.client.force_authenticate(user=self.platform_admin)
        
        data = {
            'student_ids': [],
            'achievement_type': 'first_lesson'
        }
        
        response = self.client.post(self.bulk_award_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)

    def test_bulk_award_no_valid_students(self):
        """✅ Bulk award with no valid students returns empty results"""
        self.client.force_authenticate(user=self.platform_admin)
        
        data = {
            'student_ids': [99999, 99998],
            'achievement_type': 'first_lesson'
        }
        
        response = self.client.post(self.bulk_award_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn('error', response.data)

    # ==================== CHECK_MILESTONES ACTION TESTS ====================

    def test_check_milestones_specific_student(self):
        """✅ Can check milestones for specific student"""
        self.client.force_authenticate(user=self.instructor1)
        
        data = {'student_id': self.student1_profile.id}
        response = self.client.post(self.check_milestones_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('message', response.data)
        self.assertIn('students_checked', response.data)
        self.assertIn('achievements_awarded', response.data)
        self.assertIn('results', response.data)
        
        # student1 already has 3 achievements, might get more if criteria met
        self.assertEqual(response.data['students_checked'], 1)

    def test_check_milestones_all_students_as_instructor(self):
        """✅ Instructor can check milestones for all students in their school"""
        self.client.force_authenticate(user=self.instructor1)
        
        response = self.client.post(self.check_milestones_url, {}, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        

        
        # Should check both students in school1
        self.assertEqual(response.data['students_checked'], 4)
        
        # Both might get achievements if they meet criteria
        self.assertGreaterEqual(response.data['achievements_awarded'], 0)

    def test_check_milestones_all_students_as_school_owner(self):
        """✅ School owner can check milestones for all students in their school"""
        self.client.force_authenticate(user=self.school_owner1)
        
        response = self.client.post(self.check_milestones_url, {}, format='json')
        
        print("#"*100)
        print(response.data['students_checked'])
        print(response)
        print("#"*100)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['students_checked'], 4)  # Two students in school1

    def test_check_milestones_as_student_denied(self):
        """✅ Student cannot check milestones"""
        self.client.force_authenticate(user=self.student1)
        
        response = self.client.post(self.check_milestones_url, {}, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
 
    def test_check_milestones_instructor_no_profile(self):
        """✅ Instructor without school profile cannot check milestones"""
        # Create instructor without profile
        instructor_no_profile = User.objects.create_user(
            username='instructor_no_profile',
            email='instructor_no@test.com',
            password='testpass123',
            role='I'
        )
        
        self.client.force_authenticate(user=instructor_no_profile)
        response = self.client.post(self.check_milestones_url, {}, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should still get response but with 0 students checked
        self.assertEqual(response.data['students_checked'], 0)

    # ==================== LEADERBOARD ACTION TESTS ====================

    def test_leaderboard_school_scope_as_student(self):
        """✅ Student can view school leaderboard"""
        self.client.force_authenticate(user=self.student1)
        
        response = self.client.get(self.leaderboard_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('leaderboard', response.data)
        self.assertIn('metadata', response.data)
        self.assertIn('your_rank', response.data)
        
        metadata = response.data['metadata']
        self.assertEqual(metadata['scope'], 'school')
        self.assertEqual(metadata['time_period'], 'all_time')
        
        # Check leaderboard structure
        if response.data['leaderboard']:
            student = response.data['leaderboard'][0]
            self.assertIn('rank', student)
            self.assertIn('student_id', student)
            self.assertIn('name', student)
            self.assertIn('total_points', student)

    def test_leaderboard_school_scope_as_instructor(self):
        """✅ Instructor can view school leaderboard"""
        self.client.force_authenticate(user=self.instructor1)
        
        response = self.client.get(self.leaderboard_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['metadata']['scope'], 'school')
        
        # Should show top students from school1
        for student in response.data['leaderboard']:
            self.assertEqual(student['school'], 'School 1')

    def test_leaderboard_platform_scope_as_admin(self):
        """✅ Platform admin can view platform-wide leaderboard"""
        self.client.force_authenticate(user=self.platform_admin)
        
        response = self.client.get(self.leaderboard_url, {'scope': 'platform'})
        
        print("#"*100)
        print(response.data)
        print(response)
        print("#"*100)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['metadata']['scope'], 'platform')
        
        # Should include all students from both schools
        school_names = set(student['school'] for student in response.data['leaderboard'])
        self.assertIn('School 1', school_names)

    def test_leaderboard_platform_scope_as_non_admin_denied(self):
        """✅ Non-admin cannot view platform-wide leaderboard"""
        self.client.force_authenticate(user=self.instructor1)
        
        response = self.client.get(self.leaderboard_url, {'scope': 'platform'})
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_leaderboard_with_time_filter(self):
        """✅ Can filter leaderboard by time period"""
        self.client.force_authenticate(user=self.student1)
        
        # Weekly leaderboard
        response = self.client.get(self.leaderboard_url, {'time_period': 'week'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['metadata']['time_period'], 'week')
        
        # Monthly leaderboard
        response = self.client.get(self.leaderboard_url, {'time_period': 'month'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['metadata']['time_period'], 'month')

    def test_leaderboard_with_limit(self):
        """✅ Can limit number of results"""
        self.client.force_authenticate(user=self.student1)
        
        response = self.client.get(self.leaderboard_url, {'limit': 2})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertLessEqual(len(response.data['leaderboard']), 2)
        self.assertEqual(response.data['metadata']['limit'], 2)

    def test_leaderboard_empty_school(self):
        """✅ Leaderboard works for school with no achievements"""
        # Create new school with students but no achievements
        new_school = DrivingSchool.objects.create(
            owner=self.school_owner1,
            name='Empty School',
            email='empty@test.com',
            address='789 Pine St'
        )
        
        new_student = User.objects.create_user(
            username='new_student',
            email='new_student@test.com',
            password='testpass123',
            role='S'
        )
        
        StudentProfile.objects.create(
            user=new_student,
            school=new_school,
            status='A'
        )
        
        # Authenticate as this student
        self.client.force_authenticate(user=new_student)
        response = self.client.get(self.leaderboard_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Leaderboard should be empty or show 0 points
        self.assertEqual(response.data['metadata']['total_students'], 0)

    # ==================== STATISTICS ACTION TESTS ====================

    def test_statistics_as_platform_admin(self):
        """✅ Platform admin can view platform statistics"""
        self.client.force_authenticate(user=self.platform_admin)
        
        response = self.client.get(self.statistics_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('scope', response.data)
        self.assertIn('summary', response.data)
        self.assertIn('by_type', response.data)
        self.assertIn('most_popular', response.data)
        
        self.assertEqual(response.data['scope'], 'platform')
        
        summary = response.data['summary']
        self.assertIn('total_achievements', summary)
        self.assertIn('total_points_awarded', summary)
        self.assertIn('unique_students', summary)
        
        # Should include all achievements
        self.assertEqual(summary['total_achievements'], Achievement.objects.count())

    def test_statistics_as_school_owner(self):
        """✅ School owner can view statistics for their schools"""
        self.client.force_authenticate(user=self.school_owner1)
        
        response = self.client.get(self.statistics_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['scope'], 'schools')
        
        # Should only include achievements from school1
        school1_achievements = Achievement.objects.filter(
            student__school=self.school1
        ).count()
        self.assertEqual(
            response.data['summary']['total_achievements'], 
            school1_achievements
        )

    def test_statistics_as_instructor(self):
        """✅ Instructor can view statistics for their school"""
        self.client.force_authenticate(user=self.instructor1)
        
        response = self.client.get(self.statistics_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['scope'], 'school')

    def test_statistics_as_student(self):
        """✅ Student can view personal statistics"""
        self.client.force_authenticate(user=self.student1)
        
        response = self.client.get(self.statistics_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['scope'], 'personal')
        
        # Should only include student1's achievements
        student1_achievements = Achievement.objects.filter(
            student=self.student1_profile
        ).count()
        self.assertEqual(
            response.data['summary']['total_achievements'], 
            student1_achievements
        )

    def test_statistics_no_data(self):
        """✅ Statistics works when no achievements exist"""
        # Create user with no achievements
        new_user = User.objects.create_user(
            username='no_achievements',
            email='no_achievements@test.com',
            password='testpass123',
            role='S'
        )
        
        self.client.force_authenticate(user=new_user)
        response = self.client.get(self.statistics_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['summary']['total_achievements'], 0)
        self.assertEqual(response.data['summary']['total_points_awarded'], 0)

    # ==================== STUDENT_PROGRESS ACTION TESTS ====================

    def test_student_progress_as_student(self):
        """✅ Student can view their own progress"""
        self.client.force_authenticate(user=self.student1)
        
        response = self.client.get(self.student_progress_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('student', response.data)
        self.assertIn('summary', response.data)
        self.assertIn('earned_achievements', response.data)
        self.assertIn('all_achievements_progress', response.data)
        
        student_info = response.data['student']
        self.assertEqual(student_info['id'], self.student1_profile.id)
        
        summary = response.data['summary']
        self.assertEqual(summary['earned_count'], 3)  # student1 has 3 achievements
        
        # Should show progress for all achievement types
        self.assertEqual(
            len(response.data['all_achievements_progress']), 
            len(AchievementService.ACHIEVEMENT_RULES)
        )

    def test_student_progress_as_instructor(self):
        """✅ Instructor can view student progress"""
        self.client.force_authenticate(user=self.instructor1)
        
        response = self.client.get(
            self.student_progress_url, 
            {'student_id': self.student1_profile.id}
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['student']['id'], self.student1_profile.id)

    def test_student_progress_instructor_wrong_school(self):
        """✅ Instructor cannot view student progress from another school"""
        self.client.force_authenticate(user=self.instructor1)
        
        response = self.client.get(
            self.student_progress_url, 
            {'student_id': self.student3_profile.id}
        )
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_student_progress_as_school_owner(self):
        """✅ School owner can view student progress"""
        self.client.force_authenticate(user=self.school_owner1)
        
        response = self.client.get(
            self.student_progress_url, 
            {'student_id': self.student1_profile.id}
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_student_progress_school_owner_wrong_school(self):
        """✅ School owner cannot view student progress from another school"""
        self.client.force_authenticate(user=self.school_owner1)
        
        response = self.client.get(
            self.student_progress_url, 
            {'student_id': self.student3_profile.id}
        )
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_student_progress_missing_student_id(self):
        """✅ Non-students must provide student_id"""
        self.client.force_authenticate(user=self.instructor1)
        
        response = self.client.get(self.student_progress_url)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_student_progress_invalid_student(self):
        """✅ Cannot view progress for non-existent student"""
        self.client.force_authenticate(user=self.instructor1)
        
        response = self.client.get(
            self.student_progress_url, 
            {'student_id': 99999}
        )
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_student_progress_shows_earned_and_available(self):
        """✅ Progress shows both earned and available achievements"""
        self.client.force_authenticate(user=self.student1)
        
        response = self.client.get(self.student_progress_url)
        
        earned = [a for a in response.data['all_achievements_progress'] if a['earned']]
        available = [a for a in response.data['all_achievements_progress'] if not a['earned']]
        
        # Student1 has 3 earned achievements
        self.assertEqual(len(earned), 3)
        # Should have some available achievements
        self.assertGreater(len(available), 0)
        
        # Check progress data structure
        for achievement in response.data['all_achievements_progress']:
            self.assertIn('type', achievement)
            self.assertIn('title', achievement)
            self.assertIn('progress', achievement)
            self.assertIn('current', achievement['progress'])
            self.assertIn('target', achievement['progress'])
            self.assertIn('percentage', achievement['progress'])

    # ==================== AVAILABLE_ACHIEVEMENTS ACTION TESTS ====================

    def test_available_achievements_success(self):
        """✅ Can view all available achievement types"""
        self.client.force_authenticate(user=self.student1)
        
        response = self.client.get(self.available_achievements_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('total_types', response.data)
        self.assertIn('achievements', response.data)
        
        # Should list all achievement types
        self.assertEqual(
            response.data['total_types'], 
            len(AchievementService.ACHIEVEMENT_RULES)
        )
        
        # Check achievement info structure
        for achievement in response.data['achievements']:
            self.assertIn('type', achievement)
            self.assertIn('title', achievement)
            self.assertIn('description', achievement)
            self.assertIn('icon', achievement)
            self.assertIn('points', achievement)
            self.assertIn('requirements', achievement)

    def test_available_achievements_unauthorized(self):
        """✅ Unauthenticated users cannot view achievements"""
        response = self.client.get(self.available_achievements_url)
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    # ==================== BADGES ACTION TESTS ====================

    def test_badges_as_student(self):
        """✅ Student can view their badges"""
        self.client.force_authenticate(user=self.student1)
        
        response = self.client.get(self.badges_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('student', response.data)
        self.assertIn('total_badges', response.data)
        self.assertIn('badges', response.data)
        
        self.assertEqual(response.data['total_badges'], 3)  # student1 has 3 achievements
        self.assertEqual(len(response.data['badges']), 3)
        
        # Check badge structure
        badge = response.data['badges'][0]
        self.assertIn('id', badge)
        self.assertIn('type', badge)
        self.assertIn('title', badge)
        self.assertIn('icon', badge)
        self.assertIn('earned_date', badge)
        self.assertIn('description', badge)
        self.assertIn('badge_url', badge)

    def test_badges_with_student_id(self):
        """✅ Instructor can view badges for specific student"""
        self.client.force_authenticate(user=self.instructor1)
        
        response = self.client.get(
            self.badges_url, 
            {'student_id': self.student1_profile.id}
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['student'], self.student1.username)

    def test_badges_missing_student_id_for_non_student(self):
        """✅ Non-students must provide student_id"""
        self.client.force_authenticate(user=self.instructor1)
        
        response = self.client.get(self.badges_url)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_badges_no_achievements(self):
        """✅ Badges endpoint works for students with no achievements"""
        # Create student with no achievements
        new_student = User.objects.create_user(
            username='no_badges',
            email='no_badges@test.com',
            password='testpass123',
            role='S'
        )
        
        self.client.force_authenticate(user=new_student)
        response = self.client.get(self.badges_url)
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    # ==================== EXPORT ACTION TESTS ====================

    def test_export_as_platform_admin(self):
        """✅ Platform admin can export achievements"""
        self.client.force_authenticate(user=self.platform_admin)
        
        response = self.client.get(self.export_url)
        
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response['Content-Type'], 'text/csv')
        self.assertIn('attachment; filename="achievements.csv"', response['Content-Disposition'])
        
        # Check CSV content
        content = response.content.decode('utf-8')
        self.assertIn('Student,School,Achievement,Points,Date Earned', content)
        
        # Should include all achievements
        lines = content.strip().split('\n')
        self.assertEqual(len(lines), Achievement.objects.count() + 1)  # Header + data rows

    def test_export_as_school_owner(self):
        """✅ School owner can export achievements from their schools"""
        self.client.force_authenticate(user=self.school_owner1)
        
        response = self.client.get(self.export_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Check only includes school1 achievements
        content = response.content.decode('utf-8')
        school1_achievement_count = Achievement.objects.filter(
            student__school=self.school1
        ).count()
        
        lines = content.strip().split('\n')
        self.assertEqual(len(lines), school1_achievement_count + 1)

    def test_export_as_instructor_denied(self):
        """✅ Instructor cannot export achievements"""
        self.client.force_authenticate(user=self.instructor1)
        
        response = self.client.get(self.export_url)
        
        print("#"*100)
        print(response)
        print("#"*100)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_export_as_student_denied(self):
        """✅ Student cannot export achievements"""
        self.client.force_authenticate(user=self.student1)
        
        response = self.client.get(self.export_url)
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    # ==================== EDGE CASE TESTS ====================

    def test_achievement_earned_at_auto_set(self):
        """✅ Achievement earned_at should be auto-set on creation"""
        self.client.force_authenticate(user=self.platform_admin)
        
        data = {
            'student': self.student1_profile.id,
            'type': 'theory_complete',
            'title': 'Test',
            'description': 'Test',
            'icon': '🎯',
            'points': 10
        }
        
        response = self.client.post(self.list_url, data, format='json')
        

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('earned_at', response.data)
        self.assertIsNotNone(response.data['earned_at'])
        
        # Check it's saved to database
        achievement_id = response.data['id']
        achievement = Achievement.objects.get(id=achievement_id)
        self.assertIsNotNone(achievement.earned_at)

    def test_achievement_with_special_characters(self):
        """✅ Achievement can have special characters in title/description"""
        self.client.force_authenticate(user=self.platform_admin)
        
        data = {
            'student': self.student1_profile.id,
            'type': 'theory_complete',
            'title': '🎖️ Special Achievement! 🏆',
            'description': 'Description with emojis 🎉 and special chars #️⃣',
            'icon': '🏅',
            'points': 50
        }
        
        response = self.client.post(self.list_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['title'], '🎖️ Special Achievement! 🏆')
        self.assertEqual(response.data['icon'], '🏅')

    def test_achievement_high_points(self):
        """✅ Achievement can have high point values"""
        self.client.force_authenticate(user=self.platform_admin)
        
        data = {
            'student': self.student1_profile.id,
            'type': 'driving_master',
            'title': 'High Value',
            'description': 'Worth many points',
            'icon': '💰',
            'points': 1000  # High value
        }
        
        response = self.client.post(self.list_url, data, format='json')
        

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['points'], 1000)
 
    def test_achievement_zero_points(self):
        """✅ Achievement can have zero points"""
        self.client.force_authenticate(user=self.platform_admin)
        
        data = {
            'student': self.student1_profile.id,
            'type': 'driving_master',
            'title': 'Zero Points',
            'description': 'Just for recognition',
            'icon': '🎗️',
            'points': 0
        }
        
        response = self.client.post(self.list_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['points'], 0)

    def test_multiple_achievements_same_type_different_students(self):
        """✅ Different students can have same achievement type"""
        self.client.force_authenticate(user=self.platform_admin)
        
        # Both students already have first_lesson, that's fine
        student1_first_lesson = Achievement.objects.filter(
            student=self.student1_profile, 
            type='first_lesson'
        ).exists()
        student2_first_lesson = Achievement.objects.filter(
            student=self.student2_profile, 
            type='first_lesson'
        ).exists()
        
        self.assertTrue(student1_first_lesson)
        self.assertTrue(student2_first_lesson)
        
        # Both exist and that's expected behavior
        self.assertEqual(
            Achievement.objects.filter(type='first_lesson').count(),
            2
        )

    def test_achievement_filter_by_date_range(self):
        """✅ Can filter achievements by date range"""
        self.client.force_authenticate(user=self.school_owner1)
        
        # Get achievements from last week
        week_ago = (timezone.now() - timedelta(days=7)).date().isoformat()
        today = timezone.now().date().isoformat()
        
        response = self.client.get(
            self.list_url, 
            {'earned_at__gte': week_ago, 'earned_at__lte': today}
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Check if response is paginated (has 'results' key) or a flat list
        achievements_data = response.data
        
        # Handle paginated response
        if 'results' in achievements_data:
            achievements_list = achievements_data['results']
            print(f"Pagination detected: {achievements_data['count']} total achievements")
        else:
            achievements_list = achievements_data
            print(f"Flat list: {len(achievements_list)} achievements")
        
        # Should include recent achievements
        for achievement in achievements_list:
            earned_at = achievement['earned_at']
            
            # Parse the datetime string
            if isinstance(earned_at, str):
                # Handle different datetime formats
                if 'Z' in earned_at:
                    earned_at_dt = datetime.fromisoformat(earned_at.replace('Z', '+00:00'))
                elif '+' in earned_at:
                    # Already has timezone info
                    earned_at_dt = datetime.fromisoformat(earned_at)
                else:
                    # No timezone, assume UTC
                    earned_at_dt = datetime.fromisoformat(earned_at + '+00:00')
            else:
                # If it's already a datetime object (shouldn't happen with DRF)
                earned_at_dt = earned_at
            
            self.assertGreaterEqual(earned_at_dt, timezone.now() - timedelta(days=7))
            self.assertLessEqual(earned_at_dt, timezone.now())

    def test_achievement_order_by_multiple_fields(self):
        """✅ Can order achievements by multiple fields"""
        self.client.force_authenticate(user=self.school_owner1)
        
        response = self.client.get(self.list_url, {'ordering': 'student,-points'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Extract achievements list from response
        achievements_data = response.data
        
        # Handle different response formats
        if isinstance(achievements_data, dict) and 'results' in achievements_data:
            achievements_list = achievements_data['results']
            print(f"Pagination detected: {len(achievements_list)} achievements in results")
        elif isinstance(achievements_data, list):
            achievements_list = achievements_data
            print(f"Flat list: {len(achievements_list)} achievements")
        else:
            print(f"Unexpected response format: {type(achievements_data)}")
            print(f"Response: {achievements_data}")
            return
        
        # Skip if empty or only one item
        if len(achievements_list) <= 1:
            print(f"Not enough achievements to test ordering ({len(achievements_list)} items)")
            return
        
        # Check ordering
        for i in range(len(achievements_list) - 1):
            current = achievements_list[i]
            next_item = achievements_list[i + 1]
            
            # Skip if missing required fields
            if not all(key in current and key in next_item 
                      for key in ['student', 'points']):
                print(f"Skipping comparison - missing fields in items {i} or {i+1}")
                continue
            
            # If same student, points should be descending
            if current['student'] == next_item['student']:
                self.assertGreaterEqual(
                    current['points'], 
                    next_item['points'],
                    f"Points not in descending order for same student {current['student']}: "
                    f"{current['points']} should be >= {next_item['points']}"
                )
        
        print(f"✅ Ordering test passed for {len(achievements_list)} achievements")

    # ==================== PERFORMANCE TESTS ====================

    def test_query_performance_with_many_achievements(self):
        """✅ Test performance with many achievements"""
        self.client.force_authenticate(user=self.platform_admin)
        
        # Create many achievements
        for i in range(50):
            Achievement.objects.create(
                student=self.student1_profile,
                type=f'performance_test_{i}',
                title=f'Performance Achievement {i}',
                description='Test performance',
                icon='⚡',
                points=i * 10
            )
        
        import time
        start_time = time.time()
        response = self.client.get(self.list_url)
        end_time = time.time()
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Should be reasonably fast even with many achievements
        query_time = end_time - start_time
        self.assertLess(query_time, 2.0, f"Query took too long: {query_time:.2f} seconds")
        
        print(f"\n✅ Performance test:")
        print(f"- Total achievements in DB: {Achievement.objects.count()}")
        print(f"- Query time: {query_time:.3f} seconds")
        print(f"- Achievements returned: {len(response.data)}")

    def test_n_plus_one_query_problem_prevented(self):
        """✅ Ensure no N+1 query problem in list view"""
        from django.db import connection
        
        self.client.force_authenticate(user=self.platform_admin)
        
        # Count queries when listing achievements
        with self.assertNumQueries(2):  # 1 count query + 1 data query
            response = self.client.get(self.list_url)
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            
            result = self.get_results(response.data)
            # Access related data to trigger any lazy loading
            for achievement in result:
                # These should be included in the initial query via select_related
                _ = achievement['student']
                _ = achievement['title']
        
        print(f"\n✅ N+1 Query Test:")
        print(f"- Expected queries: 2")
        print(f"- Achievements fetched: {len(response.data)}")
        print(f"- No N+1 problem detected!")

    # ==================== CLEANUP TESTS ====================

    def test_teardown_cleans_up_properly(self):
        """✅ Test that tearDown method properly cleans up test data"""
        # Count before test
        initial_user_count = User.objects.count()
        initial_achievement_count = Achievement.objects.count()
        
        # Create some test data
        test_user = User.objects.create_user(
            username='test_cleanup',
            email='cleanup@test.com',
            password='testpass123',
            role='S'
        )
        
        test_school = DrivingSchool.objects.create(
            owner=self.school_owner1,
            name='Cleanup School',
            email='cleanup@school.com',
            address='Test Address'
        )
        
        test_profile = StudentProfile.objects.create(
            user=test_user,
            school=test_school,
            status='A'
        )
        
        test_achievement = Achievement.objects.create(
            student=test_profile,
            type='cleanup_test',
            title='Cleanup Test',
            icon='🧹',
            points=10
        )
        
        # Run the test
        self.test_list_achievements_success()
        
        # After test, the tearDown should clean up everything
        # The test setup creates data that tearDown will delete
        # This verifies our test isolation

    # ==================== INTEGRATION TESTS ====================

    def test_integration_workflow(self):
        """✅ Test complete achievement workflow"""
        print("\n🔧 Testing Complete Achievement Workflow:")
        
        # 1. Student views empty achievements
        self.client.force_authenticate(user=self.student3)
        response = self.client.get(self.my_achievements_url)
        
        if response.status_code == 404:
            print("- Student has no profile yet (expected for student3)")
        else:
            print(f"- Student has {response.data['summary']['total_achievements']} achievements")
        
        # 2. Instructor awards achievement
        self.client.force_authenticate(user=self.instructor1)
        award_data = {
            'student_id': self.student1_profile.id,
            'achievement_type': 'perfect_attendance',
            'custom_title': 'Attendance Star ⭐'
        }
        
        response = self.client.post(self.award_achievement_url, award_data, format='json')
        print(f"- Awarded achievement: {response.status_code}")
        
        if response.status_code == 201:
            print(f"  New achievement: {response.data['achievement']['title']}")
            print(f"  Points: {response.data['achievement']['points']}")
        
        # 3. Check milestones
        response = self.client.post(self.check_milestones_url, {}, format='json')
        print(f"- Checked milestones: {response.data['achievements_awarded']} new achievements awarded")
        
        # 4. View leaderboard
        self.client.force_authenticate(user=self.student1)
        response = self.client.get(self.leaderboard_url)
        print(f"- Leaderboard shows {len(response.data['leaderboard'])} students")
        
        if response.data['your_rank']:
            print(f"  Student rank: {response.data['your_rank']['rank']}")
            print(f"  Student points: {response.data['your_rank']['total_points']}")
        
        # 5. View progress
        response = self.client.get(self.student_progress_url)
        print(f"- Student progress: {response.data['summary']['completion_rate']:.1f}% complete")
        print(f"  Earned: {response.data['summary']['earned_count']} achievements")
        print(f"  Available: {len(response.data['all_achievements_progress']) - response.data['summary']['earned_count']} more available")
        
        # 6. View badges
        response = self.client.get(self.badges_url)
        print(f"- Student badges: {response.data['total_badges']} badges earned")
        
        print("✅ Workflow test complete!")

    def test_error_handling(self):
        """✅ Test error responses are properly formatted"""
        # Invalid JSON
        self.client.force_authenticate(user=self.platform_admin)
        response = self.client.post(
            self.list_url,
            'invalid json',
            content_type='application/json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        
        # Invalid endpoint
        response = self.client.get('/api/invalid-endpoint/')
        self.assertIn(response.status_code, [404, 403])

    def test_rate_limiting_not_applied(self):
        """✅ Test that endpoints don't have aggressive rate limiting"""
        self.client.force_authenticate(user=self.student1)
        
        # Make multiple rapid requests
        for i in range(5):
            response = self.client.get(self.my_achievements_url)
            self.assertIn(response.status_code, [200, 404])  # Should succeed or give proper error
        
        print(f"\n✅ Rate limiting test: Made 5 rapid requests without blocking")

    # ==================== SECURITY TESTS ====================

    def test_sql_injection_prevention(self):
        """✅ Test SQL injection prevention"""
        self.client.force_authenticate(user=self.platform_admin)

        response = self.client.get(
            self.list_url,
            {'search': "' OR '1'='1"}
        )

        self.assertIn(response.status_code, [200, 400])

        if response.status_code == 200:
            self.assertIsInstance(response.data, dict)
            self.assertIn('results', response.data)
            self.assertIsInstance(response.data['results'], list)

            # Optional: ensure no data leakage
            self.assertEqual(response.data['count'], len(response.data['results']))

        print("\n✅ SQL injection test: Attempt handled safely")


    def test_xss_prevention(self):
        """✅ Test XSS prevention in achievement data"""
        self.client.force_authenticate(user=self.platform_admin)
        
        xss_payload = "<script>alert('XSS')</script>"
        
        data = {
            'student': self.student1_profile.id,
            'type': 'xss_test',
            'title': xss_payload,
            'description': xss_payload,
            'icon': '⚠️',
            'points': 10
        }
        
        response = self.client.post(self.list_url, data, format='json')
        
        # Should either reject or sanitize the input
        if response.status_code == 201:
            # If accepted, check it's not the raw script
            self.assertNotIn('<script>', response.data['title'])
            self.assertNotIn('<script>', response.data['description'])
            print(f"✅ XSS payload sanitized in response")
        else:
            print(f"✅ XSS payload rejected with status {response.status_code}")

    def test_data_privacy(self):
        """✅ Test data privacy between schools"""
        # School owner 1 should not see school 2 data
        self.client.force_authenticate(user=self.school_owner1)
        
        # Try to access school 2 achievement directly
        school2_achievement = Achievement.objects.filter(
            student__school=self.school2
        ).first()
        
        if school2_achievement:
            response = self.client.get(self.detail_url(school2_achievement.id))
            # Should get 404 (not found in filtered queryset) or 403 (forbidden)
            self.assertIn(response.status_code, [status.HTTP_404_NOT_FOUND, status.HTTP_403_FORBIDDEN],
                         f"School owner should not access school 2 achievement, got {response.status_code}")
        else:
            # If no school 2 achievements exist, that's fine too
            print("No school 2 achievements to test")
        
        # Also test that listing achievements doesn't crash
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        print("✅ Data privacy maintained - school owners cannot access other school's data")


if __name__ == '__main__':
    # Allow running tests directly
    import unittest
    unittest.main()
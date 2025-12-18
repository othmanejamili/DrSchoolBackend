import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase, APIClient
from django.contrib.auth import get_user_model
from django.utils import timezone
from DriveApp.models import (
    User, DrivingSchool, StudentProfile, Lesson, 
    Attendance, Schedule, Feedback, Vehicle
)

User = get_user_model()

class LessonViewSetTests(APITestCase):
    """Test suite for Lesson CRUD operations and permissions"""
    
    def setUp(self):
        """Set up test data with lessons across multiple schools"""
        # Create Platform Admin
        self.platform_admin = User.objects.create_user(
            username='platform_admin',
            email='admin@platform.com',
            password='AdminPass123!',
            role='A',
            is_staff=True
        )
        
        # Create School Owners
        self.school_owner1 = User.objects.create_user(
            username='school_owner1',
            email='owner1@school.com',
            password='OwnerPass123!',
            role='A'
        )
        
        self.school_owner2 = User.objects.create_user(
            username='school_owner2',
            email='owner2@school.com',
            password='OwnerPass123!',
            role='A'
        )
        
        # Create Driving Schools
        self.school1 = DrivingSchool.objects.create(
            name='Elite Driving School',
            email='contact@elite.com',
            owner=self.school_owner1
        )
        
        self.school2 = DrivingSchool.objects.create(
            name='Pro Driving Academy',
            email='contact@pro.com',
            owner=self.school_owner2
        )
        
        # Create Instructors
        self.instructor1 = User.objects.create_user(
            username='instructor1',
            email='instructor1@school1.com',
            password='InstructorPass123!',
            role='I'
        )
        self.instructor1_profile = StudentProfile.objects.create(
            user=self.instructor1,
            school=self.school1,
            status='A'
        )
        
        self.instructor2 = User.objects.create_user(
            username='instructor2',
            email='instructor2@school2.com',
            password='InstructorPass123!',
            role='I'
        )
        self.instructor2_profile = StudentProfile.objects.create(
            user=self.instructor2,
            school=self.school2,
            status='A'
        )
        
        # Create Students
        self.student1 = User.objects.create_user(
            username='student1',
            email='student1@school1.com',
            password='StudentPass123!',
            role='S'
        )
        self.student1_profile = StudentProfile.objects.create(
            user=self.student1,
            school=self.school1,
            status='A'
        )
        
        self.student2 = User.objects.create_user(
            username='student2',
            email='student2@school1.com',
            password='StudentPass123!',
            role='S'
        )
        self.student2_profile = StudentProfile.objects.create(
            user=self.student2,
            school=self.school1,
            status='A'
        )
        
        self.student3 = User.objects.create_user(
            username='student3',
            email='student3@school2.com',
            password='StudentPass123!',
            role='S'
        )
        self.student3_profile = StudentProfile.objects.create(
            user=self.student3,
            school=self.school2,
            status='A'
        )
        
        # Create Vehicles
        self.vehicle1 = Vehicle.objects.create(
            school=self.school1,
            plate_number='ABC123',
            make='Toyota',
            model='Corolla',
            year=2020,
            transmission='manual',
            status='available'
        )
        
        self.vehicle2 = Vehicle.objects.create(
            school=self.school2,
            plate_number='XYZ789',
            make='Honda',
            model='Civic',
            year=2021,
            transmission='automatic',
            status='available'
        )
        
        # Create Lessons for School 1
        self.lesson1_school1 = Lesson.objects.create(
            title='Introduction to Driving',
            lesson_type='T',  # Theory
            instructor=self.instructor1,
            school=self.school1,
            description='Basic driving rules and regulations',
            duration=120,  # 2 hours
            date=timezone.now() + timezone.timedelta(days=1),  # Future
            status='S'  # Scheduled
        )
        
        self.lesson2_school1 = Lesson.objects.create(
            title='First Driving Practice',
            lesson_type='D',  # Driving
            instructor=self.instructor1,
            school=self.school1,
            description='Basic vehicle control',
            duration=90,
            date=timezone.now() - timezone.timedelta(days=1),  # Past
            status='C'  # Completed
        )
        
        self.lesson3_school1 = Lesson.objects.create(
            title='Advanced Maneuvers',
            lesson_type='D',
            instructor=self.instructor1,
            school=self.school1,
            description='Parallel parking and reversing',
            duration=120,
            date=timezone.now() + timezone.timedelta(days=2),
            status='C'
        )
        
        # Create Lessons for School 2
        self.lesson1_school2 = Lesson.objects.create(
            title='Road Safety Workshop',
            lesson_type='T',
            instructor=self.instructor2,
            school=self.school2,
            description='Safety procedures and emergency handling',
            duration=180,
            date=timezone.now() + timezone.timedelta(days=1),
            status='C'
        )
        
        self.lesson2_school2 = Lesson.objects.create(
            title='Highway Driving',
            lesson_type='D',
            instructor=self.instructor2,
            school=self.school2,
            description='High-speed driving techniques',
            duration=150,
            date=timezone.now() - timezone.timedelta(days=2),  # Past
            status='S'
        )
        
        # Create Schedule for lesson1_school1
        self.schedule1 = Schedule.objects.create(
            lesson=self.lesson1_school1,
            vehicle=self.vehicle1,
            instructor=self.instructor1,
            start_time=timezone.now() + timezone.timedelta(days=1, hours=10),
            end_time=timezone.now() + timezone.timedelta(days=1, hours=12)
        )
        
        # Create Attendance records
        self.attendance1 = Attendance.objects.create(
            student=self.student1_profile,
            lesson=self.lesson2_school1,  # Completed lesson
            presence=True,
            hours_completed=1.5
        )
        
        self.attendance2 = Attendance.objects.create(
            student=self.student2_profile,
            lesson=self.lesson2_school1,
            presence=False,
            hours_completed=0
        )
        
        # Create Feedback
        self.feedback1 = Feedback.objects.create(
            student=self.student1_profile,
            lesson=self.lesson2_school1,
            rating=5,
            comment='Excellent instruction!'
        )
        
        self.client = APIClient()
    
    # ==================== LIST TESTS ====================
    
    def test_platform_admin_can_list_all_lessons(self):
        """Platform admin should see all lessons"""
        self.client.force_authenticate(user=self.platform_admin)
        
        url = reverse('lesson-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Total lessons: 2 from school1 + 2 from school2 = 4
        self.assertEqual(len(response.data['results']), 5)
    
    def test_school_owner_can_list_lessons_in_their_school(self):
        """School owner should see lessons in their school only"""
        self.client.force_authenticate(user=self.school_owner1)
        
        url = reverse('lesson-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # School1 has 3 lessons
        self.assertEqual(len(response.data['results']), 3)
        
        lesson_titles = [lesson['title'] for lesson in response.data['results']]
        self.assertIn('Introduction to Driving', lesson_titles)
        self.assertIn('First Driving Practice', lesson_titles)
        self.assertNotIn('Road Safety Workshop', lesson_titles)  # From school2
    
    def test_instructor_can_list_their_own_lessons(self):
        """Instructor should see only their own lessons"""
        self.client.force_authenticate(user=self.instructor1)
        
        url = reverse('lesson-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Instructor1 has 3 lessons in school1
        self.assertEqual(len(response.data['results']), 3)
        
        lesson_titles = [lesson['title'] for lesson in response.data['results']]
        self.assertIn('Introduction to Driving', lesson_titles)
        self.assertNotIn('Road Safety Workshop', lesson_titles)  # Instructor2's lesson
    
    def test_student_can_list_lessons_in_their_school(self):
        """Student should see lessons in their school"""
        self.client.force_authenticate(user=self.student1)
        
        url = reverse('lesson-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Student1 in school1 should see 3 lessons
        self.assertEqual(len(response.data['results']), 3)
        
        lesson_titles = [lesson['title'] for lesson in response.data['results']]
        self.assertIn('Introduction to Driving', lesson_titles)
        self.assertNotIn('Road Safety Workshop', lesson_titles)  # From school2
    
    def test_unauthenticated_user_cannot_list_lessons(self):
        """Unauthenticated users should not access lessons"""
        url = reverse('lesson-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    # ==================== RETRIEVE TESTS ====================
     
    def test_platform_admin_can_retrieve_any_lesson(self):
        """Platform admin should retrieve any lesson"""
        self.client.force_authenticate(user=self.platform_admin)
        
        url = reverse('lesson-detail', kwargs={'pk': self.lesson1_school1.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['title'], 'Introduction to Driving')
    
    def test_school_owner_can_retrieve_lessons_in_their_school(self):
        """School owner should retrieve lessons in their school"""
        self.client.force_authenticate(user=self.school_owner1)
        
        url = reverse('lesson-detail', kwargs={'pk': self.lesson1_school1.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['title'], 'Introduction to Driving')
    
    def test_school_owner_cannot_retrieve_lessons_in_other_school(self):
        """School owner should not retrieve lessons from other school"""
        self.client.force_authenticate(user=self.school_owner1)
        
        url = reverse('lesson-detail', kwargs={'pk': self.lesson1_school2.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    
    def test_instructor_can_retrieve_their_own_lesson(self):
        """Instructor should retrieve their own lesson"""
        self.client.force_authenticate(user=self.instructor1)
        
        url = reverse('lesson-detail', kwargs={'pk': self.lesson1_school1.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['title'], 'Introduction to Driving')
    
    def test_instructor_cannot_retrieve_other_instructors_lesson(self):
        """Instructor should not retrieve other instructors' lessons"""
        self.client.force_authenticate(user=self.instructor1)
        
        url = reverse('lesson-detail', kwargs={'pk': self.lesson1_school2.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    
    def test_student_can_retrieve_lesson_in_their_school(self):
        """Student should retrieve lessons in their school"""
        self.client.force_authenticate(user=self.student1)
        
        url = reverse('lesson-detail', kwargs={'pk': self.lesson1_school1.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['title'], 'Introduction to Driving')
    
    def test_student_cannot_retrieve_lesson_in_other_school(self):
        """Student should not retrieve lessons from other school"""
        self.client.force_authenticate(user=self.student1)
        
        url = reverse('lesson-detail', kwargs={'pk': self.lesson1_school2.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    
    # ==================== CREATE TESTS ====================
    
    def test_platform_admin_can_create_lesson(self):
        """Platform admin should create lessons"""
        self.client.force_authenticate(user=self.platform_admin)
        
        url = reverse('lesson-list')
        data = {
            'title': 'New Theory Lesson',
            'lesson_type': 'T',
            'instructor': self.instructor1.id,
            'school': self.school1.id,
            'description': 'Test lesson creation',
            'duration': 60,
            'date': (timezone.now() + timezone.timedelta(days=4)).isoformat(),
            'status': 'S'
        }
        
        response = self.client.post(url, data, format='json')
        
        print("#"*80)
        print(response.data)
        print(response)
        print("#"*80)
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Lesson.objects.count(), 6)  # Was 5, now 6
        self.assertTrue(Lesson.objects.filter(title='New Theory Lesson').exists())
    
    def test_school_owner_can_create_lesson_in_their_school(self):
        """School owner should create lessons in their school"""
        self.client.force_authenticate(user=self.school_owner1)
        
        url = reverse('lesson-list')
        data = {
            'title': 'Owner Created Lesson',
            'lesson_type': 'D',
            'instructor': self.instructor1.id,
            'school': self.school1.id,
            'description': 'Created by school owner',
            'duration': 90,
            'date': (timezone.now() + timezone.timedelta(days=4)).isoformat(),
            'status': 'S'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
    
    def test_school_owner_cannot_create_lesson_in_other_school(self):
        """School owner should not create lessons in other schools"""
        self.client.force_authenticate(user=self.school_owner1)
        
        url = reverse('lesson-list')
        data = {
            'title': 'Unauthorized Lesson',
            'lesson_type': 'T',
            'instructor': self.instructor2.id,
            'school': self.school2.id,  # Other owner's school
            'description': 'Should fail',
            'duration': 60,
            'date': (timezone.now() + timezone.timedelta(days=3)).isoformat(),
            'status': 'S'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('school', response.data)  # Error about school permission
    
    def test_instructor_cannot_create_lesson(self):
        """Instructor should not create lessons"""
        self.client.force_authenticate(user=self.instructor1)
        
        url = reverse('lesson-list')
        data = {
            'title': 'Instructor Created',
            'lesson_type': 'D',
            'instructor': self.instructor1.id,
            'school': self.school1.id,
            'duration': 60,
            'date': (timezone.now() + timezone.timedelta(days=3)).isoformat(),
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_student_cannot_create_lesson(self):
        """Student should not create lessons"""
        self.client.force_authenticate(user=self.student1)
        
        url = reverse('lesson-list')
        data = {
            'title': 'Student Created',
            'lesson_type': 'T',
            'instructor': self.instructor1.id,
            'school': self.school1.id,
            'duration': 60,
            'date': (timezone.now() + timezone.timedelta(days=3)).isoformat(),
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    # ==================== UPDATE TESTS ====================
    
    def test_platform_admin_can_update_any_lesson(self):
        """Platform admin should update any lesson"""
        self.client.force_authenticate(user=self.platform_admin)
        
        url = reverse('lesson-detail', kwargs={'pk': self.lesson1_school1.id})
        data = {'title': 'Updated Title by Admin'}
        
        response = self.client.patch(url, data, format='json')
        
        print('#'*30)
        print(response.data)
        print(response)
        print("#"*30)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.lesson1_school1.refresh_from_db()
        self.assertEqual(self.lesson1_school1.title, 'Updated Title by Admin')
    
    def test_school_owner_can_update_lessons_in_their_school(self):
        """School owner should update lessons in their school"""
        self.client.force_authenticate(user=self.school_owner1)
        
        url = reverse('lesson-detail', kwargs={'pk': self.lesson1_school1.id})
        data = {'duration': 150}
        
        response = self.client.patch(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.lesson1_school1.refresh_from_db()
        self.assertEqual(self.lesson1_school1.duration, 150)
    
    def test_school_owner_cannot_update_lessons_in_other_school(self):
        """School owner should not update lessons in other school"""
        self.client.force_authenticate(user=self.school_owner1)
        
        url = reverse('lesson-detail', kwargs={'pk': self.lesson1_school2.id})
        data = {'duration': 200}
        
        response = self.client.patch(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_instructor_can_update_their_own_lesson(self):
        """Instructor should update their own lesson"""
        self.client.force_authenticate(user=self.instructor1)

        url = reverse('lesson-detail', kwargs={'pk': self.lesson1_school1.id})
        data = {'description': 'Updated by instructor'}
        
        response = self.client.patch(url, data, format='json')

        print('#'*30)
        print(response.data)
        print(response)
        print("#"*30)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.lesson1_school1.refresh_from_db()
        self.assertEqual(self.lesson1_school1.description, 'Updated by instructor')

    def test_instructor_cannot_update_other_instructors_lesson(self):
        """Instructor should not update other instructors' lessons"""
        self.client.force_authenticate(user=self.instructor1)
        
        url = reverse('lesson-detail', kwargs={'pk': self.lesson1_school2.id})
        data = {'description': 'Should fail'}
        
        response = self.client.patch(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    
    def test_student_cannot_update_lesson(self):
        """Student should not update lessons"""
        self.client.force_authenticate(user=self.student1)
        
        url = reverse('lesson-detail', kwargs={'pk': self.lesson1_school1.id})
        data = {'title': 'Student trying to update'}
        
        response = self.client.patch(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    # ==================== DELETE TESTS ====================
    
    def test_platform_admin_can_delete_lesson(self):
        """Platform admin should delete lessons"""
        self.client.force_authenticate(user=self.platform_admin)
        
        url = reverse('lesson-detail', kwargs={'pk': self.lesson3_school1.id})
        response = self.client.delete(url)
        
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Lesson.objects.filter(id=self.lesson3_school1.id).exists())
    
    def test_school_owner_can_delete_lesson_in_their_school(self):
        """School owner should delete lessons in their school"""
        self.client.force_authenticate(user=self.school_owner1)
        
        url = reverse('lesson-detail', kwargs={'pk': self.lesson3_school1.id})
        response = self.client.delete(url)
        
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
    
    def test_school_owner_cannot_delete_lesson_in_other_school(self):
        """School owner should not delete lessons in other school"""
        self.client.force_authenticate(user=self.school_owner1)
        
        url = reverse('lesson-detail', kwargs={'pk': self.lesson1_school2.id})
        response = self.client.delete(url)
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    
    def test_instructor_cannot_delete_lesson(self):
        """Instructor should not delete lessons"""
        self.client.force_authenticate(user=self.instructor1)
        
        url = reverse('lesson-detail', kwargs={'pk': self.lesson1_school1.id})
        response = self.client.delete(url)
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_student_cannot_delete_lesson(self):
        """Student should not delete lessons"""
        self.client.force_authenticate(user=self.student1)
        
        url = reverse('lesson-detail', kwargs={'pk': self.lesson1_school1.id})
        response = self.client.delete(url)
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    # ==================== CUSTOM ACTION: ATTENDANCE ====================
    
    def test_platform_admin_can_view_lesson_attendance(self):
        """Platform admin should view attendance for any lesson"""
        self.client.force_authenticate(user=self.platform_admin)
        
        url = reverse('lesson-attendance', kwargs={'pk': self.lesson2_school1.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('total_attendance', response.data)
        self.assertIn('present_count', response.data)
        self.assertIn('attendance_list', response.data)
        self.assertEqual(response.data['total_attendance'], 2)
        self.assertEqual(response.data['present_count'], 1)
    
    def test_school_owner_can_view_attendance_in_their_school(self):
        """School owner should view attendance in their school"""
        self.client.force_authenticate(user=self.school_owner1)
        
        url = reverse('lesson-attendance', kwargs={'pk': self.lesson2_school1.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['total_attendance'], 2)
    
    def test_school_owner_cannot_view_attendance_in_other_school(self):
        """School owner should not view attendance in other school"""
        self.client.force_authenticate(user=self.school_owner1)
        
        url = reverse('lesson-attendance', kwargs={'pk': self.lesson2_school2.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    
    def test_instructor_can_view_attendance_for_their_lesson(self):
        """Instructor should view attendance for their own lessons"""
        self.client.force_authenticate(user=self.instructor1)
        
        url = reverse('lesson-attendance', kwargs={'pk': self.lesson2_school1.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['total_attendance'], 2)
    
    def test_instructor_cannot_view_attendance_for_other_instructors_lesson(self):
        """Instructor should not view attendance for other instructors' lessons"""
        self.client.force_authenticate(user=self.instructor1)
        
        url = reverse('lesson-attendance', kwargs={'pk': self.lesson2_school2.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    
    def test_student_can_view_attendance_for_lessons_they_attend(self):
        """Student should view attendance for lessons they attend"""
        self.client.force_authenticate(user=self.student1)
        
        url = reverse('lesson-attendance', kwargs={'pk': self.lesson2_school1.id})
        response = self.client.get(url)
        

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['total_attendance'], 1)
    
    def test_student_cannot_view_attendance_for_lessons_they_dont_attend(self):
        """Student should not view attendance for lessons they don't attend"""
        self.client.force_authenticate(user=self.student1)
        
        # Create a lesson without attendance for student1
        new_lesson = Lesson.objects.create(
            title='Unauthorized Lesson',
            lesson_type='T',
            instructor=self.instructor1,
            school=self.school1,
            duration=60,
            date=timezone.now() + timezone.timedelta(days=5),
            status='S'
        )
        
        url = reverse('lesson-attendance', kwargs={'pk': new_lesson.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    
    # ==================== CUSTOM ACTION: MARK_ATTENDANCE ====================
    def test_instructor_can_mark_attendance_for_their_lesson(self):
        """Instructor should mark attendance for their own lesson"""
        self.client.force_authenticate(user=self.instructor1)
        
        # Use lesson2_school1 which is a PAST lesson
        url = reverse('lesson-mark-attendance', kwargs={'pk': self.lesson2_school1.id})
        data = {
            'student_ids': [self.student1_profile.id, self.student2_profile.id],
            'presence': True,
            'hours_completed': 1.5,
            'notes': 'Both students attended'
        }
        
        response = self.client.post(url, data, format='json')
        
        # Debug: Print response if it fails
        if response.status_code != 200:
            print(f"Response: {response.data}")
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('marked_count', response.data)  # Changed from 'message'
        
        # Note: This will UPDATE existing attendance records, not create new ones
        # since lesson2_school1 already has 2 attendance records in setUp
        attendance_count = Attendance.objects.filter(
            lesson=self.lesson2_school1
        ).count()
        self.assertEqual(attendance_count, 2)
    
    def test_instructor_cannot_mark_attendance_for_other_instructors_lesson(self):
        """Instructor should not mark attendance for other instructors' lessons"""
        self.client.force_authenticate(user=self.instructor1)
        
        url = reverse('lesson-mark-attendance', kwargs={'pk': self.lesson1_school2.id})
        data = {'student_ids': [self.student3_profile.id]}
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    
    def test_school_owner_cannot_mark_attendance(self):
        """School owner should not mark attendance (only instructors)"""
        self.client.force_authenticate(user=self.school_owner1)
        
        url = reverse('lesson-mark-attendance', kwargs={'pk': self.lesson1_school1.id})
        data = {'student_ids': [self.student1_profile.id]}
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_student_cannot_mark_attendance(self):
        """Student should not mark attendance"""
        self.client.force_authenticate(user=self.student1)
        
        url = reverse('lesson-mark-attendance', kwargs={'pk': self.lesson1_school1.id})
        data = {'student_ids': [self.student1_profile.id]}
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_mark_attendance_with_invalid_student_ids(self):
        """Should fail when student IDs are invalid or from wrong school"""
        self.client.force_authenticate(user=self.instructor1)
        
        url = reverse('lesson-mark-attendance', kwargs={'pk': self.lesson1_school1.id})
        data = {
            'student_ids': [999, 1000],  # Non-existent IDs
            'presence': True,
            'hours_completed': 1.0
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)
    
    def test_mark_attendance_with_student_from_other_school(self):
        """Should fail when student is from different school"""
        self.client.force_authenticate(user=self.instructor1)
        
        url = reverse('lesson-mark-attendance', kwargs={'pk': self.lesson1_school1.id})
        data = {
            'student_ids': [self.student3_profile.id],  # Student from school2
            'presence': True,
            'hours_completed': 1.0
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    # ==================== CUSTOM ACTION: SCHEDULE ====================
    
    def test_schedule_action_returns_lesson_schedule(self):
        """Schedule action should return lesson schedule if exists"""
        self.client.force_authenticate(user=self.platform_admin)
        
        url = reverse('lesson-schedule', kwargs={'pk': self.lesson1_school1.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('start_time', response.data)
        self.assertIn('end_time', response.data)
        self.assertEqual(response.data['vehicle_info'], 'Toyota Corolla (ABC123)')
    
    def test_schedule_action_returns_404_when_no_schedule(self):
        """Schedule action should return 404 when no schedule exists"""
        self.client.force_authenticate(user=self.platform_admin)
        
        url = reverse('lesson-schedule', kwargs={'pk': self.lesson2_school1.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn('message', response.data)
    
    # ==================== CUSTOM ACTION: FEEDBACK ====================
    
    def test_feedback_action_returns_lesson_feedback(self):
        """Feedback action should return lesson feedback"""
        self.client.force_authenticate(user=self.platform_admin)
        
        url = reverse('lesson-feedback', kwargs={'pk': self.lesson2_school1.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['total_feedback'], 1)
        self.assertEqual(response.data['average_rating'], 5.0)
        self.assertEqual(len(response.data['feedback_list']), 1)
    
    def test_feedback_action_returns_empty_when_no_feedback(self):
        """Feedback action should return empty when no feedback"""
        self.client.force_authenticate(user=self.platform_admin)
        
        url = reverse('lesson-feedback', kwargs={'pk': self.lesson1_school1.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['total_feedback'], 0)
        self.assertEqual(response.data['average_rating'], 0)
        self.assertEqual(len(response.data['feedback_list']), 0)
    
    # ==================== SEARCH & FILTER TESTS ====================
     
    def test_search_lessons_by_title(self):
        """Should search lessons by title"""
        self.client.force_authenticate(user=self.platform_admin)
        
        url = reverse('lesson-list') + '?search=Introduction'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['title'], 'Introduction to Driving')
    
    def test_search_lessons_by_description(self):
        """Should search lessons by description"""
        self.client.force_authenticate(user=self.platform_admin)
        
        url = reverse('lesson-list') + '?search=parallel parking'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['title'], 'Advanced Maneuvers')
    
    def test_filter_lessons_by_lesson_type(self):
        """Should filter lessons by type (T=Theory, D=Driving)"""
        self.client.force_authenticate(user=self.platform_admin)
        
        # Filter by Theory lessons
        url = reverse('lesson-list') + '?lesson_type=T'
        response = self.client.get(url)
        

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Count theory lessons
        theory_count = sum(1 for lesson in response.data['results'] if lesson['lesson_type'] == 'T')
        
        self.assertGreater(theory_count, 0)
    
    def test_filter_lessons_by_status_schduel(self):
        """Should filter lessons by status"""
        self.client.force_authenticate(user=self.platform_admin)
        
        url = reverse('lesson-list') + '?status=S'  # Completed lessons
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # All returned lessons should be completed
        for lesson in response.data['results']:
            self.assertEqual(lesson['status'], 'S')
    

    def test_filter_lessons_by_status_complete(self):
        """Should filter lessons by status"""
        self.client.force_authenticate(user=self.platform_admin)
        
        url = reverse('lesson-list') + '?status=C'  # Completed lessons
        response = self.client.get(url)
        
        

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # All returned lessons should be completed
        for lesson in response.data['results']:
            self.assertEqual(lesson['status'], 'C')

    def test_order_lessons_by_date(self):
        """Should order lessons by date (default is descending)"""
        self.client.force_authenticate(user=self.platform_admin)
        
        url = reverse('lesson-list') + '?ordering=date'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        dates = [lesson['date'] for lesson in response.data['results']]
        
        # Check if dates are in ASCENDING order
        dates_sorted = sorted(dates)
        self.assertEqual(dates, dates_sorted)
    
    def test_order_lessons_by_date_descending(self):
        """Should order lessons by date descending (default)"""
        self.client.force_authenticate(user=self.platform_admin)
        
        url = reverse('lesson-list')  # Default ordering is -date
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        dates = [lesson['date'] for lesson in response.data['results']]
        
        # Check if dates are in DESCENDING order (most recent first)
        dates_sorted_desc = sorted(dates, reverse=True)
        self.assertEqual(dates, dates_sorted_desc)
    
    # ==================== ADDITIONAL EDGE CASE TESTS ====================
    
    def test_cannot_create_lesson_with_past_date(self):
        """Should not create lesson with past date"""
        self.client.force_authenticate(user=self.platform_admin)
        
        url = reverse('lesson-list')
        data = {
            'title': 'Past Lesson',
            'lesson_type': 'T',
            'instructor': self.instructor1.id,
            'school': self.school1.id,
            'description': 'Should fail',
            'duration': 60,
            'date': (timezone.now() - timezone.timedelta(days=1)).isoformat(),  # Past date
            'status': 'S'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('date', response.data)
    
    def test_cannot_create_lesson_with_invalid_instructor(self):
        """Should not create lesson with instructor not in school"""
        # Create instructor not assigned to any school
        outsider_instructor = User.objects.create_user(
            username='outsider',
            email='outsider@example.com',
            password='Pass123!',
            role='I'
        )
        
        self.client.force_authenticate(user=self.platform_admin)
        
        url = reverse('lesson-list')
        data = {
            'title': 'Invalid Instructor Lesson',
            'lesson_type': 'T',
            'instructor': outsider_instructor.id,  # Not assigned to school1
            'school': self.school1.id,
            'duration': 60,
            'date': (timezone.now() + timezone.timedelta(days=1)).isoformat(),
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('instructor', response.data)
    
    def test_cannot_update_lesson_with_invalid_duration(self):
        """Should not update lesson with invalid duration (too long)"""
        self.client.force_authenticate(user=self.platform_admin)
        
        url = reverse('lesson-detail', kwargs={'pk': self.lesson1_school1.id})
        data = {'duration': 500}  # More than 480 minutes (8 hours)
        
        response = self.client.patch(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('duration', response.data)
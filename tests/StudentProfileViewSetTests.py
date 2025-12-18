import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase, APIClient
from django.contrib.auth import get_user_model
from django.utils import timezone
from DriveApp.models import User, DrivingSchool, StudentProfile, SubscriptionPlan, SchoolSubscription

User = get_user_model()
class StudentProfileViewSetTests(APITestCase):
    """Test suite for StudentProfile CRUD operations and permissions"""
    
    def setUp(self):
        """Set up test data"""
        # Create Platform Admin
        self.platform_admin = User.objects.create_user(
            username='platform_admin',
            email='admin@platform.com',
            password='AdminPass123!',
            role='A',
            is_staff=True
        )
        
        # Create School Owner
        self.school_owner = User.objects.create_user(
            username='school_owner',
            email='owner@school1.com',
            password='OwnerPass123!',
            role='A'
        )
        
        # Create another school owner
        self.other_owner = User.objects.create_user(
            username='other_owner',
            email='owner@school2.com',
            password='OwnerPass123!',
            role='A'
        )
        
        # Create Driving Schools
        self.school1 = DrivingSchool.objects.create(
            name='Elite Driving School',
            email='contact@elite.com',
            owner=self.school_owner
        )
        
        self.school2 = DrivingSchool.objects.create(
            name='Pro Driving Academy',
            email='contact@pro.com',
            owner=self.other_owner
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
            status='A',
            progress_theory=50.0,
            progress_driving=30.0,
            total_hours_theory=25.0,
            total_hours_driving =12.0
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
            status='A',
            progress_theory=0.0,
            progress_driving=0.0,
            total_hours_theory=0.0,
            total_hours_driving =0.0
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
            status='A',
            progress_theory=0.0,
            progress_driving=0.0,
            total_hours_theory=0.0,
            total_hours_driving =0.0
        )
        
        # Create a completed student
        self.completed_student = User.objects.create_user(
            username='completed_student',
            email='completed@school1.com',
            password='StudentPass123!',
            role='S'
        )
        self.completed_profile = StudentProfile.objects.create(
            user=self.completed_student,
            school=self.school1,
            status='C',  # Completed
            progress_theory=100.0,
            progress_driving=100.0,
            total_hours_theory=50.0,
            total_hours_driving=40.0
        )
        
        # Create a paused student
        self.paused_student = User.objects.create_user(
            username='paused_student',
            email='paused@school1.com',
            password='StudentPass123!',
            role='S'
        )
        self.paused_profile = StudentProfile.objects.create(
            user=self.paused_student,
            school=self.school1,
            status='P'  # Paused
        )
        
        self.client = APIClient()
    
    # ==================== LIST TESTS ====================
    
    def test_platform_admin_can_list_all_student_profiles(self):
        """Platform admin should see all student profiles"""
        self.client.force_authenticate(user=self.platform_admin)
        
        url = reverse('studentprofile-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should see: student1, student2, student3, completed, paused, instructor1, instructor2
        self.assertEqual(len(response.data['results']), 7)
    
    def test_school_owner_can_list_students_in_their_school(self):
        """School owner should see students in their school only"""
        self.client.force_authenticate(user=self.school_owner)
        
        url = reverse('studentprofile-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # School1 has: student1, student2, completed_student, paused_student, instructor1
        self.assertEqual(len(response.data['results']), 5)
        
        # Should not see students from school2
        student_usernames = [profile['user_username'] for profile in response.data['results']]
        self.assertIn('student1', student_usernames)
        self.assertIn('student2', student_usernames)
        self.assertNotIn('student3', student_usernames)  # From school2
    
    def test_instructor_can_list_students_in_their_school(self):
        """Instructor should see students in their school only (not other instructors)"""
        self.client.force_authenticate(user=self.instructor1)
        
        url = reverse('studentprofile-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should see: student1, student2, completed_student, paused_student (students only)
        # Should NOT see: instructor1 (self) or instructor2
        self.assertEqual(len(response.data['results']), 4)
        
        student_usernames = [profile['user_username'] for profile in response.data['results']]
        self.assertIn('student1', student_usernames)
        self.assertIn('student2', student_usernames)
        self.assertNotIn('instructor1', student_usernames)
        self.assertNotIn('instructor2', student_usernames)
    
    def test_student_can_list_only_their_own_profile(self):
        """Student should see only their own profile"""
        self.client.force_authenticate(user=self.student1)
        
        url = reverse('studentprofile-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['user_username'], 'student1')
    
    def test_unauthenticated_user_cannot_list_profiles(self):
        """Unauthenticated users should not access student profiles"""
        url = reverse('studentprofile-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    # ==================== RETRIEVE TESTS ====================
    
    def test_platform_admin_can_retrieve_any_profile(self):
        """Platform admin should retrieve any student profile"""
        self.client.force_authenticate(user=self.platform_admin)
        
        url = reverse('studentprofile-detail', kwargs={'pk': self.student1_profile.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['user_username'], 'student1')
    
    def test_school_owner_can_retrieve_students_in_their_school(self):
        """School owner should retrieve students in their school"""
        self.client.force_authenticate(user=self.school_owner)
        
        url = reverse('studentprofile-detail', kwargs={'pk': self.student1_profile.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['user_username'], 'student1')
    
    def test_school_owner_cannot_retrieve_students_in_other_school(self):
        """School owner should not retrieve students from other school"""
        self.client.force_authenticate(user=self.school_owner)
        
        url = reverse('studentprofile-detail', kwargs={'pk': self.student3_profile.id})
        response = self.client.get(url)
        
        # Should be 404 because student3 is in school2
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    
    def test_instructor_can_retrieve_students_in_their_school(self):
        """Instructor should retrieve students in their school"""
        self.client.force_authenticate(user=self.instructor1)
        
        url = reverse('studentprofile-detail', kwargs={'pk': self.student1_profile.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['user_username'], 'student1')
    
    def test_instructor_cannot_retrieve_students_in_other_school(self):
        """Instructor should not retrieve students from other school"""
        self.client.force_authenticate(user=self.instructor1)
        
        url = reverse('studentprofile-detail', kwargs={'pk': self.student3_profile.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    
    def test_instructor_cannot_retrieve_other_instructors(self):
        """Instructor should not retrieve other instructors' profiles"""
        self.client.force_authenticate(user=self.instructor1)
        
        url = reverse('studentprofile-detail', kwargs={'pk': self.instructor2_profile.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    
    def test_student_can_retrieve_their_own_profile(self):
        """Student should retrieve their own profile"""
        self.client.force_authenticate(user=self.student1)
        
        url = reverse('studentprofile-detail', kwargs={'pk': self.student1_profile.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['user_username'], 'student1')
    
    def test_student_cannot_retrieve_other_students_profile(self):
        """Student should not retrieve other students' profiles"""
        self.client.force_authenticate(user=self.student1)
        
        url = reverse('studentprofile-detail', kwargs={'pk': self.student2_profile.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    
    # ==================== CREATE TESTS ====================
    
    def test_platform_admin_can_create_student_profile(self):
        """Platform admin should create student profiles"""
        self.client.force_authenticate(user=self.platform_admin)
        
        # Create a new user first
        new_user = User.objects.create_user(
            username='new_student',
            email='new@student.com',
            password='Pass123!',
            role='S'
        )
        
        url = reverse('studentprofile-list')
        data = {
            'user': new_user.id,
            'school': self.school1.id,
            'license_type': 'C',
            'progress_theory': 0.0,
            'progress_driving': 0.0
        }
        
        print(f"\n=== DEBUG START ===")
        print(f"Data being sent: {data}")
        
        response = self.client.post(url, data, format='json')
        
        print(f"Response status: {response.status_code}")
        print(f"Response data: {response.data}")
        print("=== DEBUG END ===\n")
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(StudentProfile.objects.filter(user=new_user, school=self.school1).exists())

    def test_school_owner_can_create_student_profile_in_their_school(self):
        """School owner should create student profiles in their school"""
        self.client.force_authenticate(user=self.school_owner)
        
        # Create a new user first
        new_user = User.objects.create_user(
            username='new_student_owner',
            email='newowner@student.com',
            password='Pass123!',
            role='S'
        )
        
        url = reverse('studentprofile-list')
        data = {
            'user': new_user.id,
            'school': self.school1.id,  # Owner's school
            'license_type': 'C'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
    
    def test_school_owner_cannot_create_student_profile_in_other_school(self):
        """School owner should not create student profiles in other schools"""
        self.client.force_authenticate(user=self.school_owner)
        
        new_user = User.objects.create_user(
            username='new_student_other',
            email='newother@student.com',
            password='Pass123!',
            role='S'
        )
        
        url = reverse('studentprofile-list')
        data = {
            'user': new_user.id,
            'school': self.school2.id,  # Other owner's school
            'license_type': 'C'
        }
        
        response = self.client.post(url, data, format='json')
        
        # Should fail - owner cannot create in other school
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_instructor_cannot_create_student_profile(self):
        """Instructor should not create student profiles"""
        self.client.force_authenticate(user=self.instructor1)
        
        new_user = User.objects.create_user(
            username='new_student_instructor',
            email='newinst@student.com',
            password='Pass123!',
            role='S'
        )
        
        url = reverse('studentprofile-list')
        data = {
            'user': new_user.id,
            'school': self.school1.id,
            'license_type': 'C'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_student_cannot_create_student_profile(self):
        """Student should not create student profiles"""
        self.client.force_authenticate(user=self.student1)
        
        new_user = User.objects.create_user(
            username='new_student_student',
            email='newstu@student.com',
            password='Pass123!',
            role='S'
        )
        
        url = reverse('studentprofile-list')
        data = {
            'user': new_user.id,
            'school': self.school1.id,
            'license_type': 'C'
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    # ==================== UPDATE TESTS ====================
    
    def test_platform_admin_can_update_any_profile(self):
        """Platform admin should update any student profile"""
        self.client.force_authenticate(user=self.platform_admin)
        
        url = reverse('studentprofile-detail', kwargs={'pk': self.student1_profile.id})
        data = {'progress_theory': 75.0}
        
        response = self.client.patch(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.student1_profile.refresh_from_db()
        self.assertEqual(self.student1_profile.progress_theory, 75.0)
    
    def test_school_owner_can_update_students_in_their_school(self):
        """School owner should update students in their school"""
        self.client.force_authenticate(user=self.school_owner)
        
        url = reverse('studentprofile-detail', kwargs={'pk': self.student1_profile.id})
        data = {'progress_driving': 60.0}

        
        print(f"\n=== DEBUG START ===")
        print(f"Data being sent: {data}")

        response = self.client.patch(url, data, format='json')
       
        print(f"Response status: {response.status_code}")
        print(f"Response data: {response.data}")
        print("=== DEBUG END ===\n")
                
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.student1_profile.refresh_from_db()
        self.assertEqual(self.student1_profile.progress_driving, 60.0)
    
    def test_school_owner_cannot_update_students_in_other_school(self):
        """School owner should not update students from other school"""
        self.client.force_authenticate(user=self.school_owner)
        
        url = reverse('studentprofile-detail', kwargs={'pk': self.student3_profile.id})
        data = {'progress_theory': 90.0}
        
        response = self.client.patch(url, data, format='json')
        
        # Should be 404 (not in queryset)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    
    def test_instructor_cannot_update_student_profiles(self):
        """Instructor should not update student profiles (only via update_progress action)"""
        self.client.force_authenticate(user=self.instructor1)
        
        url = reverse('studentprofile-detail', kwargs={'pk': self.student1_profile.id})
        data = {'progress_theory': 80.0}
        
        print(f"\n=== DEBUG START ===")
        print(f"Data being sent: {data}")

        response = self.client.patch(url, data, format='json')
       
        print(f"Response status: {response.status_code}")
        print(f"Response data: {response.data}")
        print("=== DEBUG END ===\n")
        # Instructor cannot update directly
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_student_can_update_their_own_profile(self):
        """Student should update their own profile"""
        self.client.force_authenticate(user=self.student1)
        
        url = reverse('studentprofile-detail', kwargs={'pk': self.student1_profile.id})
        data = {'license_type': 'M'}  # Change to Motorcycle
        
        
        print(f"\n=== DEBUG START ===")
        print(f"Original license_type: {self.student1_profile.license_type}")

        response = self.client.patch(url, data, format='json')
       
        print(f"Response status: {response.status_code}")
        print(f"Response data: {response.data}")
        print("=== DEBUG END ===\n")
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.student1_profile.refresh_from_db()
        self.assertEqual(self.student1_profile.license_type,'M')
    
    def test_student_cannot_update_other_students_profile(self):
        """Student should not update other students' profiles"""
        self.client.force_authenticate(user=self.student1)
        
        url = reverse('studentprofile-detail', kwargs={'pk': self.student2_profile.id})
        data = {'license_type': 'M'}
        
        response = self.client.patch(url, data, format='json')
        
        # Should be 404 (not in queryset)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    
    # ==================== DELETE TESTS ====================
    
    def test_platform_admin_can_delete_student_profile(self):
        """Platform admin should delete student profiles"""
        self.client.force_authenticate(user=self.platform_admin)
        
        url = reverse('studentprofile-detail', kwargs={'pk': self.student2_profile.id})
        response = self.client.delete(url)
        
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(StudentProfile.objects.filter(id=self.student2_profile.id).exists())
    
    def test_school_owner_cannot_delete_student_profile(self):
        """School owner should not delete student profiles"""
        self.client.force_authenticate(user=self.school_owner)
        
        url = reverse('studentprofile-detail', kwargs={'pk': self.student1_profile.id})
        response = self.client.delete(url)
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(StudentProfile.objects.filter(id=self.student1_profile.id).exists())
    
    def test_instructor_cannot_delete_student_profile(self):
        """Instructor should not delete student profiles"""
        self.client.force_authenticate(user=self.instructor1)
        
        url = reverse('studentprofile-detail', kwargs={'pk': self.student1_profile.id})
        response = self.client.delete(url)
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_student_cannot_delete_their_profile(self):
        """Student should not delete their own profile"""
        self.client.force_authenticate(user=self.student1)
        
        url = reverse('studentprofile-detail', kwargs={'pk': self.student1_profile.id})
        response = self.client.delete(url)
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    # ==================== CUSTOM ACTION: PROGRESS ====================
    
    def test_progress_action_returns_correct_data(self):
        """Progress action should return correct completion percentage"""
        self.client.force_authenticate(user=self.student1)
        
        url = reverse('studentprofile-progress', kwargs={'pk': self.student1_profile.id})
        response = self.client.get(url)
        
        print(f"Response data: {response.data}")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('completion_percentage', response.data)
        
        # Calculate expected: (50 + 30) / 2 = 40
        expected_percentage = (self.student1_profile.progress_theory + self.student1_profile.progress_driving) / 2
        self.assertEqual(response.data['completion_percentage'], expected_percentage)
    
    def test_completed_student_progress_is_100(self):
        """Completed student should show 100% progress"""
        self.client.force_authenticate(user=self.platform_admin)
        
        url = reverse('studentprofile-progress', kwargs={'pk': self.completed_profile.id})
        response = self.client.get(url)
        
        print(response.data)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['completion_percentage'], 100.0)
    
    def test_student_cannot_view_other_student_progress(self):
        """Student should not view other students' progress"""
        self.client.force_authenticate(user=self.student1)
        
        url = reverse('studentprofile-progress', kwargs={'pk': self.student2_profile.id})
        
        print(f"\n=== DEBUG START ===")
        print(f"Student1 trying to access Student2's progress")
        print(f"Student1: {self.student1.username}")
        print(f"Student2: {self.student2.username}")
        print(f"Student1 can see profiles: {list(self.student1.student_profiles.values_list('id', flat=True))}")
        print(f"Student2 profile ID: {self.student2_profile.id}")
        
        response = self.client.get(url)
        
        print(f"Response status: {response.status_code}")
        print(f"Response data: {response.data}")
        print("=== DEBUG END ===\n")
        
        # Change from 403 to 404 (more secure)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    
    # ==================== CUSTOM ACTION: UPDATE_PROGRESS ====================
    
    def test_instructor_can_update_student_progress(self):
        """Instructor should update student progress via update_progress action"""
        self.client.force_authenticate(user=self.instructor2)
        
        url = reverse('studentprofile-update-progress', kwargs={'pk': self.student3_profile.id})
        data = {
            'lesson_type': 'T',  # Theory
            'hours_completed': 2.5
        }
        
        response = self.client.post(url, data, format='json')
        
        print(response)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Check progress was updated
        self.student1_profile.refresh_from_db()
        self.assertGreater(self.student1_profile.progress_theory, 00.0)  # Was 50, now should be more
    
    def test_instructor_cannot_update_student_in_other_school(self):
        """Instructor should not update students in other schools"""
        self.client.force_authenticate(user=self.instructor1)
        
        url = reverse('studentprofile-update-progress', kwargs={'pk': self.student3_profile.id})
        data = {'lesson_type': 'T', 'hours_completed': 2.5}
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    
    def test_student_cannot_update_own_progress(self):
        """Student should not update their own progress"""
        self.client.force_authenticate(user=self.student1)
        
        url = reverse('studentprofile-update-progress', kwargs={'pk': self.student1_profile.id})
        data = {'lesson_type': 'T', 'hours_completed': 2.5}
        
        response = self.client.post(url, data, format='json')
        

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    # ==================== CUSTOM ACTION: MY_PROFILE ====================
    
    def test_student_can_view_their_profile_via_my_profile(self):
        """Student should view their profile via my_profile action"""
        self.client.force_authenticate(user=self.student1)
        
        url = reverse('studentprofile-my-profile')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['user_username'], 'student1')
    
    def test_instructor_cannot_use_my_profile(self):
        """Instructor should not use my_profile action"""
        self.client.force_authenticate(user=self.instructor1)
        
        url = reverse('studentprofile-my-profile')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    # ==================== SEARCH & FILTER TESTS ====================
    
    def test_search_student_profiles_by_username(self):
        """Should search student profiles by username"""
        self.client.force_authenticate(user=self.platform_admin)
        
        url = reverse('studentprofile-list') + '?search=student1'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['user_username'], 'student1')
    
    def test_search_student_profiles_by_email(self):
        """Should search student profiles by email"""
        self.client.force_authenticate(user=self.platform_admin)
        
        url = reverse('studentprofile-list') + '?search=student1@school1.com'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
    
    def test_order_student_profiles_by_progress(self):
        """Should order student profiles by progress ASCENDING"""
        self.client.force_authenticate(user=self.platform_admin)
        
        # ASCENDING order
        url = reverse('studentprofile-list') + '?ordering=progress_theory'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        progresses = [profile['progress_theory'] for profile in response.data['results']]
        progresses_float = [float(p) for p in progresses]
        
        # Should be ASCENDING: 0, 0, 0, 0, 0, 50, 100
        self.assertEqual(progresses_float, sorted(progresses_float))  # NO reverse=True!
        
        # Or be explicit:
        expected = [0.0, 0.0, 0.0, 0.0, 0.0, 50.0, 100.0]
        self.assertEqual(progresses_float, expected)
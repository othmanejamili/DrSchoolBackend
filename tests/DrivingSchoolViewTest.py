import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase, APIClient
from django.contrib.auth import get_user_model
from django.utils import timezone
from DriveApp.models import User, DrivingSchool, StudentProfile, SubscriptionPlan, SchoolSubscription

User = get_user_model()


class DrivingSchoolViewSetTests(APITestCase):
    """Test suite for DrivingSchool CRUD operations and permissions"""
    
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
        
        # Create School Owner (also admin)
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
        
        # Create Driving School 1
        self.school1 = DrivingSchool.objects.create(
            name='Elite Driving School',
            email='contact@elite.com',
            address='123 Main St',
            phone_number='+1234567890',
            owner=self.school_owner
        )
        
        # Create Driving School 2
        self.school2 = DrivingSchool.objects.create(
            name='Pro Driving Academy',
            email='contact@pro.com',
            address='456 Oak Ave',
            phone_number='+0987654321',
            owner=self.other_owner
        )
        
        # Create Subscription Plan
        self.plan = SubscriptionPlan.objects.create(
            name='Basic Plan',
            price=99.99,
            max_students=50,
            max_instructors=5,
            duration_days=30
        )
        
        # Create School Subscription
        self.subscription1 = SchoolSubscription.objects.create(
            school=self.school1,
            plan=self.plan,
            status='active',
            current_period_start=timezone.now(),
            current_period_end=timezone.now() + timezone.timedelta(days=30)
        )
        
        # Create Instructor for School 1
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
        
        # Create Instructor for School 2
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
        
        # Create Student for School 1
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
        
        # Create Student for School 2
        self.student2 = User.objects.create_user(
            username='student2',
            email='student2@school2.com',
            password='StudentPass123!',
            role='S'
        )
        
        self.student2_profile = StudentProfile.objects.create(
            user=self.student2,
            school=self.school2,
            status='A'
        )
        
        # API Client
        self.client = APIClient()

    # ==================== LIST TESTS ====================
    
    def test_platform_admin_can_list_all_schools(self):
        """Platform admin should see all schools"""
        self.client.force_authenticate(user=self.platform_admin)
        
        url = reverse('drivingschool-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 2)
        
        school_names = [school['name'] for school in response.data['results']]
        self.assertIn('Elite Driving School', school_names)
        self.assertIn('Pro Driving Academy', school_names)

    def test_school_owner_can_see_own_school(self):
        """School owner should only see their own school"""
        self.client.force_authenticate(user=self.school_owner)
        
        url = reverse('drivingschool-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should see only their school
        school_names = [school['name'] for school in response.data['results']]
        self.assertIn('Elite Driving School', school_names)
        self.assertNotIn('Pro Driving Academy', school_names)

    def test_instructor_can_see_their_school(self):
        """Instructor should see only their school"""
        self.client.force_authenticate(user=self.instructor1)
        
        url = reverse('drivingschool-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['name'], 'Elite Driving School')

    def test_student_can_see_their_school(self):
        """Student should see only their school"""
        self.client.force_authenticate(user=self.student1)
        
        url = reverse('drivingschool-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['name'], 'Elite Driving School')

    def test_unauthenticated_user_cannot_list_schools(self):
        """Unauthenticated users should not access schools"""
        url = reverse('drivingschool-list')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    # ==================== CREATE TESTS ====================
    
    def test_platform_admin_can_create_school(self):
        """Platform admin should be able to create schools"""
        self.client.force_authenticate(user=self.platform_admin)
        
        url = reverse('drivingschool-list')
        data = {
            'name': 'New Driving School',
            'email': 'new@school.com',
            'address': '789 Pine Rd',
            'phone_number': '+1122334455',
            'owner': self.platform_admin.id
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(DrivingSchool.objects.count(), 3)
        self.assertTrue(DrivingSchool.objects.filter(name='New Driving School').exists())

    def test_instructor_cannot_create_school(self):
        """Instructor should not be able to create schools"""
        self.client.force_authenticate(user=self.instructor1)
        
        url = reverse('drivingschool-list')
        data = {
            'name': 'Unauthorized School',
            'email': 'unauthorized@school.com',
            'address': '999 Fake St',
            'phone_number': '+9999999999',
            'owner': self.instructor1.id
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(DrivingSchool.objects.count(), 2)

    def test_student_cannot_create_school(self):
        """Student should not be able to create schools"""
        self.client.force_authenticate(user=self.student1)
        
        url = reverse('drivingschool-list')
        data = {
            'name': 'Unauthorized School',
            'email': 'unauthorized@school.com',
            'owner': self.student1.id
        }
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    # ==================== RETRIEVE TESTS ====================
    
    def test_platform_admin_can_retrieve_any_school(self):
        """Platform admin should retrieve any school"""
        self.client.force_authenticate(user=self.platform_admin)
        
        url = reverse('drivingschool-detail', kwargs={'pk': self.school1.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], 'Elite Driving School')

    def test_owner_can_retrieve_own_school(self):
        """Owner should retrieve their own school"""
        self.client.force_authenticate(user=self.school_owner)
        
        url = reverse('drivingschool-detail', kwargs={'pk': self.school1.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], 'Elite Driving School')

    def test_owner_cannot_retrieve_other_school(self):
        """Owner should not retrieve another school"""
        self.client.force_authenticate(user=self.school_owner)
        
        url = reverse('drivingschool-detail', kwargs={'pk': self.school2.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_instructor_can_retrieve_their_school(self):
        """Instructor should retrieve their school"""
        self.client.force_authenticate(user=self.instructor1)
        
        url = reverse('drivingschool-detail', kwargs={'pk': self.school1.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_student_can_retrieve_their_school(self):
        """Student should retrieve their school"""
        self.client.force_authenticate(user=self.student1)
        
        url = reverse('drivingschool-detail', kwargs={'pk': self.school1.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    # ==================== UPDATE TESTS ====================
    
    def test_platform_admin_can_update_any_school(self):
        """Platform admin should update any school"""
        self.client.force_authenticate(user=self.platform_admin)
        
        url = reverse('drivingschool-detail', kwargs={'pk': self.school1.id})
        data = {'name': 'Updated Elite School'}
        
        response = self.client.patch(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.school1.refresh_from_db()
        self.assertEqual(self.school1.name, 'Updated Elite School')

    def test_owner_can_update_own_school(self):
        """Owner should update their own school"""
        self.client.force_authenticate(user=self.school_owner)
        
        url = reverse('drivingschool-detail', kwargs={'pk': self.school1.id})
        data = {'address': '999 Updated St'}
        
        response = self.client.patch(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.school1.refresh_from_db()
        self.assertEqual(self.school1.address, '999 Updated St')

    def test_owner_cannot_update_other_school(self):
        """Owner should not update another school"""
        self.client.force_authenticate(user=self.school_owner)
        
        url = reverse('drivingschool-detail', kwargs={'pk': self.school2.id})
        data = {'name': 'Hacked School'}
        
        response = self.client.patch(url, data, format='json')
        
        # Should be 404 because school2 is not in owner's queryset
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_instructor_can_update_their_school(self):
        """Instructor should update their school"""
        self.client.force_authenticate(user=self.instructor1)
        
        url = reverse('drivingschool-detail', kwargs={'pk': self.school1.id})
        data = {'phone_number': '+1111111111'}
        
        response = self.client.patch(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.school1.refresh_from_db()
        self.assertEqual(self.school1.phone_number, '+1111111111')

    def test_student_cannot_update_school(self):
        """Student should not update their school"""
        self.client.force_authenticate(user=self.student1)
        
        url = reverse('drivingschool-detail', kwargs={'pk': self.school1.id})
        data = {'name': 'Unauthorized Update'}
        
        response = self.client.patch(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.school1.refresh_from_db()
        self.assertNotEqual(self.school1.name, 'Unauthorized Update')

    # ==================== DELETE TESTS ====================
    
    def test_platform_admin_can_delete_school(self):
        """Platform admin should delete schools"""
        self.client.force_authenticate(user=self.platform_admin)
        
        url = reverse('drivingschool-detail', kwargs={'pk': self.school2.id})
        response = self.client.delete(url)
        
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(DrivingSchool.objects.filter(id=self.school2.id).exists())

    def test_owner_cannot_delete_school(self):
        """Owner should not delete their school"""
        self.client.force_authenticate(user=self.school_owner)
        
        url = reverse('drivingschool-detail', kwargs={'pk': self.school1.id})
        response = self.client.delete(url)
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(DrivingSchool.objects.filter(id=self.school1.id).exists())

    def test_instructor_cannot_delete_school(self):
        """Instructor should not delete school"""
        self.client.force_authenticate(user=self.instructor1)
        
        url = reverse('drivingschool-detail', kwargs={'pk': self.school1.id})
        response = self.client.delete(url)
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_student_cannot_delete_school(self):
        """Student should not delete school"""
        self.client.force_authenticate(user=self.student1)
        
        url = reverse('drivingschool-detail', kwargs={'pk': self.school1.id})
        response = self.client.delete(url)
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    # ==================== CUSTOM ENDPOINT: STUDENTS ====================
    
    def test_platform_admin_can_view_school_students(self):
        """Platform admin should view any school's students"""
        self.client.force_authenticate(user=self.platform_admin)
        
        url = reverse('drivingschool-students', kwargs={'pk': self.school1.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(response.data['results']), 1)

    def test_owner_can_view_own_school_students(self):
        """Owner should view their school's students"""
        self.client.force_authenticate(user=self.school_owner)
        
        url = reverse('drivingschool-students', kwargs={'pk': self.school1.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should see at least the student and instructor profiles
        self.assertGreaterEqual(len(response.data['results']), 1)

    def test_owner_cannot_view_other_school_students(self):
        """Owner should not view other school's students"""
        self.client.force_authenticate(user=self.school_owner)
        
        url = reverse('drivingschool-students', kwargs={'pk': self.school2.id})
        response = self.client.get(url)
        
        # Should be 404 because school2 is not in owner's queryset
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_instructor_cannot_view_school_students(self):
        """Instructor should not access students list endpoint"""
        self.client.force_authenticate(user=self.instructor1)
        
        url = reverse('drivingschool-students', kwargs={'pk': self.school1.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_student_cannot_view_school_students(self):
        """Student should not access students list endpoint"""
        self.client.force_authenticate(user=self.student1)
        
        url = reverse('drivingschool-students', kwargs={'pk': self.school1.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    # ==================== CUSTOM ENDPOINT: STATS ====================
    
    def test_platform_admin_can_view_school_stats(self):
        """Platform admin should view any school's stats"""
        self.client.force_authenticate(user=self.platform_admin)
        
        url = reverse('drivingschool-stats', kwargs={'pk': self.school1.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('total_students', response.data)
        self.assertIn('active_students', response.data)
        self.assertIn('total_instructors', response.data)
        self.assertIn('subscription_status', response.data)

    def test_owner_can_view_own_school_stats(self):
        """Owner should view their school's stats"""
        self.client.force_authenticate(user=self.school_owner)
        
        url = reverse('drivingschool-stats', kwargs={'pk': self.school1.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('total_students', response.data)
        self.assertEqual(response.data['school_name'], 'Elite Driving School')

    def test_owner_cannot_view_other_school_stats(self):
        """Owner should not view other school's stats"""
        self.client.force_authenticate(user=self.school_owner)
        
        url = reverse('drivingschool-stats', kwargs={'pk': self.school2.id})
        response = self.client.get(url)
        
        # Should be 404 because school2 is not in owner's queryset
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_instructor_cannot_view_school_stats(self):
        """Instructor should not view school stats"""
        self.client.force_authenticate(user=self.instructor1)
        
        url = reverse('drivingschool-stats', kwargs={'pk': self.school1.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_student_cannot_view_school_stats(self):
        """Student should not view school stats"""
        self.client.force_authenticate(user=self.student1)
        
        url = reverse('drivingschool-stats', kwargs={'pk': self.school1.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    # ==================== SEARCH & FILTER TESTS ====================
    
    def test_search_schools_by_name(self):
        """Should be able to search schools by name"""
        self.client.force_authenticate(user=self.platform_admin)
        
        url = reverse('drivingschool-list') + '?search=Elite'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['name'], 'Elite Driving School')

    def test_search_schools_by_email(self):
        """Should be able to search schools by email"""
        self.client.force_authenticate(user=self.platform_admin)
        
        url = reverse('drivingschool-list') + '?search=contact@pro.com'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['email'], 'contact@pro.com')

    def test_ordering_schools_by_name(self):
        """Should be able to order schools by name"""
        self.client.force_authenticate(user=self.platform_admin)
        
        url = reverse('drivingschool-list') + '?ordering=name'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        school_names = [school['name'] for school in response.data['results']]
        self.assertEqual(school_names, sorted(school_names))

    def test_ordering_schools_by_created_at_desc(self):
        """Should be able to order schools by creation date descending"""
        self.client.force_authenticate(user=self.platform_admin)
        
        url = reverse('drivingschool-list') + '?ordering=-created_at'
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Just verify it doesn't error
        self.assertGreaterEqual(len(response.data['results']), 2)

    # ==================== EDGE CASES ====================
    
    def test_stats_shows_correct_student_count(self):
        """Stats should show accurate student counts"""
        self.client.force_authenticate(user=self.platform_admin)
        
        # Add more students to school1
        for i in range(3):
            user = User.objects.create_user(
                username=f'extra_student{i}',
                email=f'extra{i}@test.com',
                password='Pass123!',
                role='S'
            )
            StudentProfile.objects.create(
                user=user,
                school=self.school1,
                status='A'
            )
        
        url = reverse('drivingschool-stats', kwargs={'pk': self.school1.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # 1 original student + 3 new students + 1 instructor = 5 total profiles
        # But only 4 are students (role='S')
        self.assertEqual(response.data['active_students'], 4)

    def test_stats_counts_instructors_correctly(self):
        """Stats should count instructors correctly"""
        self.client.force_authenticate(user=self.platform_admin)
        
        # Add another instructor
        instructor3 = User.objects.create_user(
            username='instructor3',
            email='instructor3@school1.com',
            password='Pass123!',
            role='I'
        )
        StudentProfile.objects.create(
            user=instructor3,
            school=self.school1,
            status='A'
        )
        
        url = reverse('drivingschool-stats', kwargs={'pk': self.school1.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['total_instructors'], 2)

    def test_school_without_subscription_shows_no_subscription(self):
        """Stats should handle schools without subscriptions"""
        self.client.force_authenticate(user=self.platform_admin)
        
        url = reverse('drivingschool-stats', kwargs={'pk': self.school2.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['subscription_status'], 'No subscription')

    def test_stats_includes_subscription_details(self):
        """Stats should include subscription plan and capacity"""
        self.client.force_authenticate(user=self.platform_admin)
        
        url = reverse('drivingschool-stats', kwargs={'pk': self.school1.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('subscription_plan', response.data)
        self.assertIn('student_capacity', response.data)
        self.assertIn('instructor_capacity', response.data)
        self.assertIn('utilization_percentage', response.data)
        
        # Check specific values
        self.assertEqual(response.data['subscription_plan'], 'Basic Plan')
        self.assertEqual(response.data['student_capacity'], 50)
        self.assertEqual(response.data['instructor_capacity'], 5)

    def test_stats_for_school_without_subscription(self):
        """Stats should handle schools without subscriptions gracefully"""
        self.client.force_authenticate(user=self.platform_admin)
        
        url = reverse('drivingschool-stats', kwargs={'pk': self.school2.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['subscription_status'], 'No subscription')
        self.assertIsNone(response.data['subscription_plan'])
        self.assertIsNone(response.data['student_capacity'])
        self.assertIsNone(response.data['utilization_percentage'])

#==========================Subscription TEST ===================================
    def test_school_cannot_exceed_student_capacity(self):
        """School should not be able to register more students than subscription allows"""
        # Create a SMALL plan for faster testing (3 students max)
        small_plan = SubscriptionPlan.objects.create(
            name='Small Test Plan',
            price=29.99,
            max_students=3,  # ONLY 3 STUDENTS!
            max_instructors=2,
            duration_days=30
        )
        
        # Update school1 to use small plan
        self.subscription1.plan = small_plan
        self.subscription1.save()
        
        # Authenticate as platform admin
        self.client.force_authenticate(user=self.platform_admin)
        
        # School already has: student1 (1 student)
        # Register student #2
        data1 = {
            'username': 'student_2',
            'email': 'student2@test.com',
            'password': 'Pass123!',
            'confirm_password':'Pass123!',
            'driving_school_id': self.school1.id
        }
        
        url = reverse('user-register-student')
        response1 = self.client.post(url, data1, format='json')
        self.assertEqual(response1.status_code, status.HTTP_201_CREATED)
        
        # Register student #3 (last available spot)
        data2 = {
            'username': 'student_3',
            'email': 'student3@test.com',
            'password': 'Pass123!',
            'confirm_password':'Pass123!',
            'driving_school_id': self.school1.id
        }
        
        response2 = self.client.post(url, data2, format='json')
        self.assertEqual(response2.status_code, status.HTTP_201_CREATED)
        
        # Now try to register student #4 (OVER CAPACITY!)
        data3 = {
            'username': 'student_4_over_capacity',
            'email': 'student4@test.com',
            'password': 'Pass123!',
            'confirm_password':'Pass123!',
            'driving_school_id': self.school1.id
        }
        
        response3 = self.client.post(url, data3, format='json')
        
        # Should fail with 400 Bad Request
        self.assertEqual(response3.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response3.data)
        self.assertIn('student limit', response3.data['error'].lower())
        
        # Verify only 3 students exist
        student_count = StudentProfile.objects.filter(
            school=self.school1,
            user__role='S'
        ).count()
        self.assertEqual(student_count, 3)
        

    def test_student_capacity_limit(self):
        """Test that student registration respects subscription limits"""
        self.client.force_authenticate(user=self.platform_admin)
        
        # First, check current student count
        current_students = self.school1.student_profiles.filter(user__role='S').count()
        print(f"Current students: {current_students}")
        print(f"Capacity: {self.plan.max_students}")
        
        # Fill to capacity
        students_to_create = self.plan.max_students - current_students
        
        for i in range(students_to_create):
            data = {
                'username': f'fill_student_{i}',
                'email': f'fill{i}@test.com',
                'password': 'Pass123!',
                'confirm_password':'Pass123!',
                'driving_school_id': self.school1.id
            }
            
            url = reverse('user-register-student')
            response = self.client.post(url, data, format='json')
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # Try one more (should fail)
        data = {
            'username': 'over_capacity_student',
            'email': 'over@capacity.com',
            'password': 'Pass123!',
            'confirm_password':'Pass123!',
            'driving_school_id': self.school1.id
        }
        
        url = reverse('user-register-student')
        response = self.client.post(url, data, format='json')
        
        # Should fail
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        print(f"Over capacity response: {response.data}")
class DrivingSchoolPermissionsIsolationTests(APITestCase):
    """Test that schools are properly isolated from each other"""
    
    def setUp(self):
        """Create two separate schools with their own users"""
        # School 1 setup
        self.owner1 = User.objects.create_user(
            username='owner1', email='owner1@test.com', password='Pass123!', role='A'
        )
        self.school1 = DrivingSchool.objects.create(
            name='School One', email='school1@test.com', owner=self.owner1
        )
        self.instructor1 = User.objects.create_user(
            username='instructor1', email='inst1@school1.com', password='Pass123!', role='I'
        )
        StudentProfile.objects.create(user=self.instructor1, school=self.school1, status='A')
        
        # School 2 setup
        self.owner2 = User.objects.create_user(
            username='owner2', email='owner2@test.com', password='Pass123!', role='A'
        )
        self.school2 = DrivingSchool.objects.create(
            name='School Two', email='school2@test.com', owner=self.owner2
        )
        self.instructor2 = User.objects.create_user(
            username='instructor2', email='inst2@school2.com', password='Pass123!', role='I'
        )
        StudentProfile.objects.create(user=self.instructor2, school=self.school2, status='A')
        
        self.client = APIClient()
    
    def test_instructor_cannot_see_other_schools(self):
        """Instructor from school1 should not see school2"""
        self.client.force_authenticate(user=self.instructor1)
        
        url = reverse('drivingschool-list')
        response = self.client.get(url)
        
        school_names = [school['name'] for school in response.data['results']]
        self.assertIn('School One', school_names)
        self.assertNotIn('School Two', school_names)
    
    def test_owner_cannot_update_other_schools(self):
        """Owner of school1 should not update school2"""
        self.client.force_authenticate(user=self.owner1)
        
        url = reverse('drivingschool-detail', kwargs={'pk': self.school2.id})
        data = {'name': 'Hacked School'}
        response = self.client.patch(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.school2.refresh_from_db()
        self.assertEqual(self.school2.name, 'School Two')
    
    def test_instructor_cannot_access_other_school_detail(self):
        """Instructor should get 404 when accessing other school"""
        self.client.force_authenticate(user=self.instructor1)
        
        url = reverse('drivingschool-detail', kwargs={'pk': self.school2.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)




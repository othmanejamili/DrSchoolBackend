"""
Comprehensive tests for CommunicationTemplateViewSet and AutomatedMessageViewSet
"""

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from datetime import datetime, timedelta
import json

from DriveApp.models import (
    User, DrivingSchool, StudentProfile, CommunicationTemplate,
    AutomatedMessage
)
from DriveApp.services import CommunicationService, CommunicationTemplateService


class CommunicationTemplateViewSetTestCase(APITestCase):
    """Comprehensive tests for CommunicationTemplateViewSet"""

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
            status='A'
        )
        
        self.student2_profile = StudentProfile.objects.create(
            user=self.student2,
            school=self.school1,
            status='A'
        )
        
        # Create communication templates
        self.template1 = CommunicationTemplate.objects.create(
            school=self.school1,
            name='Welcome Email',
            template_type='lesson_reminder',
            subject='Welcome to {school_name}, {student_name}!',
            body='Hello {student_name},\n\nWelcome to {school_name}.',
            is_active=True
        )
        
        self.template2 = CommunicationTemplate.objects.create(
            school=self.school1,
            name='Progress Update',
            template_type='progress_update',
            subject='Your Progress Update: {progress_theory}% theory',
            body='Dear {student_name},\n\nYour theory progress is {progress_theory}%.',
            is_active=True
        )
        
        self.template3 = CommunicationTemplate.objects.create(
            school=self.school1,
            name='Inactive Template',
            template_type='birthday',
            subject='Happy Birthday!',
            body='Happy Birthday {student_name}!',
            is_active=False
        )
        
        self.template4 = CommunicationTemplate.objects.create(
            school=self.school2,
            name='School 2 Template',
            template_type='lesson_reminder',
            subject='School 2 Template',
            body='This is a school 2 template.',
            is_active=True
        )
        
        # Create messages for statistics
        self.message1 = AutomatedMessage.objects.create(
            student=self.student1_profile,
            template=self.template1,
            scheduled_for=timezone.now() + timedelta(days=1),
            status='sent'
        )
        
        self.message2 = AutomatedMessage.objects.create(
            student=self.student2_profile,
            template=self.template1,
            scheduled_for=timezone.now() + timedelta(days=2),
            status='sent',
            sent_at=timezone.now()
        )
        
        # API client
        self.client = APIClient()
        
        # URLs
        self.list_url = reverse('communicationtemplate-list')
        self.detail_url = lambda pk: reverse('communicationtemplate-detail', kwargs={'pk': pk})
        self.available_variables_url = reverse('communicationtemplate-available-variables')
        self.duplicate_url = lambda pk: reverse('communicationtemplate-duplicate', kwargs={'pk': pk})
        self.preview_url = lambda pk: reverse('communicationtemplate-preview', kwargs={'pk': pk})
        self.toggle_active_url = lambda pk: reverse('communicationtemplate-toggle-active', kwargs={'pk': pk})
        self.by_type_url = reverse('communicationtemplate-by-type')
        self.usage_stats_url = reverse('communicationtemplate-usage-stats')
        self.my_school_templates_url = reverse('communicationtemplate-my-school-templates')

    def tearDown(self):
        """Clean up after tests"""
        AutomatedMessage.objects.all().delete()
        CommunicationTemplate.objects.all().delete()
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
        """✅ Test that unauthenticated users cannot access templates"""
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_platform_admin_sees_all_templates(self):
        """✅ Platform admin should see all templates"""
        self.client.force_authenticate(user=self.platform_admin)
        response = self.client.get(self.list_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        results = self.get_results(response.data)
        self.assertEqual(len(results), CommunicationTemplate.objects.count())

    def test_school_owner_sees_only_their_templates(self):
        """✅ School owner should only see templates in their schools"""
        self.client.force_authenticate(user=self.school_owner1)
        response = self.client.get(self.list_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        results = self.get_results(response.data)
        expected_count = CommunicationTemplate.objects.filter(
            school__owner=self.school_owner1
        ).count()
        self.assertEqual(len(results), expected_count)
        
        # Verify only school1 templates
        template_ids = [template['id'] for template in results]
        self.assertIn(self.template1.id, template_ids)
        self.assertIn(self.template2.id, template_ids)
        self.assertIn(self.template3.id, template_ids)
        self.assertNotIn(self.template4.id, template_ids)  # school2 template

    def test_instructor_sees_only_their_school_templates(self):
        """✅ Instructor should see templates from their school only"""
        self.client.force_authenticate(user=self.instructor1)
        response = self.client.get(self.list_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        results = self.get_results(response.data)
        expected_count = CommunicationTemplate.objects.filter(
            school=self.school1
        ).count()
        self.assertEqual(len(results), expected_count)

    def test_student_cannot_access_templates(self):
        """✅ Student cannot access templates"""
        self.client.force_authenticate(user=self.student1)
        response = self.client.get(self.list_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = self.get_results(response.data)
        self.assertEqual(len(results), 0)  # Empty queryset

    # ==================== LIST TEMPLATES TESTS ====================

    def test_list_templates_success(self):
        """✅ Test listing templates returns correct data"""
        self.client.force_authenticate(user=self.school_owner1)
        response = self.client.get(self.list_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        results = self.get_results(response.data)
        
        # Check template data structure
        template = results[0]
        self.assertIn('id', template)
        self.assertIn('school', template)
        self.assertIn('name', template)
        self.assertIn('template_type', template)
        self.assertIn('subject', template)
        self.assertIn('body', template)
        self.assertIn('is_active', template)
        self.assertIn('created_at', template)
        self.assertIn('usage_count', template)

    def test_list_templates_with_filters(self):
        """✅ Test filtering templates"""
        self.client.force_authenticate(user=self.school_owner1)
        
        # Filter by template type
        response = self.client.get(self.list_url, {'template_type': 'lesson_reminder'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = self.get_results(response.data)
        self.assertEqual(len(results), 1)  # Only template1
        
        # Filter by is_active
        response = self.client.get(self.list_url, {'is_active': 'true'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = self.get_results(response.data)
        self.assertEqual(len(results), 2)  # template1 and template2
        
        # Filter by school
        response = self.client.get(self.list_url, {'school': self.school1.id})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = self.get_results(response.data)
        self.assertEqual(len(results), 3)  # All school1 templates

    def test_list_templates_with_search(self):
        """✅ Test searching templates"""
        self.client.force_authenticate(user=self.school_owner1)
        
        # Search by name
        response = self.client.get(self.list_url, {'search': 'Welcome'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = self.get_results(response.data)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['name'], 'Welcome Email')
        
        # Search by subject
        response = self.client.get(self.list_url, {'search': 'Progress Update'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = self.get_results(response.data)
        self.assertEqual(len(results), 1)
        
        # Search by body content
        response = self.client.get(self.list_url, {'search': 'Welcome to'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = self.get_results(response.data)
        self.assertEqual(len(results), 1)

    def test_list_templates_with_ordering(self):
        """✅ Test ordering templates"""
        self.client.force_authenticate(user=self.school_owner1)
        
        # Order by name ascending
        response = self.client.get(self.list_url, {'ordering': 'name'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        results = self.get_results(response.data)
        names = [template['name'] for template in results]
        self.assertEqual(names, sorted(names))
        
        # Order by created_at descending (default)
        response = self.client.get(self.list_url, {'ordering': '-created_at'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        results = self.get_results(response.data)
        # Check ordering (most recent first)
        created_dates = [template['created_at'] for template in results]
        # Note: For simplicity, we're checking the order exists

    # ==================== RETRIEVE TEMPLATE TESTS ====================

    def test_retrieve_template_success(self):
        """✅ Test retrieving a single template"""
        self.client.force_authenticate(user=self.school_owner1)
        response = self.client.get(self.detail_url(self.template1.pk))
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['school'], self.school1.id)
        self.assertEqual(response.data['name'], 'Welcome Email')
        self.assertEqual(response.data['template_type'], 'lesson_reminder')
        self.assertTrue(response.data['is_active'])

    def test_retrieve_template_not_found(self):
        """✅ Test retrieving non-existent template"""
        self.client.force_authenticate(user=self.platform_admin)
        response = self.client.get(self.detail_url(99999))
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_retrieve_template_no_permission(self):
        """✅ School owner cannot retrieve template from another school"""
        self.client.force_authenticate(user=self.school_owner1)
        response = self.client.get(self.detail_url(self.template4.pk))  # school2 template
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    # ==================== CREATE TEMPLATE TESTS ====================

    def test_create_template_as_platform_admin(self):
        """✅ Platform admin can create template for any school"""
        self.client.force_authenticate(user=self.platform_admin)
        
        data = {
            'school': self.school2.id,  # school2
            'name': 'New Template',
            'template_type': 'payment_reminder',
            'subject': 'Payment Due: {student_name}',
            'body': 'Dear {student_name},\n\nYour payment is due.',
            'is_active': True
        }
        
        response = self.client.post(self.list_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(CommunicationTemplate.objects.count(), 5)  # Started with 4
        self.assertEqual(response.data['school'], self.school2.id)
        self.assertEqual(response.data['name'], 'New Template')

    def test_create_template_as_school_owner(self):
        """✅ School owner can create template for their school"""
        self.client.force_authenticate(user=self.school_owner1)
        
        data = {
            'school': self.school1.id,  # Their school
            'name': 'Owner Template',
            'template_type': 'achievement',
            'subject': 'Achievement Unlocked!',
            'body': 'Congratulations {student_name}!',
            'is_active': True
        }
        
        response = self.client.post(self.list_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['school'], self.school1.id)

    def test_create_template_school_owner_wrong_school(self):
        """✅ School owner cannot create template for other schools"""
        self.client.force_authenticate(user=self.school_owner1)
        
        data = {
            'school': self.school2.id,  # Not their school
            'name': 'Invalid Template',
            'template_type': 'lesson_reminder',
            'subject': 'Test',
            'body': 'Test',
            'is_active': True
        }
        
        response = self.client.post(self.list_url, data, format='json')
        
        print("#"*100)
        print(response.data)
        print(response)
        print("#"*100)


        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_template_as_instructor_denied(self):
        """✅ Instructor cannot create templates"""
        self.client.force_authenticate(user=self.instructor1)
        
        data = {
            'school': self.school1.id,
            'name': 'Instructor Template',
            'template_type': 'lesson_reminder',
            'subject': 'Test',
            'body': 'Test',
            'is_active': True
        }
        
        response = self.client.post(self.list_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_create_template_as_student_denied(self):
        """✅ Student cannot create templates"""
        self.client.force_authenticate(user=self.student1)
        
        data = {
            'school': self.school1.id,
            'name': 'Student Template',
            'template_type': 'lesson_reminder',
            'subject': 'Test',
            'body': 'Test',
            'is_active': True
        }
        
        response = self.client.post(self.list_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_create_duplicate_template_name(self):
        """✅ Cannot create template with duplicate name in same school"""
        self.client.force_authenticate(user=self.platform_admin)
        
        data = {
            'school': self.school1.id,
            'name': 'Welcome Email',  # Already exists
            'template_type': 'lesson_reminder',
            'subject': 'Duplicate',
            'body': 'Should fail',
            'is_active': True
        }
        
        response = self.client.post(self.list_url, data, format='json')
        
        print("#"*100)
        print(response.data)
        print(response)
        print("#"*100)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('name', response.data)
 
    def test_create_template_different_school_same_name(self):
        """✅ Can create template with same name in different school"""
        self.client.force_authenticate(user=self.platform_admin)
        
        data = {
            'school': self.school2.id,
            'name': 'Welcome Email',  # Same name as school1 template
            'template_type': 'lesson_reminder',
            'subject': 'Welcome to School 2',
            'body': 'Welcome message for school 2.',
            'is_active': True
        }
        
        response = self.client.post(self.list_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['name'], 'Welcome Email')

    def test_create_template_empty_body(self):
        """✅ Cannot create template with empty body"""
        self.client.force_authenticate(user=self.platform_admin)
        
        data = {
            'school': self.school1.id,
            'name': 'Empty Body Template',
            'template_type': 'lesson_reminder',
            'subject': 'Test Subject',
            'body': '',  # Empty body
            'is_active': True
        }
        
        response = self.client.post(self.list_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('body', response.data)

    def test_create_template_missing_required_fields(self):
        """✅ Cannot create template without required fields"""
        self.client.force_authenticate(user=self.platform_admin)
        
        # Missing name
        data = {
            'school': self.school1.id,
            'template_type': 'lesson_reminder',
            'subject': 'Test',
            'body': 'Test'
        }
        
        response = self.client.post(self.list_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('name', response.data)

    def test_create_template_with_variables(self):
        """✅ Can create template with variables"""
        self.client.force_authenticate(user=self.platform_admin)
        
        data = {
            'school': self.school1.id,
            'name': 'Template with Variables',
            'template_type': 'progress_update',
            'subject': 'Progress: {progress_theory}% theory, {progress_driving}% driving',
            'body': 'Hello {student_name},\n\nYour progress at {school_name}:\n- Theory: {progress_theory}%\n- Driving: {progress_driving}%',
            'is_active': True
        }
        
        response = self.client.post(self.list_url, data, format='json')
        
        print("#"*100)
        print(response.data)
        print(response)
        print("#"*100)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('variables', response.data)
        self.assertIn('student_name', response.data['variables'])
        self.assertIn('progress_theory', response.data['variables'])

    # ==================== UPDATE TEMPLATE TESTS ====================

    def test_update_template_as_platform_admin(self):
        """✅ Platform admin can update any template"""
        self.client.force_authenticate(user=self.platform_admin)
        
        data = {
            'name': 'Updated Template Name',
            'subject': 'Updated Subject',
            'body':'Hello {student_name},\n\nWelcome to {school_name}.',
            'is_active': False
        }
        
        response = self.client.patch(
            self.detail_url(self.template1.pk), 
            data, 
            format='json'
        )


        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], 'Updated Template Name')
        self.assertEqual(response.data['subject'], 'Updated Subject')
        self.assertFalse(response.data['is_active'])
        
        # Refresh from DB
        self.template1.refresh_from_db()
        self.assertEqual(self.template1.name, 'Updated Template Name')

    def test_update_template_as_school_owner(self):
        """✅ School owner can update templates in their schools"""
        self.client.force_authenticate(user=self.school_owner1)
        
        data = {'name': 'Owner Updated Name',
                'body':'Hello {student_name},\n\nWelcome to {school_name}.',
                }
        
        response = self.client.patch(
            self.detail_url(self.template1.pk), 
            data, 
            format='json'
        )
        
        print("#"*100)
        print(response.data)
        print(response)
        print("#"*100)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], 'Owner Updated Name')

    def test_update_template_school_owner_wrong_school(self):
        """✅ School owner cannot update templates in other schools"""
        self.client.force_authenticate(user=self.school_owner1)
        
        data = {'name': 'Should not update'}
        response = self.client.patch(
            self.detail_url(self.template4.pk),  # school2 template
            data, 
            format='json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_update_template_as_instructor_denied(self):
        """✅ Instructor cannot update templates"""
        self.client.force_authenticate(user=self.instructor1)
        
        data = {'name': 'Should not update'}
        response = self.client.patch(
            self.detail_url(self.template1.pk), 
            data, 
            format='json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_update_template_as_student_denied(self):
        """✅ Student cannot update templates"""
        self.client.force_authenticate(user=self.student1)
        
        data = {'name': 'Should not update'}
        response = self.client.patch(
            self.detail_url(self.template1.pk), 
            data, 
            format='json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_update_school_field_denied(self):
        """✅ Cannot change school field of existing template"""
        self.client.force_authenticate(user=self.platform_admin)
        
        data = {'school': self.school2.id}  # Try to change school
        response = self.client.patch(
            self.detail_url(self.template1.pk), 
            data, 
            format='json'
        )
        
        print("#"*100)
        print(response.data)
        print(response)
        print("#"*100)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        # School field should not change
        self.assertNotEqual(response.data['school'], self.school2.id)
        
        # Verify school didn't change in database
        self.template1.refresh_from_db()
        self.assertEqual(self.template1.school.id, self.school1.id)

    def test_update_to_duplicate_name(self):
        """✅ Cannot update template to duplicate name in same school"""
        self.client.force_authenticate(user=self.platform_admin)
        
        # Try to update template2 to have same name as template1
        data = {'name': 'Welcome Email',
                'body':'Hello {student_name},\n\nWelcome to {school_name}.',
             }  # template1's name
        response = self.client.patch(
            self.detail_url(self.template2.pk), 
            data, 
            format='json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('name', response.data)

    # ==================== DELETE TEMPLATE TESTS ====================

    def test_delete_template_as_platform_admin(self):
        """✅ Platform admin can delete any template"""
        initial_count = CommunicationTemplate.objects.count()
        self.client.force_authenticate(user=self.platform_admin)
        
        response = self.client.delete(self.detail_url(self.template1.pk))
        
        print("#"*100)
        print(response.data)
        print(response)
        print("#"*100)

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(CommunicationTemplate.objects.count(), initial_count - 1)
        self.assertFalse(CommunicationTemplate.objects.filter(id=self.template1.id).exists())

    def test_delete_template_as_school_owner(self):
        """✅ School owner can delete templates in their schools"""
        initial_count = CommunicationTemplate.objects.count()
        self.client.force_authenticate(user=self.school_owner1)
        
        response = self.client.delete(self.detail_url(self.template1.pk))
        
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(CommunicationTemplate.objects.count(), initial_count - 1)

    def test_delete_template_school_owner_wrong_school(self):
        """✅ School owner cannot delete templates in other schools"""
        initial_count = CommunicationTemplate.objects.count()
        self.client.force_authenticate(user=self.school_owner1)
        
        response = self.client.delete(self.detail_url(self.template4.pk))  # school2 template
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(CommunicationTemplate.objects.count(), initial_count)

    def test_delete_template_as_instructor_denied(self):
        """✅ Instructor cannot delete templates"""
        initial_count = CommunicationTemplate.objects.count()
        self.client.force_authenticate(user=self.instructor1)
        
        response = self.client.delete(self.detail_url(self.template1.pk))
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(CommunicationTemplate.objects.count(), initial_count)

    def test_delete_template_as_student_denied(self):
        """✅ Student cannot delete templates"""
        initial_count = CommunicationTemplate.objects.count()
        self.client.force_authenticate(user=self.student1)
        
        response = self.client.delete(self.detail_url(self.template1.pk))
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(CommunicationTemplate.objects.count(), initial_count)

    def test_delete_template_with_pending_messages(self):
        """✅ Cannot delete template with pending messages"""
        # Create a pending message for template1
        AutomatedMessage.objects.create(
            student=self.student1_profile,
            template=self.template1,
            scheduled_for=timezone.now() + timedelta(days=1),
            status='pending'
        )
        
        self.client.force_authenticate(user=self.platform_admin)
        response = self.client.delete(self.detail_url(self.template1.pk))
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn('pending', response.data['detail'])

    # ==================== AVAILABLE_VARIABLES ACTION TESTS ====================

    def test_available_variables_success(self):
        """✅ Can view available template variables"""
        self.client.force_authenticate(user=self.school_owner1)
        response = self.client.get(self.available_variables_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('variables', response.data)
        self.assertIn('total_variables', response.data)
        self.assertIn('usage_example', response.data)
        
        variables = response.data['variables']
        self.assertIsInstance(variables, dict)
        self.assertIn('student_name', variables)
        self.assertIn('progress_theory', variables)
        self.assertIn('school_name', variables)

    # ==================== DUPLICATE ACTION TESTS ====================

    def test_duplicate_template_as_platform_admin(self):
        """✅ Platform admin can duplicate any template"""
        self.client.force_authenticate(user=self.platform_admin)
        
        data = {'new_name': 'Copy of Welcome Email'}
        response = self.client.post(self.duplicate_url(self.template1.pk), data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(CommunicationTemplate.objects.count(), 5)  # Started with 4
        self.assertEqual(response.data['new_template']['name'], 'Copy of Welcome Email')
        self.assertFalse(response.data['new_template']['is_active'])  # Should start as inactive

    def test_duplicate_template_as_school_owner(self):
        """✅ School owner can duplicate templates in their schools"""
        self.client.force_authenticate(user=self.school_owner1)
        
        data = {'new_name': 'Duplicated Template'}
        response = self.client.post(self.duplicate_url(self.template1.pk), data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['new_template']['school'], self.school1.id)

    def test_duplicate_template_school_owner_wrong_school(self):
        """✅ School owner cannot duplicate templates from other schools"""
        self.client.force_authenticate(user=self.school_owner1)
        
        data = {'new_name': 'Should not duplicate'}
        response = self.client.post(self.duplicate_url(self.template4.pk), data, format='json')
        
        print("#"*100)
        print(response.data)
        print(response)
        print("#"*100)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_duplicate_template_duplicate_name(self):
        """✅ Cannot duplicate template with existing name"""
        self.client.force_authenticate(user=self.platform_admin)
        
        # Try to duplicate with existing name
        data = {'new_name': 'Welcome Email'}  # Already exists
        response = self.client.post(self.duplicate_url(self.template2.pk), data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)

    def test_duplicate_template_no_new_name(self):
        """✅ Duplicate uses default name if no new_name provided"""
        self.client.force_authenticate(user=self.platform_admin)
        
        response = self.client.post(self.duplicate_url(self.template1.pk), {}, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['new_template']['name'], 'Copy of Welcome Email')

    # ==================== PREVIEW ACTION TESTS ====================

    def test_preview_template_with_student(self):
        """✅ Can preview template with specific student data"""
        self.client.force_authenticate(user=self.school_owner1)
        
        data = {'student_id': self.student1_profile.id}
        response = self.client.post(self.preview_url(self.template1.pk), data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('preview', response.data)
        self.assertIn('subject', response.data['preview'])
        self.assertIn('body', response.data['preview'])
        self.assertIn('data_used', response.data)
        self.assertFalse(response.data['is_sample_data'])
        
        # Check variables are replaced
        preview_subject = response.data['preview']['subject']
        self.assertNotIn('{student_name}', preview_subject)
        self.assertIn(self.student1.username, preview_subject)

    def test_preview_template_with_sample_data(self):
        """✅ Can preview template with sample data"""
        self.client.force_authenticate(user=self.school_owner1)
        
        response = self.client.post(self.preview_url(self.template1.pk), {}, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['is_sample_data'])
        
        # Check sample data was used
        preview_subject = response.data['preview']['subject']
        self.assertNotIn('{student_name}', preview_subject)
        self.assertNotIn('{school_name}', preview_subject)

    def test_preview_template_invalid_variable(self):
        """✅ Preview fails with invalid variable in template"""
        # Create template with invalid variable
        invalid_template = CommunicationTemplate.objects.create(
            school=self.school1,
            name='Invalid Template',
            template_type='lesson_reminder',
            subject='Test {invalid_variable}',
            body='Test body',
            is_active=True
        )
        
        self.client.force_authenticate(user=self.school_owner1)
        response = self.client.post(self.preview_url(invalid_template.pk), {}, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)
        self.assertIn('invalid variable', response.data['error'])

    def test_preview_template_wrong_school_student(self):
        """✅ Cannot preview with student from wrong school"""
        # Create a student in school2
        student_school2 = User.objects.create_user(
            username='student_school2',
            email='student2@school2.com',
            password='testpass123',
            role='S'
        )
        
        student_school2_profile = StudentProfile.objects.create(
            user=student_school2,
            school=self.school2,
            status='A'
        )
        
        self.client.force_authenticate(user=self.school_owner1)
        data = {'student_id': student_school2_profile.id}
        response = self.client.post(self.preview_url(self.template1.pk), data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    # ==================== TOGGLE_ACTIVE ACTION TESTS ====================

    def test_toggle_active_as_platform_admin(self):
        """✅ Platform admin can toggle template active status"""
        self.client.force_authenticate(user=self.platform_admin)
        
        # Initially active
        self.assertTrue(self.template1.is_active)
        
        response = self.client.post(self.toggle_active_url(self.template1.pk))
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['message'], 'Template deactivated successfully')
        self.assertFalse(response.data['template']['is_active'])
        
        # Toggle again
        response = self.client.post(self.toggle_active_url(self.template1.pk))
        self.assertEqual(response.data['message'], 'Template activated successfully')
        self.assertTrue(response.data['template']['is_active'])

    def test_toggle_active_as_school_owner(self):
        """✅ School owner can toggle templates in their schools"""
        self.client.force_authenticate(user=self.school_owner1)
        
        response = self.client.post(self.toggle_active_url(self.template1.pk))
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_toggle_active_school_owner_wrong_school(self):
        """✅ School owner cannot toggle templates in other schools"""
        self.client.force_authenticate(user=self.school_owner1)
        
        response = self.client.post(self.toggle_active_url(self.template4.pk))
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    # ==================== BY_TYPE ACTION TESTS ====================

    def test_by_type_success(self):
        """✅ Can view templates grouped by type"""
        self.client.force_authenticate(user=self.school_owner1)
        response = self.client.get(self.by_type_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('grouped_templates', response.data)
        self.assertIn('total_types', response.data)
        self.assertIn('total_templates', response.data)
        
        grouped = response.data['grouped_templates']
        self.assertIn('lesson_reminder', grouped)
        self.assertIn('progress_update', grouped)
        self.assertIn('birthday', grouped)
        
        # Check lesson_reminder group
        lesson_reminder = grouped['lesson_reminder']
        self.assertEqual(lesson_reminder['type_name'], 'Lesson Reminder')
        self.assertEqual(lesson_reminder['count'], 1)  # Only template1
        
        # Check progress_update group
        progress_update = grouped['progress_update']
        self.assertEqual(progress_update['type_name'], 'Progress Update')
        self.assertEqual(progress_update['count'], 1)  # Only template2

    def test_by_type_with_school_filter_admin_only(self):
        """✅ Only platform admins can filter by_type with school_id"""
        # Platform admin can filter
        self.client.force_authenticate(user=self.platform_admin)
        response = self.client.get(self.by_type_url, {'school_id': self.school1.id})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('grouped_templates', response.data)
        
        # School owner cannot filter by school_id
        self.client.force_authenticate(user=self.school_owner1)
        response = self.client.get(self.by_type_url, {'school_id': self.school2.id})
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    # ==================== USAGE_STATS ACTION TESTS ====================

    def test_usage_stats_success(self):
        """✅ Can view template usage statistics"""
        self.client.force_authenticate(user=self.school_owner1)
        response = self.client.get(self.usage_stats_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('summary', response.data)
        self.assertIn('most_used_templates', response.data)
        self.assertIn('total_messages_created', response.data)
        
        summary = response.data['summary']
        self.assertEqual(summary['total_templates'], 3)  # School1 has 3 templates
        self.assertEqual(summary['active_templates'], 2)  # 2 active, 1 inactive
        self.assertEqual(summary['inactive_templates'], 1)
        
        # Check most used templates
        most_used = response.data['most_used_templates']
        self.assertGreater(len(most_used), 0)
        
        # template1 should be most used (has 2 messages)
        if len(most_used) > 0:
            self.assertEqual(most_used[0]['name'], 'Welcome Email')
            self.assertEqual(most_used[0]['total_messages'], 2)

    def test_usage_stats_with_school_filter_admin_only(self):
        """✅ Only platform admins can filter usage_stats with school_id"""
        # Platform admin can filter
        self.client.force_authenticate(user=self.platform_admin)
        response = self.client.get(self.usage_stats_url, {'school_id': self.school1.id})
        


        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('summary', response.data)
        


    # ==================== MY_SCHOOL_TEMPLATES ACTION TESTS ====================

    def test_my_school_templates_as_school_owner(self):
        """✅ School owner can view their school templates"""
        self.client.force_authenticate(user=self.school_owner1)
        response = self.client.get(self.my_school_templates_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        results = self.get_results(response.data)
        self.assertEqual(len(results), 3)  # All school1 templates
        
        # Verify they're all from school1
        for template in results:
            self.assertEqual(template['school'], self.school1.id)

    def test_my_school_templates_as_instructor(self):
        """✅ Instructor can view their school templates"""
        self.client.force_authenticate(user=self.instructor1)
        response = self.client.get(self.my_school_templates_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        results = self.get_results(response.data)
        self.assertEqual(len(results), 3)  # All school1 templates

    def test_my_school_templates_instructor_no_school(self):
        """✅ Instructor without school gets error"""
        # Remove instructor's profile
        self.instructor1_profile.delete()
        
        self.client.force_authenticate(user=self.instructor1)
        response = self.client.get(self.my_school_templates_url)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)

    def test_my_school_templates_as_platform_admin_denied(self):
        """✅ Platform admin cannot use my_school_templates endpoint"""
        self.client.force_authenticate(user=self.platform_admin)
        response = self.client.get(self.my_school_templates_url)
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_my_school_templates_as_student_denied(self):
        """✅ Student cannot use my_school_templates endpoint"""
        self.client.force_authenticate(user=self.student1)
        response = self.client.get(self.my_school_templates_url)
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_my_school_templates_with_filters(self):
        """✅ Can filter my_school_templates"""
        self.client.force_authenticate(user=self.school_owner1)
        
        # Filter by template_type
        response = self.client.get(self.my_school_templates_url, 
                                 {'template_type': 'lesson_reminder'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        results = self.get_results(response.data)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['template_type'], 'lesson_reminder')
        
        # Filter by active_only
        response = self.client.get(self.my_school_templates_url, 
                                 {'active_only': 'true'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        results = self.get_results(response.data)
        self.assertEqual(len(results), 2)  # 2 active templates
        
        for template in results:
            self.assertTrue(template['is_active'])

    # ==================== MODEL VALIDATION TESTS ====================

    def test_template_string_representation(self):
        """✅ Template string representation is correct"""
        self.assertEqual(str(self.template1), f"{self.template1.school.name} - {self.template1.name}")

    def test_template_variables_property(self):
        """✅ Template variables property works correctly"""
        # Test with template that has variables
        variables = CommunicationTemplateService.get_available_variables()
        self.assertIsInstance(variables, dict)
        self.assertGreater(len(variables), 0)

    # ==================== SERVICE METHOD TESTS ====================

    def test_communication_service_get_is_overdue(self):
        """✅ CommunicationService.get_is_overdue works correctly"""
        # Create overdue message (scheduled for past)
        overdue_msg = AutomatedMessage.objects.create(
            student=self.student1_profile,
            template=self.template1,
            scheduled_for=timezone.now() - timedelta(days=1),
            status='pending'
        )
        
        # Create future message
        future_msg = AutomatedMessage.objects.create(
            student=self.student1_profile,
            template=self.template1,
            scheduled_for=timezone.now() + timedelta(days=1),
            status='pending'
        )
        
        # Test is_overdue
        self.assertTrue(CommunicationService.get_is_overdue(overdue_msg))
        self.assertFalse(CommunicationService.get_is_overdue(future_msg))
        
        # Test non-pending messages
        sent_msg = AutomatedMessage.objects.create(
            student=self.student1_profile,
            template=self.template1,
            scheduled_for=timezone.now() - timedelta(days=1),
            status='sent',
            sent_at=timezone.now()
        )
        self.assertFalse(CommunicationService.get_is_overdue(sent_msg))

    def test_communication_service_get_time_until_send(self):
        """✅ CommunicationService.get_time_until_send works correctly"""
        # Create message for 1 hour from now
        one_hour_later = timezone.now() + timedelta(hours=1)
        msg = AutomatedMessage.objects.create(
            student=self.student1_profile,
            template=self.template1,
            scheduled_for=one_hour_later,
            status='pending'
        )
        
        time_until = CommunicationService.get_time_until_send(msg)
        self.assertIsInstance(time_until, str)
        self.assertIn('In', time_until)
        
        # Test overdue message
        overdue_msg = AutomatedMessage.objects.create(
            student=self.student1_profile,
            template=self.template1,
            scheduled_for=timezone.now() - timedelta(days=1),
            status='pending'
        )
        
        overdue_time = CommunicationService.get_time_until_send(overdue_msg)
        self.assertIn('Overdue', overdue_time)
        
        # Test non-pending message
        sent_msg = AutomatedMessage.objects.create(
            student=self.student1_profile,
            template=self.template1,
            scheduled_for=timezone.now() + timedelta(days=1),
            status='sent'
        )
        
        sent_time = CommunicationService.get_time_until_send(sent_msg)
        self.assertIsNone(sent_time)



if __name__ == '__main__':
    # Run specific test class
    import unittest
    unittest.main()
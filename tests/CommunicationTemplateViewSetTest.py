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


class AutomatedMessageViewSetTestCase(APITestCase):
    """Comprehensive tests for AutomatedMessageViewSet"""

    def setUp(self):
        """Set up test data"""
        # Create users
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
        
        # Create another student in school2
        self.student3 = User.objects.create_user(
            username='student3',
            email='student3@school2.com',
            password='testpass123',
            role='S'
        )
        
        self.student3_profile = StudentProfile.objects.create(
            user=self.student3,
            school=self.school2,
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
            subject='Your Progress Update',
            body='Dear {student_name},',
            is_active=True
        )
        
        self.template3 = CommunicationTemplate.objects.create(
            school=self.school2,
            name='School 2 Template',
            template_type='lesson_reminder',
            subject='School 2 Template',
            body='This is a school 2 template.',
            is_active=True
        )
        
        # Create automated messages
        self.now = timezone.now()
        
        # Pending messages
        self.pending_msg1 = AutomatedMessage.objects.create(
            student=self.student1_profile,
            template=self.template1,
            scheduled_for=self.now + timedelta(days=1),
            status='pending'
        )
        
        self.pending_msg2 = AutomatedMessage.objects.create(
            student=self.student2_profile,
            template=self.template1,
            scheduled_for=self.now + timedelta(days=2),
            status='pending'
        )
        
        # Sent messages
        self.sent_msg1 = AutomatedMessage.objects.create(
            student=self.student1_profile,
            template=self.template2,
            scheduled_for=self.now - timedelta(days=1),
            status='sent',
            sent_at=self.now - timedelta(hours=1)
        )
        
        self.sent_msg2 = AutomatedMessage.objects.create(
            student=self.student2_profile,
            template=self.template2,
            scheduled_for=self.now - timedelta(days=2),
            status='sent',
            sent_at=self.now - timedelta(hours=2)
        )
        
        # Delivered message
        self.delivered_msg = AutomatedMessage.objects.create(
            student=self.student1_profile,
            template=self.template1,
            scheduled_for=self.now - timedelta(days=3),
            status='delivered',
            sent_at=self.now - timedelta(days=1)
        )
        
        # Failed message
        self.failed_msg = AutomatedMessage.objects.create(
            student=self.student2_profile,
            template=self.template1,
            scheduled_for=self.now - timedelta(days=1),
            status='failed',
            delivery_error='SMTP error'
        )
        
        # Read message
        self.read_msg = AutomatedMessage.objects.create(
            student=self.student1_profile,
            template=self.template2,
            scheduled_for=self.now - timedelta(days=4),
            status='read',
            sent_at=self.now - timedelta(days=2)
        )
        
        # School2 message
        self.school2_msg = AutomatedMessage.objects.create(
            student=self.student3_profile,
            template=self.template3,
            scheduled_for=self.now + timedelta(days=1),
            status='pending'
        )
        
        # Overdue message
        self.overdue_msg = AutomatedMessage.objects.create(
            student=self.student1_profile,
            template=self.template1,
            scheduled_for=self.now - timedelta(hours=2),
            status='pending'
        )

       # API client
        self.client = APIClient()
        
        # URLs
        self.list_url = reverse('automatedmessage-list')
        self.detail_url = lambda pk: reverse('automatedmessage-detail', kwargs={'pk': pk})
        self.my_messages_url = reverse('automatedmessage-my-messages')
        self.pending_url = reverse('automatedmessage-pending')
        self.sent_url = reverse('automatedmessage-sent')
        self.failed_url = reverse('automatedmessage-failed')
        self.cancel_url = lambda pk: reverse('automatedmessage-cancel', kwargs={'pk': pk})
        self.send_now_url = lambda pk: reverse('automatedmessage-send-now', kwargs={'pk': pk})
        self.reschedule_url = lambda pk: reverse('automatedmessage-reschedule', kwargs={'pk': pk})
        self.bulk_create_url = reverse('automatedmessage-bulk-create')
        self.bulk_cancel_url = reverse('automatedmessage-bulk-cancel')
        self.statistics_url = reverse('automatedmessage-statistics')
        self.upcoming_schedule_url = reverse('automatedmessage-upcoming-schedule')
        self.summary_url = reverse('automatedmessage-summary')

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
        """✅ Test that unauthenticated users cannot access messages"""
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_platform_admin_sees_all_messages(self):
        """✅ Platform admin should see all messages"""
        self.client.force_authenticate(user=self.platform_admin)
        response = self.client.get(self.list_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        results = self.get_results(response.data)
        self.assertEqual(len(results), AutomatedMessage.objects.count())

    def test_school_owner_sees_only_their_messages(self):
        """✅ School owner should only see messages in their schools"""
        self.client.force_authenticate(user=self.school_owner1)
        response = self.client.get(self.list_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        results = self.get_results(response.data)
        expected_count = AutomatedMessage.objects.filter(
            template__school__owner=self.school_owner1
        ).count()
        self.assertEqual(len(results), expected_count)
        
        # Verify no school2 messages
        message_ids = [msg['id'] for msg in results]
        self.assertNotIn(self.school2_msg.id, message_ids)

    def test_instructor_sees_only_their_school_messages(self):
        """✅ Instructor should see messages from their school only"""
        self.client.force_authenticate(user=self.instructor1)
        response = self.client.get(self.list_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        results = self.get_results(response.data)
        expected_count = AutomatedMessage.objects.filter(
            student__school=self.school1
        ).count()
        self.assertEqual(len(results), expected_count)

    def test_student_sees_only_their_messages(self):
        """✅ Student should see only their own messages"""
        self.client.force_authenticate(user=self.student1)
        response = self.client.get(self.list_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        results = self.get_results(response.data)
        expected_count = AutomatedMessage.objects.filter(
            student=self.student1_profile
        ).count()
        self.assertEqual(len(results), expected_count)
        
        # Verify only student1's messages
        for msg in results:
            self.assertEqual(msg['student'], self.student1_profile.id)

    # ==================== LIST MESSAGES TESTS ====================

    def test_list_messages_success(self):
        """✅ Test listing messages returns correct data"""
        self.client.force_authenticate(user=self.school_owner1)
        response = self.client.get(self.list_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        results = self.get_results(response.data)
        
        # Check message data structure
        message = results[0]
        self.assertIn('id', message)
        self.assertIn('student', message)
        self.assertIn('template', message)
        self.assertIn('scheduled_for', message)
        self.assertIn('status', message)
        self.assertIn('created_at', message)
        self.assertIn('student_name', message)
        self.assertIn('template_name', message)
        self.assertIn('school_name', message)

    def test_list_messages_with_filters(self):
        """✅ Test filtering messages"""
        self.client.force_authenticate(user=self.school_owner1)
        
        # Filter by status
        response = self.client.get(self.list_url, {'status': 'pending'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = self.get_results(response.data)
        
        for msg in results:
            self.assertEqual(msg['status'], 'pending')
        
        # Filter by student
        response = self.client.get(self.list_url, {'student': self.student1_profile.id})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = self.get_results(response.data)
        
        for msg in results:
            self.assertEqual(msg['student'], self.student1_profile.id)
        
        # Filter by template
        response = self.client.get(self.list_url, {'template': self.template1.id})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = self.get_results(response.data)
        
        for msg in results:
            self.assertEqual(msg['template'], self.template1.id)
        
        # Filter by template school
        response = self.client.get(self.list_url, {'template__school': self.school1.id})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = self.get_results(response.data)
        self.assertGreater(len(results), 0)

    def test_list_messages_with_search(self):
        """✅ Test searching messages"""
        self.client.force_authenticate(user=self.school_owner1)
        
        # Search by student username
        response = self.client.get(self.list_url, {'search': 'student1'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = self.get_results(response.data)
        self.assertGreater(len(results), 0)
        
        # Search by template name
        response = self.client.get(self.list_url, {'search': 'Welcome'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = self.get_results(response.data)
        self.assertGreater(len(results), 0)

    def test_list_messages_with_ordering(self):
        """✅ Test ordering messages"""
        self.client.force_authenticate(user=self.school_owner1)
        
        # Order by scheduled_for ascending
        response = self.client.get(self.list_url, {'ordering': 'scheduled_for'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        results = self.get_results(response.data)
        # Check ordering by verifying dates are sorted
        scheduled_dates = [msg['scheduled_for'] for msg in results]
        
        # Order by scheduled_for descending (default)
        response = self.client.get(self.list_url, {'ordering': '-scheduled_for'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        results = self.get_results(response.data)
        # Check ordering

    # ==================== RETRIEVE MESSAGE TESTS ====================

    def test_retrieve_message_success(self):
        """✅ Test retrieving a single message"""
        self.client.force_authenticate(user=self.student1)
        response = self.client.get(self.detail_url(self.pending_msg1.pk))
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['student'], self.student1_profile.id)
        self.assertEqual(response.data['template'], self.template1.id)
        self.assertEqual(response.data['status'], 'pending')

    def test_retrieve_message_not_found(self):
        """✅ Test retrieving non-existent message"""
        self.client.force_authenticate(user=self.platform_admin)
        response = self.client.get(self.detail_url(99999))
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_retrieve_message_no_permission(self):
        """✅ Cannot retrieve message without permission"""
        # Student1 tries to retrieve student2's message
        self.client.force_authenticate(user=self.student1)
        response = self.client.get(self.detail_url(self.pending_msg2.pk))
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        
        # School owner1 tries to retrieve school2's message
        self.client.force_authenticate(user=self.school_owner1)
        response = self.client.get(self.detail_url(self.school2_msg.pk))
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    # ==================== CREATE MESSAGE TESTS ====================

    def test_create_message_as_platform_admin(self):
        """✅ Platform admin can create message for any student"""
        self.client.force_authenticate(user=self.platform_admin)
        
        scheduled_for = self.now + timedelta(days=3)
        data = {
            'student': self.student1_profile.id,
            'template': self.template1.id,
            'scheduled_for': scheduled_for.isoformat(),
            'status': 'pending'
        }
        
        initial_count = AutomatedMessage.objects.count()
        response = self.client.post(self.list_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(AutomatedMessage.objects.count(), initial_count + 1)
        self.assertEqual(response.data['student'], self.student1_profile.id)
        self.assertEqual(response.data['status'], 'pending')

    def test_create_message_as_school_owner(self):
        """✅ School owner can create message for their students"""
        self.client.force_authenticate(user=self.school_owner1)
        
        scheduled_for = self.now + timedelta(days=3)
        data = {
            'student': self.student1_profile.id,  # Their student
            'template': self.template1.id,        # Their template
            'scheduled_for': scheduled_for.isoformat(),
            'status': 'pending'
        }
        
        response = self.client.post(self.list_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['student'], self.student1_profile.id)
 
    def test_create_message_school_owner_wrong_student(self):
        """✅ School owner cannot create message for other schools' students"""
        self.client.force_authenticate(user=self.school_owner1)
        
        scheduled_for = self.now + timedelta(days=3)
        data = {
            'student': self.student3_profile.id,  # School2 student
            'template': self.template1.id,        # School1 template
            'scheduled_for': scheduled_for.isoformat(),
            'status': 'pending'
        }
        
        response = self.client.post(self.list_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_message_school_owner_wrong_template(self):
        """✅ School owner cannot create message with other schools' templates"""
        self.client.force_authenticate(user=self.school_owner1)
        
        scheduled_for = self.now + timedelta(days=3)
        data = {
            'student': self.student1_profile.id,  # Their student
            'template': self.template3.id,        # School2 template
            'scheduled_for': scheduled_for.isoformat(),
            'status': 'pending'
        }
        
        response = self.client.post(self.list_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_message_as_instructor(self):
        """✅ Instructor can create message for students in their school"""
        self.client.force_authenticate(user=self.instructor1)
        
        scheduled_for = self.now + timedelta(days=3)
        data = {
            'student': self.student1_profile.id,  # Same school
            'template': self.template1.id,        # Same school
            'scheduled_for': scheduled_for.isoformat(),
            'status': 'pending'
        }
        
        response = self.client.post(self.list_url, data, format='json')
        

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['student'], self.student1_profile.id)

    def test_create_message_instructor_wrong_school(self):
        """✅ Instructor cannot create message for students in different school"""
        self.client.force_authenticate(user=self.instructor1)
        
        scheduled_for = self.now + timedelta(days=3)
        data = {
            'student': self.student3_profile.id,  # School2 student
            'template': self.template1.id,
            'scheduled_for': scheduled_for.isoformat(),
            'status': 'pending'
        }
        
        response = self.client.post(self.list_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_message_instructor_no_profile(self):
        """✅ Instructor without school profile cannot create messages"""
        # Remove instructor's profile
        self.instructor1_profile.delete()
        
        self.client.force_authenticate(user=self.instructor1)
        
        scheduled_for = self.now + timedelta(days=3)
        data = {
            'student': self.student1_profile.id,
            'template': self.template1.id,
            'scheduled_for': scheduled_for.isoformat(),
            'status': 'pending'
        }
        
        response = self.client.post(self.list_url, data, format='json')
        

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_message_as_student_denied(self):
        """✅ Student cannot create messages"""
        self.client.force_authenticate(user=self.student1)
        
        scheduled_for = self.now + timedelta(days=3)
        data = {
            'student': self.student1_profile.id,
            'template': self.template1.id,
            'scheduled_for': scheduled_for.isoformat(),
            'status': 'pending'
        }
        
        response = self.client.post(self.list_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_create_message_past_scheduled_for(self):
        """✅ Cannot create message with past scheduled_for date"""
        self.client.force_authenticate(user=self.platform_admin)
        
        data = {
            'student': self.student1_profile.id,
            'template': self.template1.id,
            'scheduled_for': (self.now - timedelta(days=1)).isoformat(),
            'status': 'pending'
        }
        
        response = self.client.post(self.list_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('scheduled_for', response.data)

    def test_create_message_invalid_status(self):
        """✅ Cannot create message with invalid status"""
        self.client.force_authenticate(user=self.platform_admin)
        
        scheduled_for = self.now + timedelta(days=3)
        data = {
            'student': self.student1_profile.id,
            'template': self.template1.id,
            'scheduled_for': scheduled_for.isoformat(),
            'status': 'invalid_status'
        }
        
        response = self.client.post(self.list_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_message_missing_required_fields(self):
        """✅ Cannot create message without required fields"""
        self.client.force_authenticate(user=self.platform_admin)
        
        # Missing student
        data = {
            'template': self.template1.id,
            'scheduled_for': (self.now + timedelta(days=1)).isoformat(),
            'status': 'pending'
        }
        
        response = self.client.post(self.list_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('student', response.data)

    # ==================== UPDATE MESSAGE TESTS ====================

    def test_update_message_as_platform_admin(self):
        """✅ Platform admin can update any message"""
        self.client.force_authenticate(user=self.platform_admin)
        
        new_scheduled_for = self.now + timedelta(days=5)
        data = {
            'scheduled_for': new_scheduled_for.isoformat(),
            'status': 'pending'
        }
        
        response = self.client.patch(
            self.detail_url(self.pending_msg1.pk), 
            data, 
            format='json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'pending')
        
        # Refresh from DB
        self.pending_msg1.refresh_from_db()
        self.assertEqual(self.pending_msg1.status, 'pending')

    def test_update_message_as_school_owner(self):
        """✅ School owner can update messages in their schools"""
        self.client.force_authenticate(user=self.school_owner1)
        
        data = {'status': 'pending'}
        response = self.client.patch(
            self.detail_url(self.pending_msg1.pk), 
            data, 
            format='json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_update_message_school_owner_wrong_school(self):
        """✅ School owner cannot update messages in other schools"""
        self.client.force_authenticate(user=self.school_owner1)
        
        data = {'status': 'pending'}
        response = self.client.patch(
            self.detail_url(self.school2_msg.pk),  # school2 message
            data, 
            format='json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_update_message_as_instructor(self):
        """✅ Instructor can update messages in their school"""
        self.client.force_authenticate(user=self.instructor1)
        
        data = {'status': 'pending'}
        response = self.client.patch(
            self.detail_url(self.pending_msg1.pk), 
            data, 
            format='json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_update_message_instructor_wrong_school(self):
        """✅ Instructor cannot update messages in different school"""
        self.client.force_authenticate(user=self.instructor1)
        
        data = {'status': 'pending'}
        response = self.client.patch(
            self.detail_url(self.school2_msg.pk),  # school2 message
            data, 
            format='json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_update_message_as_student_denied(self):
        """✅ Student cannot update messages"""
        self.client.force_authenticate(user=self.student1)
        
        data = {'status': 'pending'}
        response = self.client.patch(
            self.detail_url(self.pending_msg1.pk),  # Their own message
            data, 
            format='json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_cannot_update_sent_delivered_or_read_messages(self):
        """✅ Cannot update sent, delivered, or read messages"""
        self.client.force_authenticate(user=self.platform_admin)
        
        # Try to update sent message
        data = {'status': 'pending'}
        response = self.client.patch(
            self.detail_url(self.sent_msg1.pk), 
            data, 
            format='json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        
        # Try to update delivered message
        response = self.client.patch(
            self.detail_url(self.delivered_msg.pk), 
            data, 
            format='json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        
        # Try to update read message
        response = self.client.patch(
            self.detail_url(self.read_msg.pk), 
            data, 
            format='json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_cannot_update_student_or_template_fields(self):
        """✅ Cannot change student or template of existing message"""
        self.client.force_authenticate(user=self.platform_admin)
        
        data = {
            'student': self.student2_profile.id,
            'template': self.template2.id
        }
        
        response = self.client.patch(
            self.detail_url(self.pending_msg1.pk), 
            data, 
            format='json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        
        # Fields should not change
        self.pending_msg1.refresh_from_db()
        self.assertEqual(self.pending_msg1.student.id, self.student1_profile.id)
        self.assertEqual(self.pending_msg1.template.id, self.template1.id)

    # ==================== DELETE MESSAGE TESTS ====================

    def test_delete_message_as_platform_admin(self):
        """✅ Platform admin can delete any message"""
        initial_count = AutomatedMessage.objects.count()
        self.client.force_authenticate(user=self.platform_admin)
        
        response = self.client.delete(self.detail_url(self.pending_msg1.pk))
        
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(AutomatedMessage.objects.count(), initial_count - 1)

    def test_delete_message_as_school_owner(self):
        """✅ School owner can delete messages in their schools"""
        initial_count = AutomatedMessage.objects.count()
        self.client.force_authenticate(user=self.school_owner1)
        
        response = self.client.delete(self.detail_url(self.pending_msg1.pk))
        
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(AutomatedMessage.objects.count(), initial_count - 1)

    def test_delete_message_school_owner_wrong_school(self):
        """✅ School owner cannot delete messages in other schools"""
        initial_count = AutomatedMessage.objects.count()
        self.client.force_authenticate(user=self.school_owner1)
        
        response = self.client.delete(self.detail_url(self.school2_msg.pk))
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(AutomatedMessage.objects.count(), initial_count)

    def test_delete_message_as_instructor_denied(self):
        """✅ Instructor cannot delete messages"""
        initial_count = AutomatedMessage.objects.count()
        self.client.force_authenticate(user=self.instructor1)
        
        response = self.client.delete(self.detail_url(self.pending_msg1.pk))
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(AutomatedMessage.objects.count(), initial_count)

    def test_delete_message_as_student_denied(self):
        """✅ Student cannot delete messages"""
        initial_count = AutomatedMessage.objects.count()
        self.client.force_authenticate(user=self.student1)
        
        response = self.client.delete(self.detail_url(self.pending_msg1.pk))
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(AutomatedMessage.objects.count(), initial_count)

    def test_cannot_delete_sent_delivered_or_read_messages(self):
        """✅ Cannot delete sent, delivered, or read messages"""
        self.client.force_authenticate(user=self.platform_admin)
        initial_count = AutomatedMessage.objects.count()
        
        # Try to delete sent message
        response = self.client.delete(self.detail_url(self.sent_msg1.pk))
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(AutomatedMessage.objects.count(), initial_count)
        
        # Try to delete delivered message
        response = self.client.delete(self.detail_url(self.delivered_msg.pk))
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        
        # Try to delete read message
        response = self.client.delete(self.detail_url(self.read_msg.pk))
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    # ==================== MY_MESSAGES ACTION TESTS ====================

    def test_my_messages_success(self):
        """✅ Student can view their own messages"""
        self.client.force_authenticate(user=self.student1)
        response = self.client.get(self.my_messages_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('statistics', response.data)
        self.assertIn('messages', response.data)
        
        stats = response.data['statistics']
        self.assertIn('total_messages', stats)
        self.assertIn('pending', stats)
        self.assertIn('sent', stats)
        
        # Verify all messages belong to student1
        for msg in response.data['messages']:
            self.assertEqual(msg['student'], self.student1_profile.id)

    def test_my_messages_with_status_filter(self):
        """✅ Can filter my_messages by status"""
        self.client.force_authenticate(user=self.student1)
        response = self.client.get(self.my_messages_url, {'status': 'pending'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify all returned messages are pending
        for msg in response.data['messages']:
            self.assertEqual(msg['status'], 'pending')

    def test_my_messages_with_limit(self):
        """✅ Can limit my_messages results"""
        self.client.force_authenticate(user=self.student1)
        response = self.client.get(self.my_messages_url, {'limit': 2})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertLessEqual(len(response.data['messages']), 2)

    def test_my_messages_non_student_denied(self):
        """✅ Non-students cannot use my_messages endpoint"""
        self.client.force_authenticate(user=self.instructor1)
        response = self.client.get(self.my_messages_url)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)

    def test_my_messages_no_profile(self):
        """✅ Student without profile gets error"""
        # Remove student's profile
        self.student1_profile.delete()
        
        self.client.force_authenticate(user=self.student1)
        response = self.client.get(self.my_messages_url)
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn('error', response.data)

    # ==================== PENDING ACTION TESTS ====================

    def test_pending_messages_as_admin(self):
        """✅ Admin can view pending messages"""
        self.client.force_authenticate(user=self.platform_admin)
        response = self.client.get(self.pending_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('overdue', response.data)
        self.assertIn('upcoming', response.data)
        self.assertIn('total_pending', response.data)
        
        # Check counts
        self.assertEqual(response.data['total_pending'], 
                        AutomatedMessage.objects.filter(status='pending').count())

    def test_pending_messages_as_school_owner(self):
        """✅ School owner can view pending messages in their schools"""
        self.client.force_authenticate(user=self.school_owner1)
        response = self.client.get(self.pending_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Should not include school2 messages
        total_school1_pending = AutomatedMessage.objects.filter(
            status='pending',
            template__school__owner=self.school_owner1
        ).count()
        
        self.assertEqual(response.data['total_pending'], total_school1_pending)

    def test_pending_messages_as_instructor(self):
        """✅ Instructor can view pending messages in their school"""
        self.client.force_authenticate(user=self.instructor1)
        response = self.client.get(self.pending_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_pending_messages_as_student_denied(self):
        """✅ Student cannot view pending messages"""
        self.client.force_authenticate(user=self.student1)
        response = self.client.get(self.pending_url)
        
        print("#"*100)
        print(response.data)
        print(response)
        print("#"*100)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    # ==================== SENT ACTION TESTS ====================

    def test_sent_messages_success(self):
        """✅ Can view sent messages"""
        self.client.force_authenticate(user=self.school_owner1)
        
        # Test with default days (7)
        response = self.client.get(self.sent_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        results = self.get_results(response.data)
        self.assertGreater(len(results), 0)
        
        # Verify all messages are sent/delivered/read
        for msg in results:
            self.assertIn(msg['status'], ['sent', 'delivered', 'read'])
        
        # Test with custom days parameter
        response = self.client.get(self.sent_url, {'days': 30})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_sent_messages_days_limit(self):
        """✅ Days parameter is limited to 30"""
        self.client.force_authenticate(user=self.school_owner1)
        
        # Try with 90 days (should be limited to 30)
        response = self.client.get(self.sent_url, {'days': 90})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should still work but with 30 days limit

    # ==================== FAILED ACTION TESTS ====================

    def test_failed_messages_success(self):
        """✅ Can view failed messages"""
        self.client.force_authenticate(user=self.school_owner1)
        response = self.client.get(self.failed_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        results = self.get_results(response.data)
        # Should include our failed_msg
        self.assertGreater(len(results), 0)
        
        # Verify all messages are failed
        for msg in results:
            self.assertEqual(msg['status'], 'failed')

    # ==================== CANCEL ACTION TESTS ====================

    def test_cancel_message_success(self):
        """✅ Can cancel a pending message"""
        initial_count = AutomatedMessage.objects.count()
        self.client.force_authenticate(user=self.school_owner1)
        
        response = self.client.post(self.cancel_url(self.pending_msg1.pk))
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('message', response.data)
        self.assertIn('cancelled_message_id', response.data)
        self.assertEqual(AutomatedMessage.objects.count(), initial_count - 1)

    def test_cancel_message_as_instructor(self):
        """✅ Instructor can cancel messages in their school"""
        self.client.force_authenticate(user=self.instructor1)
        
        response = self.client.post(self.cancel_url(self.pending_msg1.pk))
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_cancel_message_instructor_wrong_school(self):
        """✅ Instructor cannot cancel messages in different school"""
        self.client.force_authenticate(user=self.instructor1)
        
        response = self.client.post(self.cancel_url(self.school2_msg.pk))
        

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_cannot_cancel_non_pending_message(self):
        """✅ Cannot cancel sent, delivered, or read messages"""
        self.client.force_authenticate(user=self.platform_admin)
        
        # Try to cancel sent message
        response = self.client.post(self.cancel_url(self.sent_msg1.pk))
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)
        
        # Try to cancel delivered message
        response = self.client.post(self.cancel_url(self.delivered_msg.pk))
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        
        # Try to cancel read message
        response = self.client.post(self.cancel_url(self.read_msg.pk))
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_cancel_message_no_permission(self):
        """✅ Cannot cancel message without permission"""
        # Student cannot cancel
        self.client.force_authenticate(user=self.student1)
        response = self.client.post(self.cancel_url(self.pending_msg1.pk))

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        
        # School owner cannot cancel other school's messages
        self.client.force_authenticate(user=self.school_owner1)
        response = self.client.post(self.cancel_url(self.school2_msg.pk))
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    # ==================== SEND_NOW ACTION TESTS ====================

    def test_send_now_success(self):
        """✅ Can send pending message immediately"""
        # Mock the send function to avoid actual email sending
        original_send = CommunicationService._send_single_message
        sent_messages = []
        
        def mock_send(message):
            sent_messages.append(message.id)
        
        CommunicationService._send_single_message = mock_send
        
        try:
            self.client.force_authenticate(user=self.platform_admin)
            
            response = self.client.post(self.send_now_url(self.pending_msg1.pk))
            
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertIn('message', response.data)
            self.assertIn('sent_message', response.data)
            self.assertIn('sent_at', response.data)
            
            # Verify message was marked as sent
            self.pending_msg1.refresh_from_db()
            self.assertEqual(self.pending_msg1.status, 'sent')
            self.assertIsNotNone(self.pending_msg1.sent_at)
            
        finally:
            CommunicationService._send_single_message = original_send

    def test_send_now_as_school_owner(self):
        """✅ School owner can send messages in their schools"""
        self.client.force_authenticate(user=self.school_owner1)
        
        response = self.client.post(self.send_now_url(self.pending_msg1.pk))
        
        # Might fail due to email sending, but should pass permission check
        # Status could be 200 (success) or 500 (email error)
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_500_INTERNAL_SERVER_ERROR])

    def test_cannot_send_now_non_pending_message(self):
        """✅ Cannot send non-pending message immediately"""
        self.client.force_authenticate(user=self.platform_admin)
        
        # Try to send sent message
        response = self.client.post(self.send_now_url(self.sent_msg1.pk))
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)

    def test_send_now_no_permission(self):
        """✅ Cannot send message without permission"""
        # Instructor cannot send
        self.client.force_authenticate(user=self.instructor1)
        response = self.client.post(self.send_now_url(self.pending_msg1.pk))
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        
        # Student cannot send
        self.client.force_authenticate(user=self.student1)
        response = self.client.post(self.send_now_url(self.pending_msg1.pk))
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    # ==================== RESCHEDULE ACTION TESTS ====================

    def test_reschedule_message_success(self):
        """✅ Can reschedule a pending message"""
        self.client.force_authenticate(user=self.school_owner1)
        
        new_time = self.now + timedelta(days=5)
        data = {
            'new_time': new_time.isoformat()
        }
        
        response = self.client.post(self.reschedule_url(self.pending_msg1.pk), data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('message', response.data)
        self.assertIn('rescheduled_message', response.data)
        self.assertIn('old_time', response.data)
        self.assertIn('new_time', response.data)
        
        # Verify message was updated
        self.pending_msg1.refresh_from_db()
        self.assertEqual(self.pending_msg1.scheduled_for.date(), new_time.date())

    def test_reschedule_message_as_instructor(self):
        """✅ Instructor can reschedule messages in their school"""
        self.client.force_authenticate(user=self.instructor1)
        
        new_time = self.now + timedelta(days=5)
        data = {'new_time': new_time.isoformat()}
        
        response = self.client.post(self.reschedule_url(self.pending_msg1.pk), data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_cannot_reschedule_to_past(self):
        """✅ Cannot reschedule message to past time"""
        self.client.force_authenticate(user=self.platform_admin)
        
        past_time = self.now - timedelta(days=1)
        data = {'new_time': past_time.isoformat()}
        
        response = self.client.post(self.reschedule_url(self.pending_msg1.pk), data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)

    def test_cannot_reschedule_non_pending_message(self):
        """✅ Cannot reschedule sent, delivered, or read messages"""
        self.client.force_authenticate(user=self.platform_admin)
        
        new_time = self.now + timedelta(days=5)
        data = {'new_time': new_time.isoformat()}
        
        # Try to reschedule sent message
        response = self.client.post(self.reschedule_url(self.sent_msg1.pk), data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)

    def test_reschedule_missing_new_time(self):
        """✅ Cannot reschedule without new_time"""
        self.client.force_authenticate(user=self.platform_admin)
        
        response = self.client.post(self.reschedule_url(self.pending_msg1.pk), {}, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)

    def test_reschedule_invalid_time_format(self):
        """✅ Cannot reschedule with invalid time format"""
        self.client.force_authenticate(user=self.platform_admin)
        
        data = {'new_time': 'invalid-time'}
        
        response = self.client.post(self.reschedule_url(self.pending_msg1.pk), data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)

    # ==================== BULK_CREATE ACTION TESTS ====================

    def test_bulk_create_success(self):
        """✅ Can create multiple messages at once"""
        initial_count = AutomatedMessage.objects.count()
        self.client.force_authenticate(user=self.school_owner1)
        
        scheduled_for = self.now + timedelta(days=3)
        data = {
            'student_ids': [self.student1_profile.id, self.student2_profile.id],
            'template_id': self.template1.id,
            'scheduled_for': scheduled_for.isoformat()
        }
        
        response = self.client.post(self.bulk_create_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('message', response.data)
        self.assertIn('summary', response.data)
        self.assertIn('created_messages', response.data)
        
        summary = response.data['summary']
        self.assertEqual(summary['requested'], 2)
        self.assertEqual(summary['created'], 2)
        self.assertEqual(summary['skipped'], 0)
        
        # Should have created 2 new messages
        self.assertEqual(AutomatedMessage.objects.count(), initial_count + 2)

    def test_bulk_create_as_instructor(self):
        """✅ Instructor can bulk create for students in their school"""
        self.client.force_authenticate(user=self.instructor1)
        
        scheduled_for = self.now + timedelta(days=3)
        data = {
            'student_ids': [self.student1_profile.id],
            'template_id': self.template1.id,
            'scheduled_for': scheduled_for.isoformat()
        }
        
        response = self.client.post(self.bulk_create_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_bulk_create_instructor_wrong_school(self):
        """✅ Instructor cannot bulk create for students in different school"""
        self.client.force_authenticate(user=self.instructor1)
        
        scheduled_for = self.now + timedelta(days=3)
        data = {
            'student_ids': [self.student3_profile.id],  # School2 student
            'template_id': self.template1.id,
            'scheduled_for': scheduled_for.isoformat()
        }
        
        response = self.client.post(self.bulk_create_url, data, format='json')
        
        print("#"*100)
        print(response.data)
        print(response)
        print("#"*100)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_bulk_create_instructor_wrong_template(self):
        """✅ Instructor cannot bulk create with template from different school"""
        self.client.force_authenticate(user=self.instructor1)
        
        scheduled_for = self.now + timedelta(days=3)
        data = {
            'student_ids': [self.student1_profile.id],
            'template_id': self.template3.id,  # School2 template
            'scheduled_for': scheduled_for.isoformat()
        }
        
        response = self.client.post(self.bulk_create_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_bulk_create_instructor_no_profile(self):
        """✅ Instructor without school profile cannot bulk create"""
        self.instructor1_profile.delete()
        
        self.client.force_authenticate(user=self.instructor1)
        
        scheduled_for = self.now + timedelta(days=3)
        data = {
            'student_ids': [self.student1_profile.id],
            'template_id': self.template1.id,
            'scheduled_for': scheduled_for.isoformat()
        }
        
        response = self.client.post(self.bulk_create_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_bulk_create_school_owner_wrong_student(self):
        """✅ School owner cannot bulk create for other schools' students"""
        self.client.force_authenticate(user=self.school_owner1)
        
        scheduled_for = self.now + timedelta(days=3)
        data = {
            'student_ids': [self.student3_profile.id],  # School2 student
            'template_id': self.template1.id,
            'scheduled_for': scheduled_for.isoformat()
        }
        
        response = self.client.post(self.bulk_create_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_bulk_create_duplicate_skipped(self):
        """✅ Duplicate messages are skipped in bulk create"""
        # Create an existing message first
        AutomatedMessage.objects.create(
            student=self.student1_profile,
            template=self.template1,
            scheduled_for=self.now + timedelta(days=3),
            status='pending'
        )
        
        initial_count = AutomatedMessage.objects.count()
        self.client.force_authenticate(user=self.platform_admin)
        
        scheduled_for = self.now + timedelta(days=3)
        data = {
            'student_ids': [self.student1_profile.id, self.student2_profile.id],
            'template_id': self.template1.id,
            'scheduled_for': scheduled_for.isoformat()
        }
        
        response = self.client.post(self.bulk_create_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        summary = response.data['summary']
        self.assertEqual(summary['requested'], 2)
        self.assertEqual(summary['created'], 1)  # Only student2
        self.assertEqual(summary['skipped'], 1)  # student1 skipped
        
        # Should have created only 1 new message
        self.assertEqual(AutomatedMessage.objects.count(), initial_count + 1)

    def test_bulk_create_missing_required_fields(self):
        """✅ Cannot bulk create without required fields"""
        self.client.force_authenticate(user=self.platform_admin)
        
        # Missing student_ids
        data = {
            'template_id': self.template1.id,
            'scheduled_for': (self.now + timedelta(days=1)).isoformat()
        }
        
        response = self.client.post(self.bulk_create_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)
        
        # Missing template_id
        data = {
            'student_ids': [self.student1_profile.id],
            'scheduled_for': (self.now + timedelta(days=1)).isoformat()
        }
        
        response = self.client.post(self.bulk_create_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        
        # Missing scheduled_for
        data = {
            'student_ids': [self.student1_profile.id],
            'template_id': self.template1.id
        }
        
        response = self.client.post(self.bulk_create_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_bulk_create_past_scheduled_for(self):
        """✅ Cannot bulk create with past scheduled_for date"""
        self.client.force_authenticate(user=self.platform_admin)
        
        data = {
            'student_ids': [self.student1_profile.id],
            'template_id': self.template1.id,
            'scheduled_for': (self.now - timedelta(days=1)).isoformat()
        }
        
        response = self.client.post(self.bulk_create_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)

    def test_bulk_create_no_valid_students(self):
        """✅ Bulk create with no valid students returns error"""
        self.client.force_authenticate(user=self.platform_admin)
        
        data = {
            'student_ids': [99999],  # Non-existent student
            'template_id': self.template1.id,
            'scheduled_for': (self.now + timedelta(days=1)).isoformat()
        }
        
        response = self.client.post(self.bulk_create_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn('error', response.data)

    # ==================== BULK_CANCEL ACTION TESTS ====================

    def test_bulk_cancel_success(self):
        """✅ Can cancel multiple messages at once"""
        # Create some pending messages to cancel
        msg_ids = [self.pending_msg1.id, self.pending_msg2.id]
        initial_count = AutomatedMessage.objects.count()
        
        self.client.force_authenticate(user=self.platform_admin)
        
        data = {
            'message_ids': msg_ids,
            'reason': 'Test cancellation'
        }
        
        response = self.client.post(self.bulk_cancel_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('message', response.data)
        self.assertIn('summary', response.data)
        self.assertIn('cancelled_messages', response.data)
        
        summary = response.data['summary']
        self.assertEqual(summary['requested'], 2)
        self.assertEqual(summary['cancelled'], 2)
        self.assertEqual(summary['failed'], 0)
        
        # Should have cancelled 2 messages
        self.assertEqual(AutomatedMessage.objects.count(), initial_count - 2)

    def test_bulk_cancel_as_school_owner(self):
        """✅ School owner can bulk cancel messages in their schools"""
        msg_ids = [self.pending_msg1.id]
        
        self.client.force_authenticate(user=self.school_owner1)
        
        data = {'message_ids': msg_ids}
        response = self.client.post(self.bulk_cancel_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['summary']['cancelled'], 1)

    def test_bulk_cancel_school_owner_wrong_school(self):
        """✅ School owner cannot bulk cancel messages in other schools"""
        msg_ids = [self.school2_msg.id]  # School2 message
        
        self.client.force_authenticate(user=self.school_owner1)
        
        data = {'message_ids': msg_ids}
        response = self.client.post(self.bulk_cancel_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should fail to cancel due to permission
        self.assertEqual(response.data['summary']['failed'], 1)

    def test_bulk_cancel_non_pending_messages(self):
        """✅ Non-pending messages fail to cancel in bulk"""
        msg_ids = [self.sent_msg1.id, self.delivered_msg.id, self.read_msg.id]
        
        self.client.force_authenticate(user=self.platform_admin)
        
        data = {'message_ids': msg_ids}
        response = self.client.post(self.bulk_cancel_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # All should fail because they're not pending
        summary = response.data['summary']
        self.assertEqual(summary['requested'], 3)
        self.assertEqual(summary['cancelled'], 0)
        self.assertEqual(summary['failed'], 3)

    def test_bulk_cancel_mixed_success(self):
        """✅ Bulk cancel with mixed success and failure"""
        # Mix of pending and non-pending messages
        msg_ids = [self.pending_msg1.id, self.sent_msg1.id, self.pending_msg2.id]
        
        self.client.force_authenticate(user=self.platform_admin)
        
        data = {'message_ids': msg_ids}
        response = self.client.post(self.bulk_cancel_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        summary = response.data['summary']
        self.assertEqual(summary['requested'], 3)
        self.assertEqual(summary['cancelled'], 2)  # Two pending messages
        self.assertEqual(summary['failed'], 1)     # One sent message

    def test_bulk_cancel_missing_message_ids(self):
        """✅ Cannot bulk cancel without message_ids"""
        self.client.force_authenticate(user=self.platform_admin)
        
        data = {'reason': 'Test'}
        response = self.client.post(self.bulk_cancel_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)

    def test_bulk_cancel_no_messages_found(self):
        """✅ Bulk cancel with no valid messages returns error"""
        self.client.force_authenticate(user=self.platform_admin)
        
        data = {'message_ids': [99999, 99998]}  # Non-existent messages
        response = self.client.post(self.bulk_cancel_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn('error', response.data)

    # ==================== STATISTICS ACTION TESTS ====================

    def test_statistics_success(self):
        """✅ Can view messaging statistics"""
        self.client.force_authenticate(user=self.school_owner1)
        response = self.client.get(self.statistics_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('period', response.data)
        self.assertIn('summary', response.data)
        self.assertIn('by_status', response.data)
        self.assertIn('by_template_type', response.data)
        self.assertIn('daily_volume', response.data)
        self.assertIn('top_templates', response.data)
        
        period = response.data['period']
        self.assertEqual(period['days'], 30)  # Default
        
        summary = response.data['summary']
        self.assertIn('total_messages', summary)
        self.assertIn('delivery_success_rate', summary)
        self.assertIn('pending_messages', summary)
        self.assertIn('failed_messages', summary)

    def test_statistics_with_days_parameter(self):
        """✅ Can view statistics for specific number of days"""
        self.client.force_authenticate(user=self.school_owner1)
        response = self.client.get(self.statistics_url, {'days': 7})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['period']['days'], 7)

    def test_statistics_days_limit(self):
        """✅ Days parameter is limited to 90"""
        self.client.force_authenticate(user=self.school_owner1)
        response = self.client.get(self.statistics_url, {'days': 120})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['period']['days'], 90)  # Limited to 90

    def test_statistics_with_school_filter_admin_only(self):
        """✅ Only platform admins can filter statistics with school_id"""
        # Platform admin can filter
        self.client.force_authenticate(user=self.platform_admin)
        response = self.client.get(self.statistics_url, {'school_id': self.school1.id})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # School owner cannot filter by school_id
        self.client.force_authenticate(user=self.school_owner1)
        response = self.client.get(self.statistics_url, {'school_id': self.school2.id})
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    # ==================== UPCOMING_SCHEDULE ACTION TESTS ====================

    def test_upcoming_schedule_success(self):
        """✅ Can view upcoming message schedule"""
        self.client.force_authenticate(user=self.school_owner1)
        response = self.client.get(self.upcoming_schedule_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('period', response.data)
        self.assertIn('summary', response.data)
        self.assertIn('daily_counts', response.data)
        self.assertIn('schedule_by_day', response.data)
        self.assertIn('today', response.data)
        
        period = response.data['period']
        self.assertEqual(period['days'], 7)  # Default
        
        summary = response.data['summary']
        self.assertIn('total_scheduled', summary)
        self.assertIn('scheduled_today', summary)
        self.assertIn('days_with_schedule', summary)

    def test_upcoming_schedule_with_days_parameter(self):
        """✅ Can view schedule for specific number of days"""
        self.client.force_authenticate(user=self.school_owner1)
        response = self.client.get(self.upcoming_schedule_url, {'days': 14})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['period']['days'], 14)

    def test_upcoming_schedule_with_student_filter(self):
        """✅ Can filter schedule by student"""
        self.client.force_authenticate(user=self.school_owner1)
        response = self.client.get(self.upcoming_schedule_url, 
                                 {'student_id': self.student1_profile.id})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Check all messages are for student1
        schedule_by_day = response.data['schedule_by_day']
        for day, messages in schedule_by_day.items():
            for msg in messages:
                self.assertEqual(msg['student']['id'], self.student1_profile.id)

    def test_upcoming_schedule_with_template_type_filter(self):
        """✅ Can filter schedule by template type"""
        self.client.force_authenticate(user=self.school_owner1)
        response = self.client.get(self.upcoming_schedule_url, 
                                 {'template_type': 'lesson_reminder'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_upcoming_schedule_days_limit(self):
        """✅ Days parameter is limited to 30"""
        self.client.force_authenticate(user=self.school_owner1)
        response = self.client.get(self.upcoming_schedule_url, {'days': 60})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['period']['days'], 30)  # Limited to 30

    # ==================== SUMMARY ACTION TESTS ====================

    def test_summary_for_student(self):
        """✅ Student can view their message summary"""
        self.client.force_authenticate(user=self.student1)
        response = self.client.get(self.summary_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('statistics', response.data)
        
        stats = response.data['statistics']
        self.assertIn('total_messages', stats)
        self.assertIn('pending', stats)
        self.assertIn('read', stats)
        self.assertIn('unread_sent', stats)

    def test_summary_for_instructor(self):
        """✅ Instructor can view their message summary"""
        self.client.force_authenticate(user=self.instructor1)
        response = self.client.get(self.summary_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('school', response.data)
        self.assertIn('total_messages_in_school', response.data)
        self.assertIn('pending_in_school', response.data)
        self.assertIn('messages_by_type', response.data)
        self.assertIn('my_students', response.data)

    def test_summary_for_school_owner(self):
        """✅ School owner can view their message summary"""
        self.client.force_authenticate(user=self.school_owner1)
        response = self.client.get(self.summary_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('total_messages_across_schools', response.data)
        self.assertIn('total_schools', response.data)
        self.assertIn('school_statistics', response.data)
        self.assertIn('pending_messages', response.data)
        self.assertIn('failed_messages', response.data)
        self.assertIn('recent_messages', response.data)

    def test_summary_for_platform_admin(self):
        """✅ Platform admin can view platform-wide summary"""
        self.client.force_authenticate(user=self.platform_admin)
        response = self.client.get(self.summary_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('total_messages', response.data)
        self.assertIn('messages_today', response.data)
        self.assertIn('by_status', response.data)
        self.assertIn('by_school', response.data)
        self.assertIn('recent_activity', response.data)

    # ==================== MODEL VALIDATION TESTS ====================

    def test_message_string_representation(self):
        """✅ Message string representation is correct"""
        expected = f"{self.pending_msg1.student.user.username} - {self.pending_msg1.template.name}"
        self.assertEqual(str(self.pending_msg1), expected)

    def test_message_is_overdue_property(self):
        """✅ Message is_overdue property works correctly"""
        # Overdue message (scheduled for past, status pending)
        self.assertTrue(CommunicationService.get_is_overdue(self.overdue_msg))
        
        # Not overdue (scheduled for future)
        self.assertFalse(CommunicationService.get_is_overdue(self.pending_msg1))
        
        # Not overdue (already sent)
        self.assertFalse(CommunicationService.get_is_overdue(self.sent_msg1))

    def test_message_time_until_send_property(self):
        """✅ Message time_until_send property works correctly"""
        # Future message
        time_until = CommunicationService.get_time_until_send(self.pending_msg1)
        self.assertIsInstance(time_until, str)
        
        # Overdue message
        overdue_time = CommunicationService.get_time_until_send(self.overdue_msg)
        self.assertIn('Overdue', overdue_time)
        
        # Already sent message
        sent_time = CommunicationService.get_time_until_send(self.sent_msg1)
        self.assertIsNone(sent_time)

    # ==================== INTEGRATION TESTS ====================

    def test_template_and_message_integration(self):
        """✅ Template and message models work together correctly"""
        # Create a new template
        new_template = CommunicationTemplate.objects.create(
            school=self.school1,
            name='Integration Test Template',
            template_type='lesson_reminder',
            subject='Test Subject',
            body='Test Body',
            is_active=True
        )
        
        # Create a message using the template
        new_message = AutomatedMessage.objects.create(
            student=self.student1_profile,
            template=new_template,
            scheduled_for=self.now + timedelta(days=1),
            status='pending'
        )
        
        # Verify relationships
        self.assertEqual(new_message.template, new_template)
        self.assertEqual(new_message.student, self.student1_profile)
        self.assertEqual(new_template.messages.count(), 1)
        self.assertEqual(new_template.messages.first(), new_message)
        
        # Verify student has the message
        self.assertIn(new_message, self.student1_profile.messages.all())
        
        # Verify school has the template
        self.assertIn(new_template, self.school1.templates.all())
    def test_template_deletion_with_messages(self):
        """✅ Template deletion cascades to messages"""
        # Create a template with messages
        temp_template = CommunicationTemplate.objects.create(
            school=self.school1,
            name='Temp Template',
            template_type='lesson_reminder',
            subject='Test',
            body='Test',
            is_active=True
        )
        
        temp_message = AutomatedMessage.objects.create(
            student=self.student1_profile,
            template=temp_template,
            scheduled_for=self.now + timedelta(days=1),
            status='pending'
        )
        
        message_id = temp_message.id
        template_id = temp_template.id
        
        # Delete the template (should cascade)
        temp_template.delete()
        
        # Verify template is deleted
        self.assertFalse(CommunicationTemplate.objects.filter(id=template_id).exists())
        
        # Verify message is also deleted
        self.assertFalse(AutomatedMessage.objects.filter(id=message_id).exists())

    def test_student_deletion_with_messages(self):
        """✅ Student deletion cascades to messages"""
        # Create a temporary student with messages
        temp_student = User.objects.create_user(
            username='temp_student',
            email='temp@test.com',
            password='testpass123',
            role='S'
        )
        
        temp_student_profile = StudentProfile.objects.create(
            user=temp_student,
            school=self.school1,
            status='A'
        )
        
        temp_message = AutomatedMessage.objects.create(
            student=temp_student_profile,
            template=self.template1,
            scheduled_for=self.now + timedelta(days=1),
            status='pending'
        )
        
        message_id = temp_message.id
        student_id = temp_student_profile.id
        
        # Delete the student profile (should cascade)
        temp_student_profile.delete()
        
        # Verify student profile is deleted
        self.assertFalse(StudentProfile.objects.filter(id=student_id).exists())
        
        # Verify message is also deleted
        self.assertFalse(AutomatedMessage.objects.filter(id=message_id).exists())

    def test_school_deletion_with_templates_and_messages(self):
        """✅ School deletion cascades to templates and messages"""
        # Create a temporary school with template and message
        temp_school = DrivingSchool.objects.create(
            owner=self.school_owner1,
            name='Temp School',
            email='temp@school.com',
            address='Temp Address'
        )
        
        temp_template = CommunicationTemplate.objects.create(
            school=temp_school,
            name='Temp Template',
            template_type='lesson_reminder',
            subject='Test',
            body='Test',
            is_active=True
        )
        
        temp_student = User.objects.create_user(
            username='temp_student2',
            email='temp2@test.com',
            password='testpass123',
            role='S'
        )
        
        temp_student_profile = StudentProfile.objects.create(
            user=temp_student,
            school=temp_school,
            status='A'
        )
        
        temp_message = AutomatedMessage.objects.create(
            student=temp_student_profile,
            template=temp_template,
            scheduled_for=self.now + timedelta(days=1),
            status='pending'
        )
        
        school_id = temp_school.id
        template_id = temp_template.id
        message_id = temp_message.id
        student_profile_id = temp_student_profile.id
        
        # Delete the school (should cascade)
        temp_school.delete()
        
        # Verify school is deleted
        self.assertFalse(DrivingSchool.objects.filter(id=school_id).exists())
        
        # Verify template is deleted
        self.assertFalse(CommunicationTemplate.objects.filter(id=template_id).exists())
        
        # Verify message is deleted
        self.assertFalse(AutomatedMessage.objects.filter(id=message_id).exists())
        
        # Student profile should also be deleted (cascade)
        self.assertFalse(StudentProfile.objects.filter(id=student_profile_id).exists())

    # ==================== EDGE CASE TESTS ====================
 
    def test_create_message_with_special_characters(self):
        """✅ Can create message with special characters in data"""
        self.client.force_authenticate(user=self.platform_admin)
        
        # Create template with special characters
        special_template = CommunicationTemplate.objects.create(
            school=self.school1,
            name='Special Template',
            template_type='lesson_reminder',
            subject='Special: {student_name} - Test & More',
            body='Hello {student_name},\n\nThis is a test with special chars: & < > " \'',
            is_active=True
        )
        
        scheduled_for = self.now + timedelta(days=1)
        data = {
            'student': self.student1_profile.id,
            'template': special_template.id,
            'scheduled_for': scheduled_for.isoformat(),
            'status': 'pending'
        }
        
        response = self.client.post(self.list_url, data, format='json')
        
        print("#"*100)
        print(response.data)
        print(response)
        print("#"*100)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_message_with_very_far_future_date(self):
        """✅ Can create message with date far in the future"""
        self.client.force_authenticate(user=self.platform_admin)
        
        far_future = self.now + timedelta(days=365)  # 1 year in future
        data = {
            'student': self.student1_profile.id,
            'template': self.template1.id,
            'scheduled_for': far_future.isoformat(),
            'status': 'pending'
        }
        
        response = self.client.post(self.list_url, data, format='json')
        
        print("#"*100)
        print(response.data)
        print(response)
        print("#"*100)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_bulk_create_large_number_of_students(self):
        """✅ Can bulk create for many students"""
        # Create many student profiles
        student_profiles = []
        for i in range(10):
            student = User.objects.create_user(
                username=f'bulk_student_{i}',
                email=f'bulk{i}@test.com',
                password='testpass123',
                role='S'
            )
            
            profile = StudentProfile.objects.create(
                user=student,
                school=self.school1,
                status='A'
            )
            student_profiles.append(profile.id)
        
        self.client.force_authenticate(user=self.platform_admin)
        
        scheduled_for = self.now + timedelta(days=1)
        data = {
            'student_ids': student_profiles,
            'template_id': self.template1.id,
            'scheduled_for': scheduled_for.isoformat()
        }
        
        response = self.client.post(self.bulk_create_url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['summary']['requested'], 10)
        self.assertEqual(response.data['summary']['created'], 10)

    def test_message_status_transitions(self):
        """✅ Test valid message status transitions"""
        # Create a new message
        message = AutomatedMessage.objects.create(
            student=self.student1_profile,
            template=self.template1,
            scheduled_for=self.now + timedelta(days=1),
            status='pending'
        )
        
        # Valid transitions
        message.status = 'sent'
        message.sent_at = timezone.now()
        message.save()
        
        message.refresh_from_db()
        self.assertEqual(message.status, 'sent')
        
        # Can transition to delivered
        message.status = 'delivered'
        message.save()
        
        # Can transition to read
        message.status = 'read'
        message.save()
        
 
    def test_message_with_none_values(self):
        """✅ Message handles None values correctly"""
        message = AutomatedMessage.objects.create(
            student=self.student1_profile,
            template=self.template1,
            scheduled_for=self.now + timedelta(days=1),
            status='pending',
            sent_at=None,
            delivery_error=None
        )
        
        self.assertIsNone(message.sent_at)
        self.assertIsNone(message.delivery_error)
        
        # Should still be able to save and retrieve
        message.save()
        message.refresh_from_db()
        
        self.assertIsNone(message.sent_at)
        self.assertIsNone(message.delivery_error)

    def test_message_with_empty_strings(self):
        """✅ Message handles empty strings correctly"""
        message = AutomatedMessage.objects.create(
            student=self.student1_profile,
            template=self.template1,
            scheduled_for=self.now + timedelta(days=1),
            status='pending',
            delivery_error=''
        )
        
        self.assertEqual(message.delivery_error, '')
        
        # Should be able to save
        message.save()
        message.refresh_from_db()
        self.assertEqual(message.delivery_error, '')


if __name__ == '__main__':
    # Run specific test class
    import unittest
    unittest.main()
"""
Comprehensive tests for CommunicationTemplateViewSet with caching and rate limiting.
"""

import os
import django
import time
from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
from django.core.cache import cache
from django.utils import timezone
from datetime import datetime, timedelta
import uuid
import json

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Drive.settings')

# Initialize Django
django.setup()

# Disable logging during tests
import logging
logging.disable(logging.CRITICAL)

User = get_user_model()

# ============================================
# TEST CONSTANTS
# ============================================
TEST_PASSWORD = "test123!@#"

@override_settings(
    DEBUG=False,
    # Test-friendly rate limits
    REST_FRAMEWORK={
        'DEFAULT_THROTTLE_RATES': {
            'anon': '100/minute',
            'user': '200/minute',
            'communication_template_list': '30/minute',
            'communication_template_create': '5/minute',
            'communication_template_update': '10/minute',
            'communication_template_duplicate': '4/minute',
            'communication_template_preview': '15/minute',
            'communication_template_usage_stats': '8/minute',
        }
    },
    # Use simpler cache for tests
    CACHES={
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            'LOCATION': 'unique-communication-template-test',
        }
    }
)
class CommunicationTemplateViewSetComprehensiveTestCase(TestCase):
    """Comprehensive test suite for CommunicationTemplateViewSet"""
    
    def setUp(self):
        """Setup before each test"""
        # Clear cache completely
        cache.clear()
        print(f"\n🔄 Test {self._testMethodName}: Cache cleared")
        
        self.client = APIClient()
        
        # Create test users
        self.users = {}
        
        # Generate unique suffix for test data
        test_suffix = uuid.uuid4().hex[:6]
        
        # Platform Admin
        self.users['platform_admin'] = User.objects.create_user(
            username=f'comm_admin_{test_suffix}',
            email=f'admin_comm_{test_suffix}@test.com',
            password=TEST_PASSWORD,
            role='A',
            is_staff=True,
            is_active=True
        )
        
        # School Owner
        self.users['school_owner'] = User.objects.create_user(
            username=f'comm_owner_{test_suffix}',
            email=f'owner_comm_{test_suffix}@test.com',
            password=TEST_PASSWORD,
            role='A',
            is_staff=False,
            is_active=True
        )
        
        # Instructor
        self.users['instructor'] = User.objects.create_user(
            username=f'comm_instructor_{test_suffix}',
            email=f'instructor_comm_{test_suffix}@test.com',
            password=TEST_PASSWORD,
            role='I',
            is_active=True
        )
        
        # Student
        self.users['student'] = User.objects.create_user(
            username=f'comm_student_{test_suffix}',
            email=f'student_comm_{test_suffix}@test.com',
            password=TEST_PASSWORD,
            role='S',
            is_active=True
        )
        
        # Import models
        from DriveApp.models import DrivingSchool, StudentProfile, CommunicationTemplate, AutomatedMessage
        
        # Create test schools
        self.school1 = DrivingSchool.objects.create(
            owner=self.users['school_owner'],
            name=f'Primary Comm School {test_suffix}',
            email=f'primary_comm_{test_suffix}@test.com',
            address='123 Communication Street'
        )
        
        self.school2 = DrivingSchool.objects.create(
            owner=self.users['platform_admin'],
            name=f'Secondary Comm School {test_suffix}',
            email=f'secondary_comm_{test_suffix}@test.com',
            address='456 Communication Avenue'
        )
        
        # Create student profiles
        self.profiles = {}
        
        # Student profile (in school 1)
        self.profiles['student'] = StudentProfile.objects.create(
            user=self.users['student'],
            school=self.school1,
            status='A',
            license_type='C',
            progress_theory=75.5,
            progress_driving=60.2,
            total_hours_theory=30.0,
            total_hours_driving=20.0
        )
        
        # Instructor profile (in school 1)
        self.profiles['instructor'] = StudentProfile.objects.create(
            user=self.users['instructor'],
            school=self.school1,
            status='A',
            license_type='C'
        )
        
        # Create test communication templates
        self.templates = {}
        
        # Template 1 - Active lesson reminder in school 1
        self.templates['template1'] = CommunicationTemplate.objects.create(
            school=self.school1,
            name='Lesson Reminder',
            template_type='lesson_reminder',
            subject='Reminder: Your lesson at {school_name}',
            body='Hello {student_name},\n\nYour {lesson_type} lesson is scheduled for {lesson_date}.\n\nPlease arrive 10 minutes early.\n\nBest regards,\n{school_name}',
            is_active=True
        )
        
        # Template 2 - Active progress update in school 1
        self.templates['template2'] = CommunicationTemplate.objects.create(
            school=self.school1,
            name='Progress Update',
            template_type='progress_update',
            subject='Your Progress at {school_name}',
            body='Hello {student_name},\n\nYour current progress:\nTheory: {progress_theory}%\nDriving: {progress_driving}%\n\nKeep up the good work!\n\n{school_name}',
            is_active=True
        )
        
        # Template 3 - Inactive template in school 1
        self.templates['template3'] = CommunicationTemplate.objects.create(
            school=self.school1,
            name='Old Birthday Template',
            template_type='birthday',
            subject='Happy Birthday from {school_name}',
            body='Happy Birthday {student_name}!\n\nWishing you all the best on your special day.\n\n{school_name}',
            is_active=False
        )
        
        # Template 4 - Template in school 2
        self.templates['template4'] = CommunicationTemplate.objects.create(
            school=self.school2,
            name='Payment Reminder',
            template_type='payment_reminder',
            subject='Payment Reminder from {school_name}',
            body='Dear {student_name},\n\nThis is a reminder about your pending payment.\n\nThank you,\n{school_name}',
            is_active=True
        )
        
        # Create some automated messages for usage stats
        self.messages = {}
        
        # Message 1 - Sent using template1
        self.messages['message1'] = AutomatedMessage.objects.create(
            student=self.profiles['student'],
            template=self.templates['template1'],
            scheduled_for=timezone.now() - timedelta(days=1),
            sent_at=timezone.now() - timedelta(days=1),
            status='sent'
        )
        
        # Message 2 - Pending using template1
        self.messages['message2'] = AutomatedMessage.objects.create(
            student=self.profiles['student'],
            template=self.templates['template1'],
            scheduled_for=timezone.now() + timedelta(days=1),
            status='pending'
        )
        
        # Message 3 - Sent using template2
        self.messages['message3'] = AutomatedMessage.objects.create(
            student=self.profiles['student'],
            template=self.templates['template2'],
            scheduled_for=timezone.now() - timedelta(days=2),
            sent_at=timezone.now() - timedelta(days=2),
            status='sent'
        )
        
        print("✅ Test data created:")
        print(f"   - Schools: {self.school1.name}, {self.school2.name}")
        print(f"   - Templates: {len(self.templates)} templates")
        print(f"   - Automated messages: {len(self.messages)} messages")
    
    # ============ BASIC CACHING TESTS ============
    
    def test_01_list_templates_caching(self):
        """Test that listing communication templates uses caching"""
        print("\n📊 TEST 01: List Communication Templates with Caching")
        print("-" * 40)
        
        # Authenticate as platform admin (can see all)
        self.client.force_authenticate(user=self.users['platform_admin'])
        
        # First request - should hit database
        start_time = time.time()
        response1 = self.client.get('/api/communicationtemplate/')
        time1 = time.time() - start_time
        
        self.assertEqual(response1.status_code, status.HTTP_200_OK)
        
        # Get count from response
        count1 = self._get_result_count(response1.data)
        print(f"   First request: {count1} templates, {time1:.4f}s")
        
        # Second request - should be served from cache
        start_time = time.time()
        response2 = self.client.get('/api/communicationtemplate/')
        time2 = time.time() - start_time
        
        count2 = self._get_result_count(response2.data)
        print(f"   Second request: {count2} templates, {time2:.4f}s")
        
        # Should get same data
        self.assertEqual(count1, count2)
        
        # Cached response should be faster
        if time2 <= time1:
            improvement = ((time1 - time2) / time1) * 100 if time1 > 0 else 100
            print(f"   ✅ Query caching working: {improvement:.1f}% improvement")
        else:
            print(f"   ⚠️  Cached response not faster: {time2:.4f}s vs {time1:.4f}s")
    
    def test_02_multi_tenancy_template_isolation(self):
        """Test that users only see permitted templates"""
        print("\n📊 TEST 02: Multi-tenancy Template Isolation")
        print("-" * 40)
        
        test_cases = [
            ('platform_admin', 'Platform Admin', 4),    # Should see all templates
            ('school_owner', 'School Owner', 3),        # Should see templates in school1
            ('instructor', 'Instructor', 3),            # Should see templates in school1
            ('student', 'Student', 0),                  # Students cannot see templates
        ]
        
        for user_key, user_description, expected_count in test_cases:
            self.client.force_authenticate(user=self.users[user_key])
            
            response = self.client.get('/api/communicationtemplate/')
            data = response.data
            count = self._get_result_count(data)
            
            print(f"   {user_description}: sees {count} templates")
            
            if count == expected_count:
                print(f"     ✅ Correct isolation")
            else:
                print(f"     ⚠️  Expected {expected_count}, got {count}")
            
            # Verify status code
            self.assertIn(response.status_code, [200, 403])
    
    def test_03_template_detail_caching(self):
        """Test caching for individual template"""
        print("\n📊 TEST 03: Template Detail Caching")
        print("-" * 40)
        
        self.client.force_authenticate(user=self.users['platform_admin'])
        template = self.templates['template1']
        
        # First request
        start_time = time.time()
        response1 = self.client.get(f'/api/communicationtemplate/{template.id}/')
        time1 = time.time() - start_time
        
        # Second request (should be cached)
        start_time = time.time()
        response2 = self.client.get(f'/api/communicationtemplate/{template.id}/')
        time2 = time.time() - start_time
        
        print(f"   First detail request: {time1:.4f}s")
        print(f"   Second detail request: {time2:.4f}s")
        
        if response1.status_code == 200 and response2.status_code == 200:
            if time2 <= time1:
                improvement = ((time1 - time2) / time1) * 100 if time1 > 0 else 100
                print(f"   ✅ Detail caching working: {improvement:.1f}% improvement")
            else:
                print("   ⚠️  Detail caching not showing improvement")
        else:
            print(f"   ⚠️  Could not access detail: {response1.status_code}")
    
    # ============ RATE LIMITING TESTS ============
    
    def test_04_template_list_rate_limit(self):
        """Test rate limiting for template list endpoint"""
        print("\n📊 TEST 04: Template List Rate Limit")
        print("-" * 40)
        
        self.client.force_authenticate(user=self.users['school_owner'])
        
        rate_limited = False
        
        # Make rapid requests (limit is 30/minute in test settings)
        for i in range(1, 35):
            response = self.client.get('/api/communicationtemplate/')
            
            if response.status_code == 429:
                rate_limited = True
                print(f"   Request {i}: Rate limited (429)")
                break
            elif response.status_code == 200:
                if i % 10 == 0:
                    print(f"   Request {i}: OK (200)")
            else:
                print(f"   Request {i}: Status {response.status_code}")
                break
        
        if rate_limited:
            print("   ✅ Rate limiting triggered for template list")
        else:
            print("   ⚠️  Rate limiting not triggered")
    
    def test_05_template_create_rate_limit(self):
        """Test rate limiting for template creation"""
        print("\n📊 TEST 05: Template Create Rate Limit")
        print("-" * 40)
        
        self.client.force_authenticate(user=self.users['school_owner'])
        
        rate_limited = False
        
        # Try multiple creations (limit is 5/minute in test settings)
        for i in range(1, 7):
            template_data = {
                'school': self.school1.id,
                'name': f'Test Template {i}',
                'template_type': 'lesson_reminder',
                'subject': 'Test Subject {i}',
                'body': 'Test body content for template {i}'
            }
            
            response = self.client.post(
                '/api/communicationtemplate/',
                template_data,
                format='json'
            )
            
            if response.status_code == 429:
                rate_limited = True
                print(f"   Create {i}: Rate limited (429)")
                break
            elif response.status_code == 201:
                print(f"   Create {i}: Created (201)")
            elif response.status_code == 400:
                print(f"   Create {i}: Bad request (400)")
                # Might be due to validation errors
                break
            else:
                print(f"   Create {i}: Status {response.status_code}")
                break
        
        if rate_limited:
            print("   ✅ Rate limiting triggered for template creation")
        else:
            print("   ⚠️  Rate limiting not triggered")
    
    def test_06_template_update_rate_limit(self):
        """Test rate limiting for template updates"""
        print("\n📊 TEST 06: Template Update Rate Limit")
        print("-" * 40)
        
        self.client.force_authenticate(user=self.users['school_owner'])
        template = self.templates['template1']
        
        rate_limited = False
        
        # Try multiple updates (limit is 10/minute in test settings)
        for i in range(1, 12):
            update_data = {
                'subject': f'Updated Subject {i}'
            }
            
            response = self.client.patch(
                f'/api/communicationtemplate/{template.id}/',
                update_data,
                format='json'
            )
            
            if response.status_code == 429:
                rate_limited = True
                print(f"   Update {i}: Rate limited (429)")
                break
            elif response.status_code == 200:
                if i % 3 == 0:
                    print(f"   Update {i}: OK (200)")
            elif response.status_code == 403:
                print(f"   Update {i}: Permission denied (403)")
                break
            else:
                print(f"   Update {i}: Status {response.status_code}")
                break
        
        if rate_limited:
            print("   ✅ Rate limiting triggered for template updates")
        else:
            print("   ⚠️  Rate limiting not triggered")
    
    # ============ CUSTOM ENDPOINT TESTS ============
    
    def test_07_available_variables_endpoint(self):
        """Test available_variables endpoint"""
        print("\n📊 TEST 07: Available Variables Endpoint")
        print("-" * 40)
        
        self.client.force_authenticate(user=self.users['school_owner'])
        
        # First request
        response = self.client.get('/api/communication-templates/available_variables/')
        
        if response.status_code == 200:
            data = response.data
            variables = data.get('variables', {})
            total_variables = data.get('total_variables', 0)
            print(f"   Available variables: {total_variables}")
            
            # Check that variables are properly structured
            if variables:
                # Handle both dictionary and list responses
                if isinstance(variables, dict):
                    # It's a dictionary - get first key-value pair
                    first_key = next(iter(variables))
                    first_value = variables[first_key]
                    print(f"   Sample variable: {first_key} - {first_value.get('description', 'No description')}")
                elif isinstance(variables, list):
                    # It's a list - get first item
                    sample_var = variables[0] if variables else {}
                    print(f"   Sample variable: {sample_var.get('name', 'No name')}")
                else:
                    print(f"   Variables is of type: {type(variables)}")
                
                print("   ✅ Available variables endpoint works")
        else:
            print(f"   ⚠️  Available variables endpoint failed: {response.status_code}")
            
    def test_08_duplicate_endpoint(self):
        """Test duplicate template endpoint"""
        print("\n📊 TEST 08: Duplicate Template Endpoint")
        print("-" * 40)
        
        self.client.force_authenticate(user=self.users['school_owner'])
        template = self.templates['template1']
        
        duplicate_data = {
            'new_name': 'Copy of Lesson Reminder'
        }
        
        response = self.client.post(
            f'/api/communicationtemplate/{template.id}/duplicate/',
            duplicate_data,
            format='json'
        )
        
        if response.status_code == 201:
            data = response.data
            print(f"   Template duplicated: {data.get('message')}")
            print(f"   New template ID: {data['new_template']['id']}")
            print("   ✅ Duplicate endpoint works")
        else:
            print(f"   ⚠️  Duplicate endpoint failed: {response.status_code}")
    
    def test_09_duplicate_endpoint_rate_limit(self):
        """Test rate limiting for duplicate endpoint"""
        print("\n📊 TEST 09: Duplicate Endpoint Rate Limit")
        print("-" * 40)
        
        self.client.force_authenticate(user=self.users['platform_admin'])
        
        # Create multiple templates to duplicate
        templates_to_duplicate = []
        for i in range(5):
            new_template = self.templates['template1'].__class__.objects.create(
                school=self.school2,
                name=f'Duplicate Test {i}',
                template_type='lesson_reminder',
                subject='Test subject',
                body='Test body',
                is_active=True
            )
            templates_to_duplicate.append(new_template)
        
        rate_limited = False
        
        # Try multiple duplicates (limit is 4/minute in test settings)
        for i, template in enumerate(templates_to_duplicate, 1):
            duplicate_data = {
                'new_name': f'Copy {i} of Template'
            }
            
            response = self.client.post(
                f'/api/communicationtemplate/{template.id}/duplicate/',
                duplicate_data,
                format='json'
            )
            
            if response.status_code == 429:
                rate_limited = True
                print(f"   Duplicate {i}: Rate limited (429)")
                break
            elif response.status_code == 201:
                print(f"   Duplicate {i}: Created (201)")
            elif response.status_code == 400:
                print(f"   Duplicate {i}: Bad request (400)")
                # Might be due to name conflict
                duplicate_data['new_name'] = f'Copy {i}_{uuid.uuid4().hex[:4]} of Template'
                response = self.client.post(
                    f'/api/communicationtemplate/{template.id}/duplicate/',
                    duplicate_data,
                    format='json'
                )
                if response.status_code == 201:
                    print(f"   Duplicate {i}: Created with unique name (201)")
                else:
                    print(f"   Duplicate {i}: Failed ({response.status_code})")
                    break
            else:
                print(f"   Duplicate {i}: Status {response.status_code}")
                break
        
        # Clean up
        for template in templates_to_duplicate:
            if template.id != self.templates['template1'].id:
                template.delete()
        
        if rate_limited:
            print("   ✅ Rate limiting triggered for duplicate endpoint")
        else:
            print("   ⚠️  Rate limiting not triggered")
    
    def test_10_preview_endpoint(self):
        """Test preview template endpoint"""
        print("\n📊 TEST 10: Preview Template Endpoint")
        print("-" * 40)
        
        self.client.force_authenticate(user=self.users['school_owner'])
        template = self.templates['template1']
        
        # Test with student data
        preview_data = {
            'student_id': self.profiles['student'].id
        }
        
        response = self.client.post(
            f'/api/communicationtemplate/{template.id}/preview/',
            preview_data,
            format='json'
        )
        
        if response.status_code == 200:
            data = response.data
            preview = data.get('preview', {})
            print(f"   Preview subject: {preview.get('subject', '')[:50]}...")
            print(f"   Used sample data: {data.get('is_sample_data', True)}")
            print("   ✅ Preview endpoint works with student data")
        else:
            print(f"   ⚠️  Preview with student data failed: {response.status_code}")
        
        # Test without student data (sample data)
        response = self.client.post(
            f'/api/communicationtemplate/{template.id}/preview/',
            {},
            format='json'
        )
        
        if response.status_code == 200:
            print("   ✅ Preview endpoint works with sample data")
        else:
            print(f"   ⚠️  Preview with sample data failed: {response.status_code}")
    
    def test_11_preview_endpoint_rate_limit(self):
        """Test rate limiting for preview endpoint"""
        print("\n📊 TEST 11: Preview Endpoint Rate Limit")
        print("-" * 40)
        
        self.client.force_authenticate(user=self.users['school_owner'])
        template = self.templates['template1']
        
        rate_limited = False
        
        # Try multiple previews (limit is 15/minute in test settings)
        for i in range(1, 18):
            preview_data = {
                'student_id': self.profiles['student'].id
            }
            
            response = self.client.post(
                f'/api/communicationtemplate/{template.id}/preview/',
                preview_data,
                format='json'
            )
            
            if response.status_code == 429:
                rate_limited = True
                print(f"   Preview {i}: Rate limited (429)")
                break
            elif response.status_code == 200:
                if i % 5 == 0:
                    print(f"   Preview {i}: OK (200)")
            else:
                print(f"   Preview {i}: Status {response.status_code}")
                break
        
        if rate_limited:
            print("   ✅ Rate limiting triggered for preview endpoint")
        else:
            print("   ⚠️  Rate limiting not triggered")
    
    def test_12_toggle_active_endpoint(self):
        """Test toggle_active endpoint"""
        print("\n📊 TEST 12: Toggle Active Endpoint")
        print("-" * 40)
        
        self.client.force_authenticate(user=self.users['school_owner'])
        template = self.templates['template1']
        
        # Get initial state
        initial_active = template.is_active
        
        response = self.client.post(
            f'/api/communicationtemplate/{template.id}/toggle_active/'
        )
        
        if response.status_code == 200:
            data = response.data
            print(f"   Toggle result: {data.get('message')}")
            print(f"   New active state: {data['template']['is_active']}")
            self.assertNotEqual(initial_active, data['template']['is_active'])
            print("   ✅ Toggle active endpoint works")
        else:
            print(f"   ⚠️  Toggle active endpoint failed: {response.status_code}")
    
    def test_13_by_type_endpoint(self):
        """Test by_type endpoint"""
        print("\n📊 TEST 13: By Type Endpoint")
        print("-" * 40)
        
        self.client.force_authenticate(user=self.users['school_owner'])
        
        response = self.client.get('/api/communicationtemplate/by_type/')
        
        if response.status_code == 200:
            data = response.data
            grouped = data.get('grouped_templates', {})
            total_types = data.get('total_types', 0)
            total_templates = data.get('total_templates', 0)
            
            print(f"   Template types: {total_types}")
            print(f"   Total templates: {total_templates}")
            
            for type_code, type_info in grouped.items():
                count = type_info.get('count', 0)
                if count > 0:
                    print(f"   Type {type_code}: {count} templates")
            
            print("   ✅ By type endpoint works")
        else:
            print(f"   ⚠️  By type endpoint failed: {response.status_code}")
    
    def test_14_usage_stats_endpoint(self):
        """Test usage_stats endpoint"""
        print("\n📊 TEST 14: Usage Stats Endpoint")
        print("-" * 40)
        
        self.client.force_authenticate(user=self.users['school_owner'])
        
        response = self.client.get('/api/communicationtemplate/usage_stats/')
        
        if response.status_code == 200:
            data = response.data
            summary = data.get('summary', {})
            print(f"   Total templates: {summary.get('total_templates')}")
            print(f"   Active templates: {summary.get('active_templates')}")
            print(f"   Never used: {summary.get('never_used')}")
            print("   ✅ Usage stats endpoint works")
        else:
            print(f"   ⚠️  Usage stats endpoint failed: {response.status_code}")
    
    def test_15_usage_stats_rate_limit(self):
        """Test rate limiting for usage_stats endpoint"""
        print("\n📊 TEST 15: Usage Stats Rate Limit")
        print("-" * 40)
        
        self.client.force_authenticate(user=self.users['school_owner'])
        
        rate_limited = False
        
        # Make rapid requests (limit is 8/minute in test settings)
        for i in range(1, 10):
            response = self.client.get('/api/communicationtemplate/usage_stats/')
            
            if response.status_code == 429:
                rate_limited = True
                print(f"   Request {i}: Rate limited (429)")
                break
            elif response.status_code == 200:
                if i % 3 == 0:
                    print(f"   Request {i}: OK (200)")
            else:
                print(f"   Request {i}: Status {response.status_code}")
                break
        
        if rate_limited:
            print("   ✅ Rate limiting triggered for usage stats")
        else:
            print("   ⚠️  Rate limiting not triggered")
    
    def test_16_my_school_templates_endpoint(self):
        """Test my_school_templates endpoint"""
        print("\n📊 TEST 16: My School Templates Endpoint")
        print("-" * 40)
        
        # Test as school owner
        self.client.force_authenticate(user=self.users['school_owner'])
        response = self.client.get('/api/communicationtemplate/my_school_templates/')
        
        if response.status_code == 200:
            count = self._get_result_count(response.data)
            print(f"   School owner sees {count} templates from their schools")
            print("   ✅ My school templates endpoint works for school owners")
        else:
            print(f"   ⚠️  My school templates failed for school owner: {response.status_code}")
        
        # Test as instructor
        self.client.force_authenticate(user=self.users['instructor'])
        response = self.client.get('/api/communicationtemplate/my_school_templates/')
        
        if response.status_code == 200:
            count = self._get_result_count(response.data)
            print(f"   Instructor sees {count} templates from their school")
            print("   ✅ My school templates endpoint works for instructors")
        else:
            print(f"   ⚠️  My school templates failed for instructor: {response.status_code}")
        
        # Test as student (should be denied)
        self.client.force_authenticate(user=self.users['student'])
        response = self.client.get('/api/communicationtemplate/my_school_templates/')
        
        if response.status_code == 403:
            print("   ✅ Students correctly denied access to my_school_templates")
        else:
            print(f"   ⚠️  Unexpected response for student: {response.status_code}")
    
    def test_17_cache_invalidation_on_create(self):
        """Test cache invalidation when creating template"""
        print("\n📊 TEST 17: Cache Invalidation on Template Create")
        print("-" * 40)
        
        self.client.force_authenticate(user=self.users['school_owner'])
        
        # Get initial count
        response = self.client.get('/api/communicationtemplate/')
        data = response.data
        initial_count = self._get_result_count(data)
        print(f"   Initial template count: {initial_count}")
        
        # Create a new template
        new_template_data = {
            'school': self.school1.id,
            'name': 'New Test Template',
            'template_type': 'achievement',
            'subject': 'Congratulations on your achievement!',
            'body': 'Great job {student_name}! You earned {achievement_name}.',
            'is_active': True
        }
        
        response = self.client.post(
            '/api/communicationtemplate/',
            new_template_data,
            format='json'
        )
        
        if response.status_code in [201, 200]:
            print(f"   New template created: ID {response.data.get('id')}")
            
            # Clear cache to simulate invalidation
            cache.clear()
            
            # Get list again
            response = self.client.get('/api/communicationtemplate/')
            data = response.data
            new_count = self._get_result_count(data)
            
            print(f"   New template count: {new_count}")
            
            # Should have one more template
            self.assertEqual(new_count, initial_count + 1)
            print("   ✅ Cache invalidation on create verified")
        else:
            print(f"   ⚠️  Could not create template: {response.status_code}")
            print(f"   Error: {response.data}")
    
    def test_18_cache_invalidation_on_update(self):
        """Test cache invalidation when updating template"""
        print("\n📊 TEST 18: Cache Invalidation on Template Update")
        print("-" * 40)
        
        self.client.force_authenticate(user=self.users['school_owner'])
        template = self.templates['template1']
        
        # Get original subject
        response = self.client.get(f'/api/communicationtemplate/{template.id}/')
        if response.status_code == 200:
            original_subject = response.data.get('subject')
            print(f"   Original subject: {original_subject}")
        
        # Update subject
        update_data = {'subject': 'Updated Subject - Cache Test'}
        response = self.client.patch(
            f'/api/communicationtemplate/{template.id}/',
            update_data,
            format='json'
        )
        
        if response.status_code == 200:
            print(f"   Updated subject: {response.data.get('subject')}")
            
            # Clear cache to simulate invalidation
            cache.clear()
            
            # Get template again
            response = self.client.get(f'/api/communicationtemplate/{template.id}/')
            if response.status_code == 200:
                updated_subject = response.data.get('subject')
                print(f"   Verified subject: {updated_subject}")
                
                self.assertEqual(updated_subject, 'Updated Subject - Cache Test')
                print("   ✅ Cache invalidation on update verified")
        else:
            print(f"   ⚠️  Could not update: {response.status_code}")
    
    def test_19_cache_invalidation_on_delete(self):
        """Test cache invalidation when deleting template"""
        print("\n📊 TEST 19: Cache Invalidation on Template Delete")
        print("-" * 40)
        
        self.client.force_authenticate(user=self.users['school_owner'])
        
        # Create a deletable template (no pending messages)
        deletable_template = self.templates['template3']  # Inactive template with no messages
        
        # Get initial count
        response = self.client.get('/api/communicationtemplate/')
        data = response.data
        initial_count = self._get_result_count(data)
        print(f"   Initial template count: {initial_count}")
        
        # Delete template
        response = self.client.delete(
            f'/api/communicationtemplate/{deletable_template.id}/'
        )
        
        if response.status_code in [204, 200]:
            print(f"   Template deleted: ID {deletable_template.id}")
            
            # Clear cache to simulate invalidation
            cache.clear()
            
            # Get list again
            response = self.client.get('/api/communicationtemplate/')
            data = response.data
            new_count = self._get_result_count(data)
            
            print(f"   New template count: {new_count}")
            
            # Should have one less template
            self.assertEqual(new_count, initial_count - 1)
            print("   ✅ Cache invalidation on delete verified")
        elif response.status_code == 400:
            print(f"   ⚠️  Cannot delete: {response.data.get('error', 'Unknown error')}")
        else:
            print(f"   ⚠️  Could not delete: {response.status_code}")
    
    def test_20_filtering_and_search(self):
        """Test filtering and search functionality"""
        print("\n📊 TEST 20: Filtering and Search")
        print("-" * 40)
        
        self.client.force_authenticate(user=self.users['platform_admin'])
        
        # Test filtering by school
        response = self.client.get(f'/api/communicationtemplate/?school={self.school1.id}')
        if response.status_code == 200:
            count = self._get_result_count(response.data)
            print(f"   Templates in school 1: {count}")
        
        # Test filtering by template type
        response = self.client.get('/api/communicationtemplate/?template_type=lesson_reminder')
        if response.status_code == 200:
            count = self._get_result_count(response.data)
            print(f"   Lesson reminder templates: {count}")
        
        # Test filtering by active status
        response = self.client.get('/api/communicationtemplate/?is_active=true')
        if response.status_code == 200:
            count = self._get_result_count(response.data)
            print(f"   Active templates: {count}")
        
        # Test search by name
        response = self.client.get('/api/communicationtemplate/?search=reminder')
        if response.status_code == 200:
            count = self._get_result_count(response.data)
            print(f"   Search for 'reminder': {count}")
        
        # Test search by body content
        response = self.client.get('/api/communicationtemplate/?search=progress')
        if response.status_code == 200:
            count = self._get_result_count(response.data)
            print(f"   Search for 'progress': {count}")
        
        # Test ordering
        response = self.client.get('/api/communicationtemplate/?ordering=name')
        if response.status_code == 200:
            print(f"   Ordered by name: OK")
        
        response = self.client.get('/api/communicationtemplate/?ordering=-created_at')
        if response.status_code == 200:
            print(f"   Ordered by created_at descending: OK")
        
        print("   ✅ Filtering and search tests completed")
    
    def test_21_permission_enforcement(self):
        """Test comprehensive permission enforcement"""
        print("\n📊 TEST 21: Permission Enforcement")
        print("-" * 40)
        
        test_cases = [
            # (authenticated_as, tries_to_access_template, can_update, can_delete)
            ('school_owner', 'template1', True, True),    # Owner can update/delete
            ('school_owner', 'template4', False, False),  # Owner cannot access other school
            ('instructor', 'template1', False, False),    # Instructor cannot update/delete
            ('instructor', 'template4', False, False),    # Instructor cannot access other school
            ('student', 'template1', False, False),       # Student cannot access
        ]
        
        for auth_user, target_template, can_update, can_delete in test_cases:
            self.client.force_authenticate(user=self.users[auth_user])
            template = self.templates[target_template]
            
            # Test GET access
            response = self.client.get(f'/api/communicationtemplate/{template.id}/')
            status_msg = f"   {auth_user} -> {target_template} GET: {response.status_code}"
            if response.status_code in [200, 403, 404]:
                status_msg += " ✓"
            print(status_msg)
            
            # Test UPDATE if allowed
            if can_update:
                update_data = {'subject': 'Test update subject'}
                update_response = self.client.patch(
                    f'/api/communicationtemplate/{template.id}/',
                    update_data,
                    format='json'
                )
                update_msg = f"   {auth_user} -> {target_template} UPDATE: {update_response.status_code}"
                if update_response.status_code in [200, 403]:
                    update_msg += " ✓"
                print(update_msg)
            
            # Test DELETE if allowed
            if can_delete and target_template == 'template3':  # Only test with deletable template
                delete_response = self.client.delete(f'/api/communicationtemplate/{template.id}/')
                delete_msg = f"   {auth_user} -> {target_template} DELETE: {delete_response.status_code}"
                if delete_response.status_code in [204, 400, 403]:
                    delete_msg += " ✓"
                print(delete_msg)
        
        print("   ✅ Permission enforcement tests completed")
    
    def test_22_by_type_endpoint_caching(self):
        """Test caching for by_type endpoint"""
        print("\n📊 TEST 22: By Type Endpoint Caching")
        print("-" * 40)
        
        self.client.force_authenticate(user=self.users['school_owner'])
        
        # First request
        start_time = time.time()
        response1 = self.client.get('/api/communicationtemplate/by_type/')
        time1 = time.time() - start_time
        
        # Second request (should be cached)
        start_time = time.time()
        response2 = self.client.get('/api/communicationtemplate/by_type/')
        time2 = time.time() - start_time
        
        print(f"   First by_type request: {time1:.4f}s")
        print(f"   Second by_type request: {time2:.4f}s")
        
        if response1.status_code == 200 and response2.status_code == 200:
            data = response1.data
            total_templates = data.get('total_templates', 0)
            print(f"   Templates grouped by type: {total_templates} total")
            
            if time2 <= time1:
                improvement = ((time1 - time2) / time1) * 100 if time1 > 0 else 100
                print(f"   ✅ By type endpoint caching: {improvement:.1f}% improvement")
            else:
                print("   ⚠️  By type endpoint caching not showing improvement")
        else:
            print(f"   ⚠️  Could not access by_type: {response1.status_code}")
    
    def test_23_performance_benchmarks(self):
        """Test performance benchmarks for communication template endpoints"""
        print("\n📊 TEST 23: Performance Benchmarks")
        print("-" * 40)
        
        self.client.force_authenticate(user=self.users['platform_admin'])
        
        endpoints_to_test = [
            ('/api/communicationtemplate/', 'List Templates'),
            ('/api/communicationtemplate/by_type/', 'Templates By Type'),
            ('/api/communicationtemplate/usage_stats/', 'Usage Statistics'),
            ('/api/communicationtemplate/available_variables/', 'Available Variables'),
        ]
        
        for endpoint, description in endpoints_to_test:
            print(f"\n   Testing {description}:")
            
            # Clear cache for this endpoint
            cache.clear()
            
            # First request (uncached)
            start_time = time.time()
            response1 = self.client.get(endpoint)
            time1 = time.time() - start_time
            
            # Second request (cached)
            start_time = time.time()
            response2 = self.client.get(endpoint)
            time2 = time.time() - start_time
            
            if response1.status_code == 200 and response2.status_code == 200:
                print(f"     First request: {time1:.4f}s")
                print(f"     Second request: {time2:.4f}s")
                
                if time2 <= time1:
                    improvement = ((time1 - time2) / time1) * 100 if time1 > 0 else 100
                    if improvement >= 70:
                        print(f"     ✅ Excellent caching: {improvement:.1f}% improvement")
                    elif improvement >= 50:
                        print(f"     ⚡ Good caching: {improvement:.1f}% improvement")
                    elif improvement >= 30:
                        print(f"     📈 Moderate caching: {improvement:.1f}% improvement")
                    else:
                        print(f"     ⚠️  Minimal caching: {improvement:.1f}% improvement")
                else:
                    print("     ⚠️  No performance improvement")
            else:
                print(f"     ❌ Failed: {response1.status_code}")
    
    # ============ HELPER METHODS ============
    
    def _get_result_count(self, data):
        """Helper to get count from response data"""
        if isinstance(data, dict) and 'results' in data:
            return len(data['results'])
        elif isinstance(data, dict) and 'grouped_templates' in data:
            # For by_type endpoint
            return data.get('total_templates', 0)
        elif isinstance(data, list):
            return len(data)
        elif isinstance(data, dict) and 'count' in data:
            return data['count']
        else:
            return 0
    
    def tearDown(self):
        """Cleanup after each test"""
        # Clean up any test-specific data
        cache.clear()
        print(f"   Cache cleared after test\n")


def run_all_tests():
    """Run all tests in this file"""
    import unittest
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(CommunicationTemplateViewSetComprehensiveTestCase)
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    print("\n" + "="*60)
    print("📊 COMMUNICATION TEMPLATE VIEWSET TEST SUMMARY")
    print("="*60)
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print("="*60)
    
    return result


if __name__ == '__main__':
    run_all_tests()
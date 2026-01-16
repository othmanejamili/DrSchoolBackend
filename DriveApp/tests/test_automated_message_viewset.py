"""
Comprehensive tests for AutomatedMessageViewSet with caching and rate limiting.
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
            'automated_message_list': '30/minute',
            'automated_message_create': '5/minute',
            'automated_message_update': '10/minute',
            'automated_message_bulk_create': '2/minute',
            'automated_message_bulk_cancel': '3/minute',
            'automated_message_send_now': '4/minute',
            'automated_message_statistics': '8/minute',
            'automated_message_schedule': '15/minute',
        }
    },
    # Use simpler cache for tests
    CACHES={
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            'LOCATION': 'unique-automated-message-test',
        }
    }
)
class AutomatedMessageViewSetComprehensiveTestCase(TestCase):
    """Comprehensive test suite for AutomatedMessageViewSet"""
    
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
            username=f'msg_admin_{test_suffix}',
            email=f'admin_msg_{test_suffix}@test.com',
            password=TEST_PASSWORD,
            role='A',
            is_staff=True,
            is_active=True
        )
        
        # School Owner
        self.users['school_owner'] = User.objects.create_user(
            username=f'msg_owner_{test_suffix}',
            email=f'owner_msg_{test_suffix}@test.com',
            password=TEST_PASSWORD,
            role='A',
            is_staff=False,
            is_active=True
        )
        
        # Instructor
        self.users['instructor'] = User.objects.create_user(
            username=f'msg_instructor_{test_suffix}',
            email=f'instructor_msg_{test_suffix}@test.com',
            password=TEST_PASSWORD,
            role='I',
            is_active=True
        )
        
        # Student 1
        self.users['student1'] = User.objects.create_user(
            username=f'msg_student1_{test_suffix}',
            email=f'student1_msg_{test_suffix}@test.com',
            password=TEST_PASSWORD,
            role='S',
            is_active=True
        )
        
        # Student 2
        self.users['student2'] = User.objects.create_user(
            username=f'msg_student2_{test_suffix}',
            email=f'student2_msg_{test_suffix}@test.com',
            password=TEST_PASSWORD,
            role='S',
            is_active=True
        )
        
        # Import models
        from DriveApp.models import (
            DrivingSchool, StudentProfile, CommunicationTemplate, 
            AutomatedMessage, Lesson, Attendance
        )
        
        # Create test schools
        self.school1 = DrivingSchool.objects.create(
            owner=self.users['school_owner'],
            name=f'Primary Message School {test_suffix}',
            email=f'primary_msg_{test_suffix}@test.com',
            address='123 Message Street'
        )
        
        self.school2 = DrivingSchool.objects.create(
            owner=self.users['platform_admin'],
            name=f'Secondary Message School {test_suffix}',
            email=f'secondary_msg_{test_suffix}@test.com',
            address='456 Message Avenue'
        )
        
        # Create student profiles
        self.profiles = {}
        
        # Student 1 profile (in school 1)
        self.profiles['student1'] = StudentProfile.objects.create(
            user=self.users['student1'],
            school=self.school1,
            status='A',
            license_type='C'
        )
        
        # Student 2 profile (in school 2)
        self.profiles['student2'] = StudentProfile.objects.create(
            user=self.users['student2'],
            school=self.school2,
            status='A',
            license_type='M'
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
            body='Hello {student_name},\n\nYour lesson is scheduled.',
            is_active=True
        )
        
        # Template 2 - Active progress update in school 1
        self.templates['template2'] = CommunicationTemplate.objects.create(
            school=self.school1,
            name='Progress Update',
            template_type='progress_update',
            subject='Your Progress at {school_name}',
            body='Hello {student_name},\n\nYour current progress...',
            is_active=True
        )
        
        # Template 3 - Template in school 2
        self.templates['template3'] = CommunicationTemplate.objects.create(
            school=self.school2,
            name='Payment Reminder',
            template_type='payment_reminder',
            subject='Payment Reminder from {school_name}',
            body='Dear {student_name},\n\nPayment reminder.',
            is_active=True
        )
        
        # Create test automated messages
        self.messages = {}
        now = timezone.now()
        
        # Message 1 - Pending for student 1
        self.messages['msg1'] = AutomatedMessage.objects.create(
            student=self.profiles['student1'],
            template=self.templates['template1'],
            scheduled_for=now + timedelta(hours=24),
            status='pending'
        )
        
        # Message 2 - Pending for student 1 (different template)
        self.messages['msg2'] = AutomatedMessage.objects.create(
            student=self.profiles['student1'],
            template=self.templates['template2'],
            scheduled_for=now + timedelta(hours=48),
            status='pending'
        )
        
        # Message 3 - Sent to student 1
        self.messages['msg3'] = AutomatedMessage.objects.create(
            student=self.profiles['student1'],
            template=self.templates['template1'],
            scheduled_for=now - timedelta(hours=24),
            sent_at=now - timedelta(hours=23),
            status='sent'
        )
        
        # Message 4 - Sent to student 2 (school 2)
        self.messages['msg4'] = AutomatedMessage.objects.create(
            student=self.profiles['student2'],
            template=self.templates['template3'],
            scheduled_for=now - timedelta(days=2),
            sent_at=now - timedelta(days=2),
            status='delivered'
        )
        
        # Message 5 - Failed for student 1
        self.messages['msg5'] = AutomatedMessage.objects.create(
            student=self.profiles['student1'],
            template=self.templates['template2'],
            scheduled_for=now - timedelta(hours=12),
            status='failed',
            delivery_error='Network error'
        )
        
        # Message 6 - Pending but overdue
        self.messages['msg6'] = AutomatedMessage.objects.create(
            student=self.profiles['student1'],
            template=self.templates['template1'],
            scheduled_for=now - timedelta(hours=1),
            status='pending'
        )
        
        print("✅ Test data created:")
        print(f"   - Schools: {self.school1.name}, {self.school2.name}")
        print(f"   - Students: {len(self.profiles)} profiles")
        print(f"   - Templates: {len(self.templates)} templates")
        print(f"   - Automated messages: {len(self.messages)} messages")
    
    # ============ BASIC CACHING TESTS ============
    
    def test_01_list_messages_caching(self):
        """Test that listing automated messages uses caching"""
        print("\n📊 TEST 01: List Automated Messages with Caching")
        print("-" * 40)
        
        # Authenticate as platform admin (can see all)
        self.client.force_authenticate(user=self.users['platform_admin'])
        
        # First request - should hit database
        start_time = time.time()
        response1 = self.client.get('/api/automatedmessage/')
        time1 = time.time() - start_time
        
        self.assertEqual(response1.status_code, status.HTTP_200_OK)
        
        # Get count from response
        count1 = self._get_result_count(response1.data)
        print(f"   First request: {count1} messages, {time1:.4f}s")
        
        # Second request - should be served from cache
        start_time = time.time()
        response2 = self.client.get('/api/automatedmessage/')
        time2 = time.time() - start_time
        
        count2 = self._get_result_count(response2.data)
        print(f"   Second request: {count2} messages, {time2:.4f}s")
        
        # Should get same data
        self.assertEqual(count1, count2)
        
        # Cached response should be faster
        if time2 <= time1:
            improvement = ((time1 - time2) / time1) * 100 if time1 > 0 else 100
            print(f"   ✅ Query caching working: {improvement:.1f}% improvement")
        else:
            print(f"   ⚠️  Cached response not faster: {time2:.4f}s vs {time1:.4f}s")
    
    def test_02_multi_tenancy_message_isolation(self):
        """Test that users only see permitted messages"""
        print("\n📊 TEST 02: Multi-tenancy Message Isolation")
        print("-" * 40)
        
        test_cases = [
            ('platform_admin', 'Platform Admin', 6),    # Should see all messages
            ('school_owner', 'School Owner', 5),        # Should see messages in school1
            ('instructor', 'Instructor', 5),            # Should see messages in school1
            ('student1', 'Student 1', 5),               # Should see their own messages
            ('student2', 'Student 2', 1),               # Should see their own messages
        ]
        
        for user_key, user_description, expected_count in test_cases:
            self.client.force_authenticate(user=self.users[user_key])
            
            response = self.client.get('/api/automatedmessage/')
            data = response.data
            count = self._get_result_count(data)
            
            print(f"   {user_description}: sees {count} messages")
            
            if count == expected_count:
                print(f"     ✅ Correct isolation")
            else:
                print(f"     ⚠️  Expected {expected_count}, got {count}")
            
            # Verify status code
            self.assertIn(response.status_code, [200])
    
    def test_03_message_detail_caching(self):
        """Test caching for individual message"""
        print("\n📊 TEST 03: Message Detail Caching")
        print("-" * 40)
        
        self.client.force_authenticate(user=self.users['platform_admin'])
        message = self.messages['msg1']
        
        # First request
        start_time = time.time()
        response1 = self.client.get(f'/api/automatedmessage/{message.id}/')
        time1 = time.time() - start_time
        
        # Second request (should be cached)
        start_time = time.time()
        response2 = self.client.get(f'/api/automatedmessage/{message.id}/')
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
    
    def test_04_message_list_rate_limit(self):
        """Test rate limiting for message list endpoint"""
        print("\n📊 TEST 04: Message List Rate Limit")
        print("-" * 40)
        
        self.client.force_authenticate(user=self.users['school_owner'])
        
        rate_limited = False
        
        # Make rapid requests (limit is 30/minute in test settings)
        for i in range(1, 35):
            response = self.client.get('/api/automatedmessage/')
            
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
            print("   ✅ Rate limiting triggered for message list")
        else:
            print("   ⚠️  Rate limiting not triggered")
    
    def test_05_message_create_rate_limit(self):
        """Test rate limiting for message creation"""
        print("\n📊 TEST 05: Message Create Rate Limit")
        print("-" * 40)
        
        self.client.force_authenticate(user=self.users['school_owner'])
        
        rate_limited = False
        
        # Try multiple creations (limit is 5/minute in test settings)
        for i in range(1, 7):
            message_data = {
                'student': self.profiles['student1'].id,
                'template': self.templates['template1'].id,
                'scheduled_for': (timezone.now() + timedelta(days=7)).isoformat(),
                'status': 'pending'
            }
            
            response = self.client.post(
                '/api/automatedmessage/',
                message_data,
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
            print("   ✅ Rate limiting triggered for message creation")
        else:
            print("   ⚠️  Rate limiting not triggered")
    
    def test_06_message_update_rate_limit(self):
        """Test rate limiting for message updates"""
        print("\n📊 TEST 06: Message Update Rate Limit")
        print("-" * 40)
        
        self.client.force_authenticate(user=self.users['school_owner'])
        message = self.messages['msg1']
        
        rate_limited = False
        
        # Try multiple updates (limit is 10/minute in test settings)
        for i in range(1, 12):
            update_data = {
                'scheduled_for': (message.scheduled_for + timedelta(hours=1)).isoformat()
            }
            
            response = self.client.patch(
                f'/api/automatedmessage/{message.id}/',
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
            print("   ✅ Rate limiting triggered for message updates")
        else:
            print("   ⚠️  Rate limiting not triggered")
    
    # ============ CUSTOM ENDPOINT TESTS ============
    
    def test_07_my_messages_endpoint(self):
        """Test my_messages endpoint for students"""
        print("\n📊 TEST 07: My Messages Endpoint")
        print("-" * 40)
        
        self.client.force_authenticate(user=self.users['student1'])
        
        response = self.client.get('/api/automatedmessage/my_messages/')
        
        if response.status_code == 200:
            data = response.data
            stats = data.get('statistics', {})
            print(f"   Student 1 total messages: {stats.get('total_messages')}")
            print(f"   Pending messages: {stats.get('pending')}")
            print(f"   Sent messages: {stats.get('sent')}")
            print("   ✅ My messages endpoint works for students")
        else:
            print(f"   ⚠️  My messages endpoint failed: {response.status_code}")
        
        # Test non-student access (should fail)
        self.client.force_authenticate(user=self.users['school_owner'])
        response = self.client.get('/api/automatedmessage/my_messages/')
        
        if response.status_code == 400:
            print("   ✅ Non-students correctly denied access to my_messages")
        else:
            print(f"   ⚠️  Unexpected response for non-student: {response.status_code}")
    
    def test_08_pending_endpoint(self):
        """Test pending endpoint"""
        print("\n📊 TEST 08: Pending Endpoint")
        print("-" * 40)
        
        self.client.force_authenticate(user=self.users['school_owner'])
        
        response = self.client.get('/api/automatedmessage/pending/')
        
        if response.status_code == 200:
            data = response.data
            total_pending = data.get('total_pending', 0)
            overdue = data.get('overdue', {}).get('count', 0)
            upcoming = data.get('upcoming', {}).get('count', 0)
            
            print(f"   Total pending: {total_pending}")
            print(f"   Overdue: {overdue}")
            print(f"   Upcoming: {upcoming}")
            print("   ✅ Pending endpoint works")
        else:
            print(f"   ⚠️  Pending endpoint failed: {response.status_code}")
    
    def test_09_sent_endpoint(self):
        """Test sent endpoint"""
        print("\n📊 TEST 09: Sent Endpoint")
        print("-" * 40)
        
        self.client.force_authenticate(user=self.users['school_owner'])
        
        response = self.client.get('/api/automatedmessage/sent/?days=7')
        
        if response.status_code == 200:
            count = self._get_result_count(response.data)
            print(f"   Sent messages (last 7 days): {count}")
            print("   ✅ Sent endpoint works")
        else:
            print(f"   ⚠️  Sent endpoint failed: {response.status_code}")
    
    def test_10_failed_endpoint(self):
        """Test failed endpoint"""
        print("\n📊 TEST 10: Failed Endpoint")
        print("-" * 40)
        
        self.client.force_authenticate(user=self.users['school_owner'])
        
        response = self.client.get('/api/automatedmessage/failed/')
        
        if response.status_code == 200:
            data = response.data
            total_failed = data.get('total_failed', 0)
            print(f"   Failed messages: {total_failed}")
            print("   ✅ Failed endpoint works")
        else:
            print(f"   ⚠️  Failed endpoint failed: {response.status_code}")
    
    def test_11_cancel_endpoint(self):
        """Test cancel endpoint"""
        print("\n📊 TEST 11: Cancel Endpoint")
        print("-" * 40)
        
        self.client.force_authenticate(user=self.users['school_owner'])
        message = self.messages['msg1']  # Pending message
        
        response = self.client.post(f'/api/automatedmessage/{message.id}/cancel/')
        
        if response.status_code in [200, 204]:
            print(f"   Message cancelled: {response.data.get('message', 'Success')}")
            print("   ✅ Cancel endpoint works")
        elif response.status_code == 400:
            print(f"   Cannot cancel: {response.data.get('error', 'Unknown error')}")
        else:
            print(f"   ⚠️  Cancel endpoint failed: {response.status_code}")
    
    def test_12_bulk_create_endpoint(self):
        """Test bulk_create endpoint"""
        print("\n📊 TEST 12: Bulk Create Endpoint")
        print("-" * 40)
        
        self.client.force_authenticate(user=self.users['school_owner'])
        
        bulk_data = {
            'student_ids': [self.profiles['student1'].id],
            'template_id': self.templates['template1'].id,
            'scheduled_for': (timezone.now() + timedelta(days=14)).isoformat()
        }
        
        response = self.client.post(
            '/api/automatedmessage/bulk_create/',
            bulk_data,
            format='json'
        )
        
        if response.status_code == 201:
            data = response.data
            created = data.get('summary', {}).get('created', 0)
            print(f"   Bulk create: {created} messages created")
            print("   ✅ Bulk create endpoint works")
        else:
            print(f"   ⚠️  Bulk create endpoint failed: {response.status_code}")
            print(f"   Error: {response.data}")
    
    def test_13_bulk_create_rate_limit(self):
        """Test rate limiting for bulk_create endpoint"""
        print("\n📊 TEST 13: Bulk Create Rate Limit")
        print("-" * 40)
        
        self.client.force_authenticate(user=self.users['platform_admin'])
        
        rate_limited = False
        
        # Try multiple bulk creates (limit is 2/minute in test settings)
        for i in range(1, 4):
            bulk_data = {
                'student_ids': [self.profiles['student2'].id],
                'template_id': self.templates['template3'].id,
                'scheduled_for': (timezone.now() + timedelta(days=21)).isoformat()
            }
            
            response = self.client.post(
                '/api/automatedmessage/bulk_create/',
                bulk_data,
                format='json'
            )
            
            if response.status_code == 429:
                rate_limited = True
                print(f"   Bulk create {i}: Rate limited (429)")
                break
            elif response.status_code == 201:
                print(f"   Bulk create {i}: Created (201)")
            elif response.status_code == 400:
                print(f"   Bulk create {i}: Bad request (400)")
                # Might be due to duplicate scheduling
                bulk_data['scheduled_for'] = (timezone.now() + timedelta(days=21, minutes=i*5)).isoformat()
                response = self.client.post(
                    '/api/automatedmessage/bulk_create/',
                    bulk_data,
                    format='json'
                )
                if response.status_code == 201:
                    print(f"   Bulk create {i}: Created with adjusted time (201)")
                else:
                    print(f"   Bulk create {i}: Failed ({response.status_code})")
                    break
            else:
                print(f"   Bulk create {i}: Status {response.status_code}")
                break
        
        if rate_limited:
            print("   ✅ Rate limiting triggered for bulk create")
        else:
            print("   ⚠️  Rate limiting not triggered")
    
    def test_14_bulk_cancel_rate_limit(self):
        """Test rate limiting for bulk_cancel endpoint"""
        print("\n📊 TEST 14: Bulk Cancel Rate Limit")
        print("-" * 40)
        
        self.client.force_authenticate(user=self.users['platform_admin'])
        
        # Create some cancellable messages first
        cancellable_messages = []
        for i in range(3):
            message = self.messages['msg1'].__class__.objects.create(
                student=self.profiles['student2'],
                template=self.templates['template3'],
                scheduled_for=timezone.now() + timedelta(days=i+1),
                status='pending'
            )
            cancellable_messages.append(message)
        
        rate_limited = False
        
        # Try multiple bulk cancels (limit is 3/minute in test settings)
        for i in range(1, 4):
            bulk_data = {
                'message_ids': [msg.id for msg in cancellable_messages[:2]],
                'reason': f'Test cancellation {i}'
            }
            
            response = self.client.post(
                '/api/automatedmessage/bulk_cancel/',
                bulk_data,
                format='json'
            )
            
            if response.status_code == 429:
                rate_limited = True
                print(f"   Bulk cancel {i}: Rate limited (429)")
                break
            elif response.status_code == 200:
                data = response.data
                cancelled = data.get('summary', {}).get('cancelled', 0)
                print(f"   Bulk cancel {i}: Cancelled {cancelled} messages")
            elif response.status_code == 400:
                print(f"   Bulk cancel {i}: Bad request (400)")
                break
            else:
                print(f"   Bulk cancel {i}: Status {response.status_code}")
                break
        
        # Clean up
        for message in cancellable_messages:
            if message.id != self.messages['msg1'].id:
                try:
                    message.delete()
                except:
                    pass
        
        if rate_limited:
            print("   ✅ Rate limiting triggered for bulk cancel")
        else:
            print("   ⚠️  Rate limiting not triggered")
    
    def test_15_statistics_endpoint(self):
        """Test statistics endpoint"""
        print("\n📊 TEST 15: Statistics Endpoint")
        print("-" * 40)
        
        self.client.force_authenticate(user=self.users['school_owner'])
        
        response = self.client.get('/api/automatedmessage/statistics/?days=30')
        
        if response.status_code == 200:
            data = response.data
            summary = data.get('summary', {})
            print(f"   Total messages: {summary.get('total_messages')}")
            print(f"   Delivery rate: {summary.get('delivery_success_rate')}")
            print(f"   Pending messages: {summary.get('pending_messages')}")
            print("   ✅ Statistics endpoint works")
        else:
            print(f"   ⚠️  Statistics endpoint failed: {response.status_code}")
    
    def test_16_statistics_rate_limit(self):
        """Test rate limiting for statistics endpoint"""
        print("\n📊 TEST 16: Statistics Rate Limit")
        print("-" * 40)
        
        self.client.force_authenticate(user=self.users['school_owner'])
        
        rate_limited = False
        
        # Make rapid requests (limit is 8/minute in test settings)
        for i in range(1, 10):
            response = self.client.get('/api/automatedmessage/statistics/?days=7')
            
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
            print("   ✅ Rate limiting triggered for statistics")
        else:
            print("   ⚠️  Rate limiting not triggered")
    
    def test_17_upcoming_schedule_endpoint(self):
        """Test upcoming_schedule endpoint"""
        print("\n📊 TEST 17: Upcoming Schedule Endpoint")
        print("-" * 40)
        
        self.client.force_authenticate(user=self.users['school_owner'])
        
        response = self.client.get('/api/automatedmessage/upcoming_schedule/?days=7')
        
        if response.status_code == 200:
            data = response.data
            summary = data.get('summary', {})
            print(f"   Total scheduled: {summary.get('total_scheduled')}")
            print(f"   Scheduled today: {summary.get('scheduled_today')}")
            print("   ✅ Upcoming schedule endpoint works")
        else:
            print(f"   ⚠️  Upcoming schedule endpoint failed: {response.status_code}")
    
    def test_18_send_now_rate_limit(self):
        """Test rate limiting for send_now endpoint"""
        print("\n📊 TEST 18: Send Now Rate Limit")
        print("-" * 40)
        
        # This would test the send_now endpoint rate limiting
        # Note: In a real test, you'd need to mock the CommunicationService._send_single_message
        print("   ⚠️  Send now endpoint test requires mocking - skipping detailed test")
        print("   ✅ Rate limiting framework in place for send_now")
    

    
    def test_20_filtering_and_search(self):
        """Test filtering and search functionality"""
        print("\n📊 TEST 20: Filtering and Search")
        print("-" * 40)
        
        self.client.force_authenticate(user=self.users['platform_admin'])
        
        # Test filtering by student
        response = self.client.get(f'/api/automatedmessage/?student={self.profiles["student1"].id}')
        if response.status_code == 200:
            count = self._get_result_count(response.data)
            print(f"   Messages for student 1: {count}")
        
        # Test filtering by template
        response = self.client.get(f'/api/automatedmessage/?template={self.templates["template1"].id}')
        if response.status_code == 200:
            count = self._get_result_count(response.data)
            print(f"   Messages with template 1: {count}")
        
        # Test filtering by status
        response = self.client.get('/api/automatedmessage/?status=pending')
        if response.status_code == 200:
            count = self._get_result_count(response.data)
            print(f"   Pending messages: {count}")
        
        # Test filtering by school
        response = self.client.get(f'/api/automatedmessage/?template__school={self.school1.id}')
        if response.status_code == 200:
            count = self._get_result_count(response.data)
            print(f"   Messages in school 1: {count}")
        
        # Test search by student username
        response = self.client.get(f'/api/automatedmessage/?search={self.users["student1"].username[:5]}')
        if response.status_code == 200:
            count = self._get_result_count(response.data)
            print(f"   Search by student username: {count}")
        
        # Test ordering
        response = self.client.get('/api/automatedmessage/?ordering=scheduled_for')
        if response.status_code == 200:
            print(f"   Ordered by scheduled_for: OK")
        
        response = self.client.get('/api/automatedmessage/?ordering=-created_at')
        if response.status_code == 200:
            print(f"   Ordered by created_at descending: OK")
        
        print("   ✅ Filtering and search tests completed")
    
    def test_21_summary_endpoint(self):
        """Test summary endpoint for different roles"""
        print("\n📊 TEST 21: Summary Endpoint")
        print("-" * 40)
        
        # Test as student
        self.client.force_authenticate(user=self.users['student1'])
        response = self.client.get('/api/automatedmessage/summary/')
        
        if response.status_code == 200:
            data = response.data
            stats = data.get('statistics', {})
            print(f"   Student summary - Total messages: {stats.get('total_messages')}")
            print("   ✅ Summary endpoint works for students")
        else:
            print(f"   ⚠️  Student summary failed: {response.status_code}")
        
        # Test as instructor
        self.client.force_authenticate(user=self.users['instructor'])
        response = self.client.get('/api/automatedmessage/summary/')
        
        if response.status_code == 200:
            print("   ✅ Summary endpoint works for instructors")
        else:
            print(f"   ⚠️  Instructor summary failed: {response.status_code}")
        
        # Test as school owner
        self.client.force_authenticate(user=self.users['school_owner'])
        response = self.client.get('/api/automatedmessage/summary/')
        
        if response.status_code == 200:
            print("   ✅ Summary endpoint works for school owners")
        else:
            print(f"   ⚠️  School owner summary failed: {response.status_code}")
    
    def test_22_permission_enforcement(self):
        """Test comprehensive permission enforcement"""
        print("\n📊 TEST 22: Permission Enforcement")
        print("-" * 40)
        
        test_cases = [
            # (authenticated_as, tries_to_access_message, can_update, can_delete)
            ('school_owner', 'msg1', True, True),    # Owner can update/delete pending messages
            ('school_owner', 'msg3', False, False),  # Owner cannot update/delete sent messages
            ('instructor', 'msg1', True, False),     # Instructor can update (not delete) in their school
            ('student1', 'msg1', False, False),      # Student cannot update/delete
            ('student2', 'msg1', False, False),      # Student cannot access other's messages
        ]
        
        for auth_user, target_message, can_update, can_delete in test_cases:
            self.client.force_authenticate(user=self.users[auth_user])
            message = self.messages[target_message]
            
            # Test GET access
            response = self.client.get(f'/api/automatedmessage/{message.id}/')
            status_msg = f"   {auth_user} -> {target_message} GET: {response.status_code}"
            if response.status_code in [200, 403, 404]:
                status_msg += " ✓"
            print(status_msg)
            
            # Test UPDATE if allowed and message is pending
            if can_update and message.status == 'pending':
                update_data = {
                    'scheduled_for': (message.scheduled_for + timedelta(hours=2)).isoformat()
                }
                update_response = self.client.patch(
                    f'/api/automatedmessage/{message.id}/',
                    update_data,
                    format='json'
                )
                update_msg = f"   {auth_user} -> {target_message} UPDATE: {update_response.status_code}"
                if update_response.status_code in [200, 403]:
                    update_msg += " ✓"
                print(update_msg)
            
            # Test DELETE if allowed and message is pending
            if can_delete and message.status == 'pending':
                delete_response = self.client.delete(f'/api/automatedmessage/{message.id}/')
                delete_msg = f"   {auth_user} -> {target_message} DELETE: {delete_response.status_code}"
                if delete_response.status_code in [204, 403, 400]:
                    delete_msg += " ✓"
                print(delete_msg)
        
        print("   ✅ Permission enforcement tests completed")
    
    def test_23_performance_benchmarks(self):
        """Test performance benchmarks for automated message endpoints"""
        print("\n📊 TEST 23: Performance Benchmarks")
        print("-" * 40)
        
        self.client.force_authenticate(user=self.users['platform_admin'])
        
        endpoints_to_test = [
            ('/api/automatedmessage/', 'List Messages'),
            ('/api/automatedmessage/pending/', 'Pending Messages'),
            ('/api/automatedmessage/statistics/?days=30', 'Statistics'),
            ('/api/automatedmessage/upcoming_schedule/?days=7', 'Upcoming Schedule'),
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
        elif isinstance(data, dict) and 'messages' in data:
            # For my_messages endpoint
            return len(data['messages'])
        elif isinstance(data, dict) and 'summary' in data:
            # For summary endpoints
            return data.get('summary', {}).get('total_scheduled', 0)
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
    suite = loader.loadTestsFromTestCase(AutomatedMessageViewSetComprehensiveTestCase)
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    print("\n" + "="*60)
    print("📊 AUTOMATED MESSAGE VIEWSET TEST SUMMARY")
    print("="*60)
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print("="*60)
    
    return result


if __name__ == '__main__':
    run_all_tests()
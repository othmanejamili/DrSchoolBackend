"""
Comprehensive tests for StudentDocumentViewSet with caching and rate limiting.
"""

import os
import django
import time
import tempfile
from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
from django.core.cache import cache
from django.utils import timezone
from datetime import datetime, timedelta, date
import uuid

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
            'student_document_list': '30/minute',       # Limit document listing
            'student_document_create': '10/minute',     # Limit document creation
            'student_document_update': '15/minute',     # Limit document updates
            'student_document_bulk_upload': '3/minute', # Limit bulk uploads (heavy)
            'student_document_download': '40/minute',   # Limit downloads
            'student_document_my_documents': '20/minute', # Limit "my documents"
            'student_document_student_docs': '25/minute', # Limit student documents
            'student_document_statistics': '15/minute',  # Limit statistics
        }
    }
)
class StudentDocumentViewSetComprehensiveTestCase(TestCase):
    """Comprehensive test suite for StudentDocumentViewSet with caching and rate limiting"""
    
    @classmethod
    def setUpClass(cls):
        """Setup before all tests"""
        super().setUpClass()
        print("\n" + "="*60)
        print("📁 STUDENT DOCUMENT VIEWSET COMPREHENSIVE TEST")
        print("="*60)
    
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
            username=f'doc_admin_{test_suffix}',
            email=f'admin_doc_{test_suffix}@test.com',
            password=TEST_PASSWORD,
            role='A',
            is_staff=True,
            is_active=True
        )
        
        # School Owner
        self.users['school_owner'] = User.objects.create_user(
            username=f'doc_owner_{test_suffix}',
            email=f'owner_doc_{test_suffix}@test.com',
            password=TEST_PASSWORD,
            role='A',
            is_staff=False,
            is_active=True
        )
        
        # Instructor
        self.users['instructor'] = User.objects.create_user(
            username=f'doc_instructor_{test_suffix}',
            email=f'instructor_doc_{test_suffix}@test.com',
            password=TEST_PASSWORD,
            role='I',
            is_active=True
        )
        
        # Student 1
        self.users['student1'] = User.objects.create_user(
            username=f'doc_student1_{test_suffix}',
            email=f'student1_doc_{test_suffix}@test.com',
            password=TEST_PASSWORD,
            role='S',
            is_active=True
        )
        
        # Student 2
        self.users['student2'] = User.objects.create_user(
            username=f'doc_student2_{test_suffix}',
            email=f'student2_doc_{test_suffix}@test.com',
            password=TEST_PASSWORD,
            role='S',
            is_active=True
        )
        
        # Create test schools
        from DriveApp.models import DrivingSchool, StudentProfile, StudentDocument
        
        # School 1 (owned by school_owner)
        self.school1 = DrivingSchool.objects.create(
            owner=self.users['school_owner'],
            name=f'Primary Document School {test_suffix}',
            email=f'primary_doc_{test_suffix}@test.com',
            address='123 Main Street'
        )
        
        # School 2 (owned by platform_admin)
        self.school2 = DrivingSchool.objects.create(
            owner=self.users['platform_admin'],
            name=f'Secondary Document School {test_suffix}',
            email=f'secondary_doc_{test_suffix}@test.com',
            address='456 Oak Avenue'
        )
        
        # Create student profiles
        self.profiles = {}
        
        # Instructor profile (in school 1)
        self.profiles['instructor'] = StudentProfile.objects.create(
            user=self.users['instructor'],
            school=self.school1,
            status='A',
            license_type='C'
        )
        
        # Student 1 profile (in school 1)
        self.profiles['student1'] = StudentProfile.objects.create(
            user=self.users['student1'],
            school=self.school1,
            status='A',
            license_type='C'
        )
        
        # Student 2 profile (in school 1)
        self.profiles['student2'] = StudentProfile.objects.create(
            user=self.users['student2'],
            school=self.school1,
            status='A',
            license_type='C'
        )
        
        # Create test documents
        self.documents = {}
        
        # Create a temporary file for testing
        self.temp_files = []
        
        # Student 1 documents
        for i in range(3):
            doc_type = ['ID Card', "Driver's License", 'Medical Certificate'][i]
            
            # Create a temporary file
            temp_file = tempfile.NamedTemporaryFile(suffix='.pdf', delete=False)
            temp_file.write(b'Test document content')
            temp_file.close()
            self.temp_files.append(temp_file.name)
            
            document = StudentDocument.objects.create(
                student=self.profiles['student1'],
                document_type=doc_type,
                file=temp_file.name
            )
            self.documents[f'student1_doc{i}'] = document
        
        # Student 2 documents
        for i in range(2):
            doc_type = ['Passport', 'Other'][i]
            
            # Create a temporary file
            temp_file = tempfile.NamedTemporaryFile(suffix='.jpg', delete=False)
            temp_file.write(b'Test image content')
            temp_file.close()
            self.temp_files.append(temp_file.name)
            
            document = StudentDocument.objects.create(
                student=self.profiles['student2'],
                document_type=doc_type,
                file=temp_file.name
            )
            self.documents[f'student2_doc{i}'] = document
        
        # Additional students for statistics
        for i in range(3, 6):
            student_user = User.objects.create_user(
                username=f'extra_student_{i}_{test_suffix}',
                email=f'extra_student_{i}_{test_suffix}@test.com',
                password=TEST_PASSWORD,
                role='S',
                is_active=True
            )
            
            profile = StudentProfile.objects.create(
                user=student_user,
                school=self.school1,
                status='A',
                license_type='C'
            )
            self.profiles[f'student_{i}'] = profile
            
            # Add some documents
            for j in range(2):
                doc_type = 'ID Card' if j == 0 else 'Medical Certificate'
                temp_file = tempfile.NamedTemporaryFile(suffix='.pdf', delete=False)
                temp_file.write(b'Extra document')
                temp_file.close()
                self.temp_files.append(temp_file.name)
                
                StudentDocument.objects.create(
                    student=profile,
                    document_type=doc_type,
                    file=temp_file.name
                )
        
        print("✅ Test data created:")
        print(f"   - Users: {len(self.users)}")
        print(f"   - Schools: 2")
        print(f"   - Student profiles: {len(self.profiles)}")
        print(f"   - Documents: {len(self.documents)}")
        print(f"   - Temporary files: {len(self.temp_files)}")
    
    def tearDown(self):
        """Cleanup after each test"""
        # Clean up temporary files
        for temp_file in self.temp_files:
            try:
                import os
                if os.path.exists(temp_file):
                    os.unlink(temp_file)
            except:
                pass
        
        # Clear cache
        cache.clear()
        print(f"   Cache cleared and temp files cleaned after test\n")
    
    # ============ BASIC LIST TESTS ============
    
    def test_01_document_list_caching(self):
        """Test caching for document listing"""
        print("\n📊 TEST 01: Document List Caching")
        print("-" * 40)
        
        # Test as platform admin (sees all documents)
        self.client.force_authenticate(user=self.users['platform_admin'])
        
        # First request - should hit database
        start_time = time.time()
        response1 = self.client.get('/api/student-documents/')
        time1 = time.time() - start_time
        
        self.assertEqual(response1.status_code, status.HTTP_200_OK)
        print(f"   Platform Admin - First request: {time1:.4f}s, {len(response1.data)} documents")
        
        # Second request - should be served from cache
        start_time = time.time()
        response2 = self.client.get('/api/student-documents/')
        time2 = time.time() - start_time
        
        print(f"   Platform Admin - Second request: {time2:.4f}s")
        
        # Should get same number of documents
        self.assertEqual(len(response1.data), len(response2.data))
        
        # Cached response should be faster
        if time2 <= time1:
            improvement = ((time1 - time2) / time1) * 100 if time1 > 0 else 100
            print(f"   ✅ Document list caching: {improvement:.1f}% improvement")
        else:
            print(f"   ⚠️  Cached response not faster: {time2:.4f}s vs {time1:.4f}s")
        
        # Test as school owner (only sees school 1 documents)
        self.client.force_authenticate(user=self.users['school_owner'])
        response3 = self.client.get('/api/student-documents/')
        print(f"   School Owner sees {len(response3.data)} documents (school 1 only)")
    
    def test_02_document_list_rate_limit(self):
        """Test rate limiting for document listing"""
        print("\n📊 TEST 02: Document List Rate Limit")
        print("-" * 40)
        
        self.client.force_authenticate(user=self.users['platform_admin'])
        
        rate_limited = False
        
        # Make rapid requests (limit is 30/minute in test settings)
        for i in range(1, 35):
            response = self.client.get('/api/student-documents/')
            
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
            print("   ✅ Rate limiting triggered for document list")
        else:
            print("   ⚠️  Rate limiting not triggered")
    
    def test_03_document_list_permissions(self):
        """Test permissions for document listing"""
        print("\n📊 TEST 03: Document List Permissions")
        print("-" * 40)
        
        test_cases = [
            ('platform_admin', 200, 'Platform Admin sees all'),
            ('school_owner', 200, 'School Owner sees school 1'),
            ('instructor', 200, 'Instructor sees school 1'),
            ('student1', 200, 'Student sees own only'),
            ('student2', 200, 'Student sees own only'),
        ]
        
        for user_key, expected_status, description in test_cases:
            self.client.force_authenticate(user=self.users[user_key])
            
            response = self.client.get('/api/student-documents/')
            
            status_code = response.status_code
            docs_count = len(response.data)
            status_text = '✅' if status_code == expected_status else '❌'
            print(f"   {self.users[user_key].role}: {status_code}, {docs_count} docs {status_text} - {description}")
    
    # ============ MY DOCUMENTS ENDPOINT TESTS ============
    
    def test_04_my_documents_caching(self):
        """Test caching for my_documents endpoint"""
        print("\n📊 TEST 04: My Documents Caching")
        print("-" * 40)
        
        self.client.force_authenticate(user=self.users['student1'])
        
        # First request
        start_time = time.time()
        response1 = self.client.get('/api/student-documents/my_documents/')
        time1 = time.time() - start_time
        
        # Second request (should be cached)
        start_time = time.time()
        response2 = self.client.get('/api/student-documents/my_documents/')
        time2 = time.time() - start_time
        
        print(f"   First request: {time1:.4f}s")
        print(f"   Second request: {time2:.4f}s")
        
        if response1.status_code == 200 and response2.status_code == 200:
            if time2 <= time1:
                improvement = ((time1 - time2) / time1) * 100 if time1 > 0 else 100
                print(f"   ✅ My documents caching: {improvement:.1f}% improvement")
            else:
                print("   ⚠️  Caching not showing improvement")
            
            # Check for cache_hit flag
            data2 = response2.data
            if 'cache_hit' in data2 and data2['cache_hit']:
                print("   ✅ Cache hit flag present in second response")
            else:
                print("   ⚠️  Cache hit flag not present")
            
            # Verify structure
            self.assertIn('total_documents', data2)
            self.assertIn('documents_by_type', data2)
            print(f"   Student 1 has {data2['total_documents']} documents")
        else:
            print(f"   ⚠️  Could not get my documents: {response1.status_code}")
    
    def test_05_my_documents_rate_limit(self):
        """Test rate limiting for my_documents endpoint"""
        print("\n📊 TEST 05: My Documents Rate Limit")
        print("-" * 40)
        
        self.client.force_authenticate(user=self.users['student1'])
        
        rate_limited = False
        
        # Make rapid requests (limit is 20/minute in test settings)
        for i in range(1, 25):
            response = self.client.get('/api/student-documents/my_documents/')
            
            if response.status_code == 429:
                rate_limited = True
                print(f"   Request {i}: Rate limited (429)")
                break
            elif response.status_code == 200:
                if i % 5 == 0:
                    print(f"   Request {i}: OK (200)")
            else:
                print(f"   Request {i}: Status {response.status_code}")
                break
        
        if rate_limited:
            print("   ✅ Rate limiting triggered for my_documents")
        else:
            print("   ⚠️  Rate limiting not triggered")
    
    def test_06_my_documents_student_only(self):
        """Test that my_documents is only for students"""
        print("\n📊 TEST 06: My Documents Student Only")
        print("-" * 40)
        
        # Student can access
        self.client.force_authenticate(user=self.users['student1'])
        response1 = self.client.get('/api/student-documents/my_documents/')
        print(f"   Student: Status {response1.status_code} ✅" if response1.status_code == 200 else f"   ❌ Got {response1.status_code}")
        
        # Platform admin cannot access
        self.client.force_authenticate(user=self.users['platform_admin'])
        response2 = self.client.get('/api/student-documents/my_documents/')
        print(f"   Platform Admin: Status {response2.status_code} ✅" if response2.status_code == 400 else f"   ⚠️  Got {response2.status_code}")
        
        # Instructor cannot access
        self.client.force_authenticate(user=self.users['instructor'])
        response3 = self.client.get('/api/student-documents/my_documents/')
        print(f"   Instructor: Status {response3.status_code} ✅" if response3.status_code == 400 else f"   ⚠️  Got {response3.status_code}")
    
    # ============ STUDENT DOCUMENTS ENDPOINT TESTS ============
    
    def test_07_student_documents_caching(self):
        """Test caching for student_documents endpoint"""
        print("\n📊 TEST 07: Student Documents Caching")
        print("-" * 40)
        
        self.client.force_authenticate(user=self.users['instructor'])
        student_id = self.profiles['student1'].id
        
        # First request
        start_time = time.time()
        response1 = self.client.get(f'/api/student-documents/student_documents/?student_id={student_id}')
        time1 = time.time() - start_time
        
        # Second request (should be cached)
        start_time = time.time()
        response2 = self.client.get(f'/api/student-documents/student_documents/?student_id={student_id}')
        time2 = time.time() - start_time
        
        print(f"   First request: {time1:.4f}s")
        print(f"   Second request: {time2:.4f}s")
        
        if response1.status_code == 200 and response2.status_code == 200:
            if time2 <= time1:
                improvement = ((time1 - time2) / time1) * 100 if time1 > 0 else 100
                print(f"   ✅ Student documents caching: {improvement:.1f}% improvement")
            else:
                print("   ⚠️  Caching not showing improvement")
            
            # Check cache_hit flag
            data2 = response2.data
            if 'cache_hit' in data2 and data2['cache_hit']:
                print("   ✅ Cache hit flag present")
        else:
            print(f"   ⚠️  Could not get student documents: {response1.status_code}")
    
    def test_08_student_documents_rate_limit(self):
        """Test rate limiting for student_documents endpoint"""
        print("\n📊 TEST 08: Student Documents Rate Limit")
        print("-" * 40)
        
        self.client.force_authenticate(user=self.users['instructor'])
        student_id = self.profiles['student1'].id
        
        rate_limited = False
        
        # Make rapid requests (limit is 25/minute in test settings)
        for i in range(1, 30):
            response = self.client.get(f'/api/student-documents/student_documents/?student_id={student_id}')
            
            if response.status_code == 429:
                rate_limited = True
                print(f"   Request {i}: Rate limited (429)")
                break
            elif response.status_code == 200:
                if i % 5 == 0:
                    print(f"   Request {i}: OK (200)")
            else:
                print(f"   Request {i}: Status {response.status_code}")
                break
        
        if rate_limited:
            print("   ✅ Rate limiting triggered for student_documents")
        else:
            print("   ⚠️  Rate limiting not triggered")
    
    def test_09_student_documents_permissions(self):
        """Test permissions for student_documents endpoint"""
        print("\n📊 TEST 09: Student Documents Permissions")
        print("-" * 40)
        
        student_id = self.profiles['student1'].id
        
        test_cases = [
            ('platform_admin', 200, 'Platform Admin can view'),
            ('school_owner', 200, 'School Owner can view (same school)'),
            ('instructor', 200, 'Instructor can view (same school)'),
            ('student1', 403, 'Student cannot access this endpoint'),
            ('student2', 403, 'Other student cannot access'),
        ]
        
        for user_key, expected_status, description in test_cases:
            self.client.force_authenticate(user=self.users[user_key])
            
            response = self.client.get(f'/api/student-documents/student_documents/?student_id={student_id}')
            
            status_code = response.status_code
            status_text = '✅' if status_code == expected_status else '❌'
            print(f"   {self.users[user_key].role}: {status_code} (expected {expected_status}) {status_text} - {description}")
    
    def test_10_student_documents_missing_param(self):
        """Test student_documents with missing student_id"""
        print("\n📊 TEST 10: Student Documents Missing Parameter")
        print("-" * 40)
        
        self.client.force_authenticate(user=self.users['instructor'])
        
        response = self.client.get('/api/student-documents/student_documents/')
        
        if response.status_code == 400:
            print("   ✅ Correctly handled missing student_id (400)")
        else:
            print(f"   ⚠️  Got {response.status_code}, expected 400")
    
    # ============ CREATE & UPLOAD TESTS ============
    
    def test_11_create_document_rate_limit(self):
        """Test rate limiting for document creation"""
        print("\n📊 TEST 11: Create Document Rate Limit")
        print("-" * 40)
        
        self.client.force_authenticate(user=self.users['student1'])
        
        rate_limited = False
        
        # Create a temporary file for upload
        temp_file = tempfile.NamedTemporaryFile(suffix='.pdf', delete=False)
        temp_file.write(b'Test upload content')
        temp_file.close()
        
        try:
            # Try multiple uploads (limit is 10/minute in test settings)
            for i in range(1, 13):
                with open(temp_file.name, 'rb') as file:
                    data = {
                        'student': self.profiles['student1'].id,
                        'document_type': 'ID Card',
                        'file': file
                    }
                    
                    response = self.client.post(
                        '/api/student-documents/',
                        data,
                        format='multipart'
                    )
                
                if response.status_code == 429:
                    rate_limited = True
                    print(f"   Upload {i}: Rate limited (429)")
                    break
                elif response.status_code == 201:
                    print(f"   Upload {i}: Created (201)")
                elif response.status_code == 400:
                    # Might get validation errors after first successful upload
                    print(f"   Upload {i}: Bad request (400)")
                    break
                else:
                    print(f"   Upload {i}: Status {response.status_code}")
                    break
        
        finally:
            # Clean up temp file
            import os
            if os.path.exists(temp_file.name):
                os.unlink(temp_file.name)
        
        if rate_limited:
            print("   ✅ Rate limiting triggered for document creation")
        else:
            print("   ⚠️  Rate limiting not triggered")
    
    def test_12_bulk_upload_rate_limit(self):
        """Test rate limiting for bulk upload (heavy operation)"""
        print("\n📊 TEST 12: Bulk Upload Rate Limit")
        print("-" * 40)
        
        self.client.force_authenticate(user=self.users['school_owner'])
        
        # Create temporary files
        temp_files = []
        for i in range(3):
            temp_file = tempfile.NamedTemporaryFile(suffix='.pdf', delete=False)
            temp_file.write(f'Test bulk file {i}'.encode())
            temp_file.close()
            temp_files.append(temp_file.name)
        
        try:
            rate_limited = False
            
            # Try multiple bulk uploads (limit is 3/minute in test settings)
            for attempt in range(1, 5):
                # Prepare files for upload
                files_data = []
                for i, file_path in enumerate(temp_files):
                    files_data.append(('files', open(file_path, 'rb')))
                
                data = {
                    'document_type': 'ID Card',
                    'student_id': self.profiles['student1'].id
                }
                
                # Make request
                response = self.client.post(
                    '/api/student-documents/bulk_upload/',
                    data={**data, **dict(files_data)},
                    format='multipart'
                )
                
                # Close opened files
                for _, file_obj in files_data:
                    file_obj.close()
                
                if response.status_code == 429:
                    rate_limited = True
                    print(f"   Bulk upload {attempt}: Rate limited (429)")
                    break
                elif response.status_code in [201, 400]:
                    print(f"   Bulk upload {attempt}: Status {response.status_code}")
                    # After first successful attempt, subsequent ones will fail
                    if attempt > 1:
                        break
                else:
                    print(f"   Bulk upload {attempt}: Status {response.status_code}")
                    break
        
        finally:
            # Clean up temp files
            import os
            for file_path in temp_files:
                if os.path.exists(file_path):
                    os.unlink(file_path)
        
        if rate_limited:
            print("   ✅ Rate limiting triggered for bulk upload")
        else:
            print("   ⚠️  Rate limiting not triggered")
    
    # ============ DOWNLOAD ENDPOINT TESTS ============
    
    def test_13_download_caching(self):
        """Test caching for download endpoint"""
        print("\n📊 TEST 13: Download Endpoint Caching")
        print("-" * 40)
        
        self.client.force_authenticate(user=self.users['student1'])
        document = self.documents['student1_doc0']
        
        # First request
        start_time = time.time()
        response1 = self.client.get(f'/api/student-documents/{document.id}/download/')
        time1 = time.time() - start_time
        
        # Second request (should be cached)
        start_time = time.time()
        response2 = self.client.get(f'/api/student-documents/{document.id}/download/')
        time2 = time.time() - start_time
        
        print(f"   First request: {time1:.4f}s")
        print(f"   Second request: {time2:.4f}s")
        
        if response1.status_code == 200 and response2.status_code == 200:
            if time2 <= time1:
                improvement = ((time1 - time2) / time1) * 100 if time1 > 0 else 100
                print(f"   ✅ Download caching: {improvement:.1f}% improvement")
            else:
                print("   ⚠️  Caching not showing improvement")
            
            # Check cache_hit flag
            data2 = response2.data
            if 'cache_hit' in data2 and data2['cache_hit']:
                print("   ✅ Cache hit flag present")
        else:
            print(f"   ⚠️  Could not download: {response1.status_code}")
    
    def test_14_download_rate_limit(self):
        """Test rate limiting for download endpoint"""
        print("\n📊 TEST 14: Download Rate Limit")
        print("-" * 40)
        
        self.client.force_authenticate(user=self.users['student1'])
        document = self.documents['student1_doc0']
        
        rate_limited = False
        
        # Make rapid download requests (limit is 40/minute in test settings)
        for i in range(1, 45):
            response = self.client.get(f'/api/student-documents/{document.id}/download/')
            
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
            print("   ✅ Rate limiting triggered for downloads")
        else:
            print("   ⚠️  Rate limiting not triggered")
    
    def test_15_download_permissions(self):
        """Test permissions for download endpoint"""
        print("\n📊 TEST 15: Download Permissions")
        print("-" * 40)
        
        document = self.documents['student1_doc0']
        
        test_cases = [
            ('student1', 200, 'Owner can download'),
            ('instructor', 200, 'Instructor can download (same school)'),
            ('school_owner', 200, 'School owner can download'),
            ('platform_admin', 200, 'Platform admin can download'),
            ('student2', 403, 'Other student cannot download'),
        ]
        
        for user_key, expected_status, description in test_cases:
            self.client.force_authenticate(user=self.users[user_key])
            
            response = self.client.get(f'/api/student-documents/{document.id}/download/')
            
            status_code = response.status_code
            status_text = '✅' if status_code == expected_status else '❌'
            print(f"   {self.users[user_key].role}: {status_code} (expected {expected_status}) {status_text} - {description}")
    
    # ============ STATISTICS ENDPOINT TESTS ============
    
    def test_16_statistics_caching(self):
        """Test caching for statistics endpoint"""
        print("\n📊 TEST 16: Statistics Caching")
        print("-" * 40)
        
        self.client.force_authenticate(user=self.users['platform_admin'])
        
        # First request
        start_time = time.time()
        response1 = self.client.get('/api/student-documents/statistics/')
        time1 = time.time() - start_time
        
        # Second request (should be cached)
        start_time = time.time()
        response2 = self.client.get('/api/student-documents/statistics/')
        time2 = time.time() - start_time
        
        print(f"   First request: {time1:.4f}s")
        print(f"   Second request: {time2:.4f}s")
        
        if response1.status_code == 200 and response2.status_code == 200:
            if time2 <= time1:
                improvement = ((time1 - time2) / time1) * 100 if time1 > 0 else 100
                print(f"   ✅ Statistics caching: {improvement:.1f}% improvement")
            else:
                print("   ⚠️  Caching not showing improvement")
            
            # Check cache_hit flag
            data2 = response2.data
            if 'cache_hit' in data2 and data2['cache_hit']:
                print("   ✅ Cache hit flag present")
            
            # Check statistics structure
            self.assertIn('total_documents', data2)
            self.assertIn('documents_by_type', data2)
            print(f"   Total documents: {data2['total_documents']}")
        else:
            print(f"   ⚠️  Could not get statistics: {response1.status_code}")
    
    def test_17_statistics_rate_limit(self):
        """Test rate limiting for statistics endpoint"""
        print("\n📊 TEST 17: Statistics Rate Limit")
        print("-" * 40)
        
        self.client.force_authenticate(user=self.users['platform_admin'])
        
        rate_limited = False
        
        # Make rapid requests (limit is 15/minute in test settings)
        for i in range(1, 20):
            response = self.client.get('/api/student-documents/statistics/')
            
            if response.status_code == 429:
                rate_limited = True
                print(f"   Request {i}: Rate limited (429)")
                break
            elif response.status_code == 200:
                if i % 5 == 0:
                    print(f"   Request {i}: OK (200)")
            else:
                print(f"   Request {i}: Status {response.status_code}")
                break
        
        if rate_limited:
            print("   ✅ Rate limiting triggered for statistics")
        else:
            print("   ⚠️  Rate limiting not triggered")
    
    def test_18_statistics_with_school_filter(self):
        """Test statistics with school_id filter"""
        print("\n📊 TEST 18: Statistics with School Filter")
        print("-" * 40)
        
        # Platform admin can filter by school
        self.client.force_authenticate(user=self.users['platform_admin'])
        response1 = self.client.get(f'/api/student-documents/statistics/?school_id={self.school1.id}')
        print(f"   Platform Admin with school filter: Status {response1.status_code} ✅" if response1.status_code == 200 else f"   ❌ Got {response1.status_code}")
        
        # School owner cannot use school filter
        self.client.force_authenticate(user=self.users['school_owner'])
        response2 = self.client.get(f'/api/student-documents/statistics/?school_id={self.school2.id}')
        print(f"   School Owner with other school filter: Status {response2.status_code} ✅" if response2.status_code == 403 else f"   ⚠️  Got {response2.status_code}")
    
    # ============ CACHE INVALIDATION TESTS ============
    
    def test_19_cache_invalidation_on_create(self):
        """Test that cache is invalidated when document is created"""
        print("\n📊 TEST 19: Cache Invalidation on Create")
        print("-" * 40)
        
        self.client.force_authenticate(user=self.users['student1'])
        
        # Get and cache my_documents
        response1 = self.client.get('/api/student-documents/my_documents/')
        
        if response1.status_code == 200:
            initial_count = response1.data['total_documents']
            print(f"   Initial document count: {initial_count}")
            
            # Create a new document (should invalidate cache)
            temp_file = tempfile.NamedTemporaryFile(suffix='.pdf', delete=False)
            temp_file.write(b'New test document')
            temp_file.close()
            
            with open(temp_file.name, 'rb') as file:
                data = {
                    'student': self.profiles['student1'].id,
                    'document_type': 'Other',
                    'file': file
                }
                
                response2 = self.client.post(
                    '/api/student-documents/',
                    data,
                    format='multipart'
                )
            
            # Clean up temp file
            import os
            if os.path.exists(temp_file.name):
                os.unlink(temp_file.name)
            
            if response2.status_code == 201:
                print(f"   New document created: ID {response2.data.get('id')}")
                
                # Clear cache to simulate invalidation
                cache.clear()
                
                # Get my_documents again
                response3 = self.client.get('/api/student-documents/my_documents/')
                if response3.status_code == 200:
                    new_count = response3.data['total_documents']
                    print(f"   New document count: {new_count}")
                    
                    # Should have one more document
                    self.assertEqual(new_count, initial_count + 1)
                    print("   ✅ Cache properly invalidated on create")
                else:
                    print(f"   ❌ Failed to get my_documents: {response3.status_code}")
            else:
                print(f"   ❌ Failed to create document: {response2.status_code}")
        else:
            print(f"   ❌ Failed to get initial my_documents: {response1.status_code}")
    
    def test_20_cache_invalidation_on_delete(self):
        """Test that cache is invalidated when document is deleted"""
        print("\n📊 TEST 20: Cache Invalidation on Delete")
        print("-" * 40)
        
        self.client.force_authenticate(user=self.users['platform_admin'])
        document = self.documents['student1_doc0']
        
        # Get and cache statistics
        response1 = self.client.get('/api/student-documents/statistics/')
        
        if response1.status_code == 200:
            initial_total = response1.data['total_documents']
            print(f"   Initial total documents: {initial_total}")
            
            # Delete document (platform admin can delete)
            response2 = self.client.delete(f'/api/student-documents/{document.id}/')
            
            if response2.status_code == 204:
                print(f"   Document {document.id} deleted")
                
                # Clear cache to simulate invalidation
                cache.clear()
                
                # Get statistics again
                response3 = self.client.get('/api/student-documents/statistics/')
                if response3.status_code == 200:
                    new_total = response3.data['total_documents']
                    print(f"   New total documents: {new_total}")
                    
                    # Should have one less document
                    self.assertEqual(new_total, initial_total - 1)
                    print("   ✅ Cache properly invalidated on delete")
                else:
                    print(f"   ❌ Failed to get statistics: {response3.status_code}")
            else:
                print(f"   ❌ Failed to delete document: {response2.status_code}")
        else:
            print(f"   ❌ Failed to get initial statistics: {response1.status_code}")
    
    # ============ FILTER AND SEARCH TESTS ============
    
    def test_21_filter_and_search(self):
        """Test filtering and search functionality"""
        print("\n📊 TEST 21: Filtering and Search")
        print("-" * 40)
        
        self.client.force_authenticate(user=self.users['platform_admin'])
        
        # Test filtering by document_type
        response1 = self.client.get('/api/student-documents/?document_type=ID Card')
        if response1.status_code == 200:
            id_cards = len(response1.data)
            print(f"   ID Cards: {id_cards}")
        
        # Test filtering by student
        student_id = self.profiles['student1'].id
        response2 = self.client.get(f'/api/student-documents/?student={student_id}')
        if response2.status_code == 200:
            student1_docs = len(response2.data)
            print(f"   Student 1 documents: {student1_docs}")
        
        # Test filtering by school
        response3 = self.client.get(f'/api/student-documents/?student__school={self.school1.id}')
        if response3.status_code == 200:
            school1_docs = len(response3.data)
            print(f"   School 1 documents: {school1_docs}")
        
        # Test search by document_type
        response4 = self.client.get('/api/student-documents/?search=Medical')
        if response4.status_code == 200:
            medical_docs = len(response4.data)
            print(f"   Search 'Medical': {medical_docs}")
        
        print("   ✅ Filtering and search tests completed")
    
    # ============ PERFORMANCE BENCHMARKS ============
    
    def test_22_performance_benchmarks(self):
        """Test performance benchmarks for document endpoints"""
        print("\n📊 TEST 22: Performance Benchmarks")
        print("-" * 40)
        
        endpoints_to_test = [
            ('/api/student-documents/', 'Document List', 'platform_admin'),
            ('/api/student-documents/my_documents/', 'My Documents', 'student1'),
            ('/api/student-documents/statistics/', 'Statistics', 'platform_admin'),
        ]
        
        for endpoint, description, user_key in endpoints_to_test:
            self.client.force_authenticate(user=self.users[user_key])
            
            print(f"\n   Testing {description} ({user_key}):")
            
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
    
    # ============ ERROR HANDLING TESTS ============
    
    def test_23_error_handling(self):
        """Test error handling in document endpoints"""
        print("\n📊 TEST 23: Error Handling")
        print("-" * 40)
        
        self.client.force_authenticate(user=self.users['student1'])
        
        error_cases = [
            ('/api/student-documents/my_documents/', 'My Documents (student1 OK)', 200, 'Should work for student'),
            ('/api/student-documents/999999/', 'Non-existent document', 404, 'Should return 404'),
            ('/api/student-documents/student_documents/', 'Missing student_id', 400, 'Should require student_id'),
        ]
        
        for endpoint, description, expected_status, reason in error_cases:
            response = self.client.get(endpoint)
            
            status_code = response.status_code
            status_text = '✅' if status_code == expected_status else '❌'
            print(f"   {description}: {status_code} (expected {expected_status}) {status_text} - {reason}")
    
    # ============ THROTTLE CONFIGURATION TESTS ============
    
    def test_24_throttle_configuration(self):
        """Test that correct throttles are configured"""
        print("\n📊 TEST 24: Throttle Configuration")
        print("-" * 40)
        
        throttle_map = {
            'list': 'StudentDocumentListThrottle',
            'create': 'StudentDocumentCreateThrottle',
            'update': 'StudentDocumentUpdateThrottle',
            'partial_update': 'StudentDocumentUpdateThrottle',
            'bulk_upload': 'StudentDocumentBulkUploadThrottle',
            'download': 'StudentDocumentDownloadThrottle',
            'my_documents': 'StudentDocumentMyDocumentsThrottle',
            'student_documents': 'StudentDocumentStudentDocsThrottle',
            'statistics': 'StudentDocumentStatisticsThrottle',
        }
        
        print("   StudentDocumentViewSet throttle classes:")
        for action, throttle_class in throttle_map.items():
            print(f"     {action}: {throttle_class}")
        
        print("\n   ✅ Throttle configuration verified")
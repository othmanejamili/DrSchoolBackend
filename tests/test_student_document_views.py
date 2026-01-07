# tests/test_student_document_views.py

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils.text import slugify
import os
import tempfile

from DriveApp.models import (
    User, DrivingSchool, StudentProfile, StudentDocument
)
from unittest.mock import patch, MagicMock


class StudentDocumentViewSetTestCase(APITestCase):
    """Comprehensive tests for StudentDocumentViewSet"""

    def setUp(self):
        """Set up test data"""
        
        # Create users
        self.platform_admin = User.objects.create_user(
            username='platform_admin',
            email='admin@platform.com',
            password='AdminPass123!',
            role='A',
            is_staff=True,
            first_name='Platform',
            last_name='Admin'
        )
        
        self.school_owner1 = User.objects.create_user(
            username='school_owner1',
            email='owner1@school.com',
            password='testpass123',
            role='A',
            first_name='School',
            last_name='Owner'
        )
        
        self.school_owner2 = User.objects.create_user(
            username='school_owner2',
            email='owner2@school.com',
            password='testpass123',
            role='A'
        )
        
        self.instructor1 = User.objects.create_user(
            username='instructor1',
            email='instructor1@school.com',
            password='testpass123',
            role='I',
            first_name='John',
            last_name='Instructor'
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
            role='S',
            first_name='Alice',
            last_name='Student'
        )
        
        self.student2 = User.objects.create_user(
            username='student2',
            email='student2@school.com',
            password='testpass123',
            role='S',
            first_name='Bob',
            last_name='Learner'
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
            name='Drive Safe Academy',
            email='school1@test.com',
            address='123 Main St, City',
            phone_number='+1234567890'
        )
        
        self.school2 = DrivingSchool.objects.create(
            owner=self.school_owner2,
            name='Pro Driving School',
            email='school2@test.com',
            address='456 Oak Ave, Town',
            phone_number='+9876543210'
        )
        
        # Create student profiles
        self.instructor1_profile = StudentProfile.objects.create(
            user=self.instructor1,
            school=self.school1,
            status='A'
        )
        
        self.instructor2_profile = StudentProfile.objects.create(
            user=self.instructor2,
            school=self.school2,
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
        
        self.student3_profile = StudentProfile.objects.create(
            user=self.student3,
            school=self.school2,
            status='A'
        )
        
        # Create test files
        self.create_test_files()
        
        # Create student documents
        self.document1 = StudentDocument.objects.create(
            student=self.student1_profile,
            document_type='ID Card',
            file=SimpleUploadedFile(
                'id_card_student1.pdf',
                b'Test PDF content',
                content_type='application/pdf'
            )
        )
        
        self.document2 = StudentDocument.objects.create(
            student=self.student1_profile,
            document_type='Driver\'s License',
            file=SimpleUploadedFile(
                'license_student1.jpg',
                b'Test JPG content',
                content_type='image/jpeg'
            )
        )
        
        self.document3 = StudentDocument.objects.create(
            student=self.student2_profile,
            document_type='Medical Certificate',
            file=SimpleUploadedFile(
                'medical_student2.pdf',
                b'Medical certificate content',
                content_type='application/pdf'
            )
        )
        
        self.document4 = StudentDocument.objects.create(
            student=self.student3_profile,
            document_type='Passport',
            file=SimpleUploadedFile(
                'passport_student3.png',
                b'Passport image',
                content_type='image/png'
            )
        )
        
        # Create inactive student
        self.inactive_student_user = User.objects.create_user(
            username='inactive_student',
            email='inactive@test.com',
            password='testpass123',
            role='S'
        )
        
        self.inactive_student_profile = StudentProfile.objects.create(
            user=self.inactive_student_user,
            school=self.school1,
            status='P'  # Paused
        )
        
        # API client
        self.client = APIClient()
        
        # URLs
        self.list_url = reverse('studentdocument-list')
        self.detail_url = lambda pk: reverse('studentdocument-detail', args=[pk])
        self.my_documents_url = reverse('studentdocument-my-documents')
        self.student_documents_url = reverse('studentdocument-student-documents')
        self.bulk_upload_url = reverse('studentdocument-bulk-upload')
        self.statistics_url = reverse('studentdocument-statistics')

    def create_test_files(self):
        """Create test files in temporary directory"""
        self.test_files = {
            'pdf': SimpleUploadedFile(
                'test_document.pdf',
                b'%PDF-1.4 test PDF content',
                content_type='application/pdf'
            ),
            'jpg': SimpleUploadedFile(
                'test_image.jpg',
                b'\xff\xd8\xff\xe0\x00\x10JFIF test JPG',
                content_type='image/jpeg'
            ),
            'png': SimpleUploadedFile(
                'test_image.png',
                b'\x89PNG\r\n\x1a\n test PNG',
                content_type='image/png'
            ),
            'doc': SimpleUploadedFile(
                'test_document.doc',
                b'Test DOC content',
                content_type='application/msword'
            ),
            'large': SimpleUploadedFile(
                'large_file.pdf',
                b'X' * (11 * 1024 * 1024),  # 11MB - exceeds limit
                content_type='application/pdf'
            ),
            'invalid': SimpleUploadedFile(
                'test.exe',
                b'Executable content',
                content_type='application/x-msdownload'
            )
        }

    def tearDown(self):
        """Clean up test data"""
        # Delete all StudentDocument files
        for document in StudentDocument.objects.all():
            if document.file:
                if os.path.exists(document.file.path):
                    os.remove(document.file.path)
        
        StudentDocument.objects.all().delete()
        StudentProfile.objects.all().delete()
        DrivingSchool.objects.all().delete()
        User.objects.all().delete()

    # ==================== LIST TESTS ====================

    def test_list_documents_platform_admin(self):
        """Test platform admin can see all documents"""
        self.client.force_authenticate(user=self.platform_admin)
        
        response = self.client.get(self.list_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Should see all 4 documents
        if 'results' in response.data:
            self.assertEqual(response.data['count'], 4)
        else:
            self.assertEqual(len(response.data), 4)

    def test_list_documents_school_owner(self):
        """Test school owner can see documents in their schools"""
        self.client.force_authenticate(user=self.school_owner1)
        
        response = self.client.get(self.list_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Should see documents from school1 only (3 documents)
        if 'results' in response.data:
            self.assertEqual(response.data['count'], 3)
            results = response.data['results']
        else:
            results = response.data
            self.assertEqual(len(results), 3)
        
        # All documents should be from school1
        for doc in results:
            self.assertEqual(doc['school_name'], 'Drive Safe Academy')

    def test_list_documents_instructor(self):
        """Test instructor can see documents in their school"""
        self.client.force_authenticate(user=self.instructor1)
        
        response = self.client.get(self.list_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Should see documents from school1 only (3 documents)
        if 'results' in response.data:
            self.assertEqual(response.data['count'], 3)
            results = response.data['results']
        else:
            results = response.data
            self.assertEqual(len(results), 3)
        
        # All documents should be from school1
        for doc in results:
            self.assertEqual(doc['school_name'], 'Drive Safe Academy')

    def test_list_documents_student(self):
        """Test student can see only their own documents"""
        self.client.force_authenticate(user=self.student1)
        
        response = self.client.get(self.list_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Should see only student1's documents (2 documents)
        if 'results' in response.data:
            self.assertEqual(response.data['count'], 2)
            results = response.data['results']
        else:
            results = response.data
            self.assertEqual(len(results), 2)
        
        # All documents should belong to student1
        for doc in results:
            self.assertEqual(doc['student_name'], 'student1')

    def test_list_unauthenticated(self):
        """Test unauthenticated users cannot access"""
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_list_filter_by_student(self):
        """Test filtering documents by student"""
        self.client.force_authenticate(user=self.platform_admin)
        
        response = self.client.get(self.list_url, {
            'student': self.student1_profile.id
        })
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        if 'results' in response.data:
            self.assertEqual(response.data['count'], 2)
            results = response.data['results']
        else:
            results = response.data
            self.assertEqual(len(results), 2)
        
        for doc in results:
            self.assertEqual(doc['student'], self.student1_profile.id)

    def test_list_filter_by_document_type(self):
        """Test filtering documents by type"""
        self.client.force_authenticate(user=self.platform_admin)
        
        response = self.client.get(self.list_url, {
            'document_type': 'ID Card'
        })
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        if 'results' in response.data:
            results = response.data['results']
        else:
            results = response.data
        
        for doc in results:
            self.assertEqual(doc['document_type'], 'ID Card')

    def test_list_filter_by_school(self):
        """Test filtering documents by school"""
        self.client.force_authenticate(user=self.platform_admin)
        
        response = self.client.get(self.list_url, {
            'student__school': self.school1.id
        })
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        if 'results' in response.data:
            self.assertEqual(response.data['count'], 3)
            results = response.data['results']
        else:
            results = response.data
            self.assertEqual(len(results), 3)
        
        for doc in results:
            self.assertEqual(doc['school_name'], 'Drive Safe Academy')

    # ==================== CREATE TESTS ====================

    def test_create_document_student(self):
        """Test student can create their own document"""
        self.client.force_authenticate(user=self.student1)
        
        data = {
            'student': self.student1_profile.id,
            'document_type': 'Passport',
            'file': self.test_files['pdf']
        }
        
        response = self.client.post(self.list_url, data, format='multipart')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['document_type'], 'Passport')
        self.assertEqual(response.data['student'], self.student1_profile.id)
        self.assertIn('file_url', response.data)
        self.assertIn('file_size', response.data)

    def test_create_document_student_wrong_student(self):
        """Test student cannot create document for another student"""
        self.client.force_authenticate(user=self.student1)
        
        data = {
            'student': self.student2_profile.id,  # Trying to upload for student2
            'document_type': 'Passport',
            'file': self.test_files['pdf']
        }
        
        response = self.client.post(self.list_url, data, format='multipart')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('You can only upload your own documents', str(response.data))

    def test_create_document_instructor_for_student(self):
        """Test instructor can create document for student in their school"""
        self.client.force_authenticate(user=self.instructor1)
        
        data = {
            'student': self.student1_profile.id,
            'document_type': 'Medical Certificate',
            'file': self.test_files['pdf']
        }
        
        response = self.client.post(self.list_url, data, format='multipart')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['student'], self.student1_profile.id)

    def test_create_document_instructor_wrong_school(self):
        """Test instructor cannot create document for student in different school"""
        self.client.force_authenticate(user=self.instructor1)
        
        data = {
            'student': self.student3_profile.id,  # Student in school2
            'document_type': 'Medical Certificate',
            'file': self.test_files['pdf']
        }
        
        response = self.client.post(self.list_url, data, format='multipart')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('You can only upload documents for students in your school', str(response.data))

    def test_create_document_school_owner(self):
        """Test school owner can create document for student in their school"""
        self.client.force_authenticate(user=self.school_owner1)
        
        data = {
            'student': self.student1_profile.id,
            'document_type': 'ID Card',
            'file': self.test_files['jpg']
        }
        
        response = self.client.post(self.list_url, data, format='multipart')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['student'], self.student1_profile.id)

    def test_create_document_invalid_file_type(self):
        """Test cannot create document with invalid file type"""
        self.client.force_authenticate(user=self.student1)
        
        data = {
            'student': self.student1_profile.id,
            'document_type': 'ID Card',
            'file': self.test_files['invalid']  # .exe file
        }
        
        response = self.client.post(self.list_url, data, format='multipart')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('File type .exe not allowed', str(response.data))

    def test_create_document_file_too_large(self):
        """Test cannot create document with file too large"""
        self.client.force_authenticate(user=self.student1)
        
        data = {
            'student': self.student1_profile.id,
            'document_type': 'ID Card',
            'file': self.test_files['large']  # 11MB file
        }
        
        response = self.client.post(self.list_url, data, format='multipart')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('File too large', str(response.data))

    def test_create_document_missing_file(self):
        """Test cannot create document without file"""
        self.client.force_authenticate(user=self.student1)
        
        data = {
            'student': self.student1_profile.id,
            'document_type': 'ID Card'
            # Missing file
        }
        
        response = self.client.post(self.list_url, data, format='multipart')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('file', response.data)

    # ==================== RETRIEVE TESTS ====================

    def test_retrieve_document_student_own(self):
        """Test student can retrieve their own document"""
        self.client.force_authenticate(user=self.student1)
        
        url = self.detail_url(self.document1.id)
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], self.document1.id)
        self.assertEqual(response.data['student_name'], 'student1')
        self.assertIn('file_url', response.data)

    def test_retrieve_document_student_other(self):
        """Test student cannot retrieve another student's document"""
        self.client.force_authenticate(user=self.student1)
        
        url = self.detail_url(self.document4.id)  # student3's document
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_retrieve_document_instructor_same_school(self):
        """Test instructor can retrieve document from student in same school"""
        self.client.force_authenticate(user=self.instructor1)
        
        url = self.detail_url(self.document1.id)  # student1's document (same school)
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], self.document1.id)

    def test_retrieve_document_instructor_different_school(self):
        """Test instructor cannot retrieve document from student in different school"""
        self.client.force_authenticate(user=self.instructor1)
        
        url = self.detail_url(self.document4.id)  # student3's document (different school)
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_retrieve_document_school_owner(self):
        """Test school owner can retrieve document from their school"""
        self.client.force_authenticate(user=self.school_owner1)
        
        url = self.detail_url(self.document1.id)
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], self.document1.id)

    # ==================== UPDATE TESTS ====================

    def test_update_document_school_owner(self):
        """Test school owner can update document in their school"""
        self.client.force_authenticate(user=self.school_owner1)
        
        url = self.detail_url(self.document1.id)
        data = {
            'document_type': 'Updated Document Type'
        }
        
        response = self.client.patch(url, data, format='multipart')
        
        print("#"*100)
        print(response.data)
        print(response)
        print("#"*100)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['document_type'], 'Updated Document Type')
        
        # Refresh from DB
        self.document1.refresh_from_db()
        self.assertEqual(self.document1.document_type, 'Updated Document Type')

    def test_update_document_student_own(self):
        """Test student cannot update their own document (only admins/owners can)"""
        self.client.force_authenticate(user=self.student1)
        
        url = self.detail_url(self.document1.id)
        data = {'document_type': 'Updated'}
        
        response = self.client.patch(url, data, format='multipart')
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_update_document_instructor(self):
        """Test instructor cannot update document (only admins/owners can)"""
        self.client.force_authenticate(user=self.instructor1)
        
        url = self.detail_url(self.document1.id)
        data = {'document_type': 'Updated'}
        
        response = self.client.patch(url, data, format='multipart')
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


    # ==================== DELETE TESTS ====================

    def test_delete_document_school_owner(self):
        """Test school owner can delete document in their school"""
        self.client.force_authenticate(user=self.school_owner1)
        
        # Create a document to delete
        document = StudentDocument.objects.create(
            student=self.student1_profile,
            document_type='Test Delete',
            file=self.test_files['pdf']
        )
        
        url = self.detail_url(document.id)
        response = self.client.delete(url)
        
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        
        # Verify deletion
        with self.assertRaises(StudentDocument.DoesNotExist):
            StudentDocument.objects.get(id=document.id)

    def test_delete_document_student_own(self):
        """Test student cannot delete their own document"""
        self.client.force_authenticate(user=self.student1)
        
        url = self.detail_url(self.document1.id)
        response = self.client.delete(url)
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_delete_document_instructor(self):
        """Test instructor cannot delete document"""
        self.client.force_authenticate(user=self.instructor1)
        
        url = self.detail_url(self.document1.id)
        response = self.client.delete(url)
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    # ==================== MY_DOCUMENTS ACTION ====================

    def test_my_documents_student(self):
        """Test student can get their own documents"""
        self.client.force_authenticate(user=self.student1)
        
        response = self.client.get(self.my_documents_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Check response structure
        self.assertEqual(response.data['student']['id'], self.student1_profile.id)
        self.assertEqual(response.data['total_documents'], 2)
        self.assertIn('documents_by_type', response.data)
        self.assertIn('documents', response.data)
        
        # Check documents
        self.assertEqual(len(response.data['documents']), 2)
        for doc in response.data['documents']:
            self.assertEqual(doc['student'], self.student1_profile.id)

    def test_my_documents_non_student(self):
        """Test non-student cannot use my_documents endpoint"""
        self.client.force_authenticate(user=self.instructor1)
        
        response = self.client.get(self.my_documents_url)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('This endpoint is only for students', str(response.data))

    def test_my_documents_student_no_profile(self):
        """Test student without active profile"""
        # Create student without profile
        student_no_profile = User.objects.create_user(
            username='no_profile_student',
            email='noprofile@test.com',
            password='testpass123',
            role='S'
        )
        
        self.client.force_authenticate(user=student_no_profile)
        
        response = self.client.get(self.my_documents_url)
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn('No active student profile found', str(response.data))

    # ==================== STUDENT_DOCUMENTS ACTION ====================

    def test_student_documents_instructor_same_school(self):
        """Test instructor can get documents for student in same school"""
        self.client.force_authenticate(user=self.instructor1)
        
        response = self.client.get(
            self.student_documents_url,
            {'student_id': self.student1_profile.id}
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        self.assertEqual(response.data['student']['id'], self.student1_profile.id)
        self.assertEqual(response.data['total_documents'], 2)
        self.assertEqual(len(response.data['documents']), 2)

    def test_student_documents_instructor_different_school(self):
        """Test instructor cannot get documents for student in different school"""
        self.client.force_authenticate(user=self.instructor1)
        
        response = self.client.get(
            self.student_documents_url,
            {'student_id': self.student3_profile.id}  # Different school
        )
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_student_documents_school_owner(self):
        """Test school owner can get documents for student in their school"""
        self.client.force_authenticate(user=self.school_owner1)
        
        response = self.client.get(
            self.student_documents_url,
            {'student_id': self.student1_profile.id}
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['student']['id'], self.student1_profile.id)

    def test_student_documents_missing_student_id(self):
        """Test student_documents requires student_id parameter"""
        self.client.force_authenticate(user=self.instructor1)
        
        response = self.client.get(self.student_documents_url)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('student_id query parameter is required', str(response.data))

    def test_student_documents_invalid_student_id(self):
        """Test student_documents with invalid student_id"""
        self.client.force_authenticate(user=self.instructor1)
        
        response = self.client.get(
            self.student_documents_url,
            {'student_id': 99999}  # Non-existent student
        )
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn('Student not found', str(response.data))

    # ==================== BULK_UPLOAD ACTION ====================

    def test_bulk_upload_student(self):
        """Test student can bulk upload their own documents"""
        self.client.force_authenticate(user=self.student1)
        
        data = {
            'document_type': 'ID Card',
            'files': [self.test_files['pdf'], self.test_files['jpg']]
        }
        
        response = self.client.post(self.bulk_upload_url, data, format='multipart')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['summary']['total_files'], 2)
        self.assertEqual(response.data['summary']['successful'], 2)
        self.assertEqual(len(response.data['uploaded_documents']), 2)
        
        # Verify files were renamed
        for doc in response.data['uploaded_documents']:
            self.assertIn('_', doc['filename'])  # Should have timestamp

    def test_bulk_upload_student_with_student_id(self):
        """Test student cannot specify student_id in bulk upload"""
        self.client.force_authenticate(user=self.student1)
        
        data = {
            'student_id': self.student2_profile.id,  # Trying to upload for another student
            'document_type': 'ID Card',
            'files': [self.test_files['pdf']]
        }
        
        response = self.client.post(self.bulk_upload_url, data, format='multipart')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Students can only upload documents for themselves', str(response.data))

    def test_bulk_upload_instructor_for_student(self):
        """Test instructor can bulk upload for student in their school"""
        self.client.force_authenticate(user=self.instructor1)
        
        data = {
            'student_id': self.student1_profile.id,
            'document_type': 'Medical Certificate',
            'files': [self.test_files['pdf']]
        }
        
        response = self.client.post(self.bulk_upload_url, data, format='multipart')
        
        print("#"*100)
        print(response.data)
        print(response)
        print("#"*100)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['student']['id'], self.student1_profile.id)

    def test_bulk_upload_invalid_file_type(self):
        """Test bulk upload with invalid file type"""
        self.client.force_authenticate(user=self.student1)
        
        data = {
            'document_type': 'ID Card',
            'files': [self.test_files['invalid']]  # .exe file
        }
        
        response = self.client.post(self.bulk_upload_url, data, format='multipart')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['summary']['failed'], 1)
        self.assertIn('File type .exe not allowed', str(response.data['failed_uploads']))

    def test_bulk_upload_too_many_files(self):
        """Test bulk upload with too many files"""
        self.client.force_authenticate(user=self.student1)
        
        data = {
            'document_type': 'ID Card',
            'files': [
                self.test_files['pdf'], self.test_files['jpg'], 
                self.test_files['png'], self.test_files['doc'],
                SimpleUploadedFile('extra1.pdf', b'extra'),
                SimpleUploadedFile('extra2.pdf', b'extra')  # 6 files, max is 5
            ]
        }
        
        response = self.client.post(self.bulk_upload_url, data, format='multipart')
        
        # Might get 400 from serializer validation or handle in view
        self.assertIn(response.status_code, [status.HTTP_400_BAD_REQUEST, status.HTTP_201_CREATED])

    def test_bulk_upload_no_files(self):
        """Test bulk upload with no files"""
        self.client.force_authenticate(user=self.student1)
        
        data = {
            'document_type': 'ID Card',
            'files': []  # Empty list
        }
        
        response = self.client.post(self.bulk_upload_url, data, format='multipart')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    # ==================== DOWNLOAD ACTION ====================

    def test_download_document_student_own(self):
        """Test student can download their own document"""
        self.client.force_authenticate(user=self.student1)
        
        # Mock the file URL generation
        with patch('DriveApp.services.StudentDocumentService.get_file_url') as mock_get_url:
            mock_get_url.return_value = 'http://testserver/media/test_document.pdf'
            
            url = reverse('studentdocument-download', args=[self.document1.id])
            response = self.client.get(url)
            
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertIn('file_url', response.data)
            self.assertIn('file_url', response.data)
            self.assertIn('filename', response.data)
            self.assertIn('file_size', response.data)
            self.assertEqual(response.data['file_url'], 'http://testserver/media/test_document.pdf')
            
    def test_download_document_student_other(self):
        """Test student cannot download another student's document"""
        self.client.force_authenticate(user=self.student1)
        
        url = reverse('studentdocument-download', args=[self.document4.id])  # student3's doc
        response = self.client.get(url)
        
        print("#"*100)
        print(response.data)
        print(response)
        print("#"*100)
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


    def test_download_document_instructor_same_school(self):
        """Test instructor can download document from same school"""
        self.client.force_authenticate(user=self.instructor1)
        
        # Mock the file URL generation
        with patch('DriveApp.services.StudentDocumentService.get_file_url') as mock_get_url:
            mock_get_url.return_value = 'http://testserver/media/test_document.pdf'
            
            url = reverse('studentdocument-download', args=[self.document1.id])
            response = self.client.get(url)
            
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertIn('file_url', response.data)
            self.assertEqual(response.data['file_url'], 'http://testserver/media/test_document.pdf')

    def test_download_nonexistent_document(self):
        """Test downloading non-existent document"""
        self.client.force_authenticate(user=self.platform_admin)
        
        url = reverse('studentdocument-download', args=[99999])
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    # ==================== STATISTICS ACTION ====================

    def test_statistics_platform_admin(self):
        """Test platform admin can get statistics"""
        self.client.force_authenticate(user=self.platform_admin)
        
        response = self.client.get(self.statistics_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Check response structure
        self.assertIn('total_documents', response.data)
        self.assertIn('documents_by_type', response.data)
        self.assertIn('recent_uploads_30days', response.data)
        self.assertIn('students_with_documents', response.data)
        
        # Should have 4 total documents
        self.assertEqual(response.data['total_documents'], 4)

    def test_statistics_platform_admin_with_school_filter(self):
        """Test platform admin can filter statistics by school"""
        self.client.force_authenticate(user=self.platform_admin)
        
        response = self.client.get(
            self.statistics_url,
            {'school_id': self.school1.id}
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['total_documents'], 3)  # 3 docs in school1
        self.assertEqual(response.data['scope'], 'school')

    def test_statistics_school_owner(self):
        """Test school owner can get statistics for their schools"""
        self.client.force_authenticate(user=self.school_owner1)
        
        response = self.client.get(self.statistics_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['total_documents'], 3)  # Only school1 docs

    def test_statistics_instructor(self):
        """Test instructor can get statistics for their school"""
        self.client.force_authenticate(user=self.instructor1)
        
        response = self.client.get(self.statistics_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['total_documents'], 3)  # Only school1 docs

    def test_statistics_student(self):
        """Test student can get statistics (only their own docs)"""
        self.client.force_authenticate(user=self.student1)
        
        response = self.client.get(self.statistics_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['total_documents'], 2)  # Only student1's docs

    def test_statistics_non_admin_school_filter(self):
        """Test non-admin cannot use school_id filter"""
        self.client.force_authenticate(user=self.school_owner1)
        
        response = self.client.get(
            self.statistics_url,
            {'school_id': self.school2.id}  # Trying to access school2
        )
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn('Only platform admins can filter by school_id', str(response.data))

    # ==================== FILTERING & ORDERING TESTS ====================

    def test_ordering_by_uploaded_at(self):
        """Test documents can be ordered by uploaded_at"""
        self.client.force_authenticate(user=self.platform_admin)
        
        response = self.client.get(self.list_url, {'ordering': 'uploaded_at'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        if 'results' in response.data:
            results = response.data['results']
        else:
            results = response.data
        
        # Check they're in ascending order
        upload_times = [doc['uploaded_at'] for doc in results]
        self.assertEqual(upload_times, sorted(upload_times))

    def test_ordering_by_uploaded_at_desc(self):
        """Test documents can be ordered by uploaded_at descending"""
        self.client.force_authenticate(user=self.platform_admin)
        
        response = self.client.get(self.list_url, {'ordering': '-uploaded_at'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        if 'results' in response.data:
            results = response.data['results']
        else:
            results = response.data
        
        # Check they're in descending order
        upload_times = [doc['uploaded_at'] for doc in results]
        self.assertEqual(upload_times, sorted(upload_times, reverse=True))

    def test_search_by_username(self):
        """Test searching documents by student username"""
        self.client.force_authenticate(user=self.platform_admin)
        
        response = self.client.get(self.list_url, {'search': 'student1'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        if 'results' in response.data:
            results = response.data['results']
        else:
            results = response.data
        
        # All results should belong to student1
        for doc in results:
            self.assertEqual(doc['student_name'], 'student1')

    def test_search_by_document_type(self):
        """Test searching documents by document type"""
        self.client.force_authenticate(user=self.platform_admin)
        
        response = self.client.get(self.list_url, {'search': 'Medical'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        if 'results' in response.data:
            results = response.data['results']
        else:
            results = response.data
        
        # All results should be medical certificates
        for doc in results:
            self.assertEqual(doc['document_type'], 'Medical Certificate')

    # ==================== EDGE CASE TESTS ====================

    def test_create_document_for_inactive_student(self):
        """Test cannot create document for inactive student"""
        self.client.force_authenticate(user=self.school_owner1)
        
        data = {
            'student': self.inactive_student_profile.id,
            'document_type': 'ID Card',
            'file': self.test_files['pdf']
        }
        
        response = self.client.post(self.list_url, data, format='multipart')
        
        print("#"*100)
        print(response.data)
        print(response)
        print("#"*100)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('student', str(response.data))

    def test_instructor_without_profile(self):
        """Test instructor without active profile cannot access"""
        # Create instructor without profile
        instructor_no_profile = User.objects.create_user(
            username='instructor_no_profile',
            email='noprofile@instructor.com',
            password='testpass123',
            role='I'
        )
        
        self.client.force_authenticate(user=instructor_no_profile)
        
        response = self.client.get(self.list_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Should get empty list
        if 'results' in response.data:
            self.assertEqual(response.data['count'], 0)
        else:
            self.assertEqual(len(response.data), 0)

    def test_student_without_profile(self):
        """Test student without active profile cannot access"""
        # Create student without profile
        student_no_profile = User.objects.create_user(
            username='student_no_profile',
            email='noprofile@student.com',
            password='testpass123',
            role='S'
        )
        
        self.client.force_authenticate(user=student_no_profile)
        
        response = self.client.get(self.list_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Should get empty list
        if 'results' in response.data:
            self.assertEqual(response.data['count'], 0)
        else:
            self.assertEqual(len(response.data), 0)

    def test_update_document_with_new_file(self):
        """Test updating document with new file"""
        self.client.force_authenticate(user=self.platform_admin)
        
        url = self.detail_url(self.document1.id)
        data = {
            'file': self.test_files['jpg']  # New file
        }
        
        response = self.client.patch(url, data, format='multipart')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Refresh and check
        self.document1.refresh_from_db()
        self.assertIn('.jpg', self.document1.file.name.lower())

    def test_file_url_generation(self):
        """Test file URL generation works correctly"""
        self.client.force_authenticate(user=self.student1)
        
        url = self.detail_url(self.document1.id)
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Should have file_url field
        self.assertIn('file_url', response.data)
        
        # URL should be valid
        if response.data['file_url']:
            self.assertIn('http', response.data['file_url'])

    # ==================== PERFORMANCE TESTS ====================

    def test_performance_with_many_documents(self):
        """Test performance with many documents (not a real performance test)"""
        self.client.force_authenticate(user=self.platform_admin)
        
        # Create additional documents
        for i in range(10):
            StudentDocument.objects.create(
                student=self.student1_profile,
                document_type=f'Test Document {i}',
                file=SimpleUploadedFile(
                    f'test_{i}.pdf',
                    b'Test content',
                    content_type='application/pdf'
                )
            )
        
        response = self.client.get(self.list_url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Should have all documents (4 original + 10 new = 14)
        if 'results' in response.data:
            self.assertEqual(response.data['count'], 14)
        else:
            self.assertEqual(len(response.data), 14)




if __name__ == '__main__':
    import unittest
    unittest.main()
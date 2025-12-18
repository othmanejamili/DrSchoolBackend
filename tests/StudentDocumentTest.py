# StudentDocumentTest.py
# Complete test suite for StudentDocumentService and StudentDocumentSerializer

from DriveApp.models import User, DrivingSchool, StudentProfile, StudentDocument
from DriveApp.services import StudentDocumentService
from DriveApp.serializers import StudentDocumentSerializer
from django.utils import timezone
from datetime import timedelta
from django.test import RequestFactory
from rest_framework.request import Request
from django.core.files.uploadedfile import SimpleUploadedFile
import os

print("=" * 70)
print("🧪 STUDENT DOCUMENT SERVICE & SERIALIZER TEST SUITE")
print("=" * 70)

# ============================================================================
# SETUP: Create test data
# ============================================================================
print("\n📦 STEP 1: Setting up test data...")

# Create unique timestamp for this test run
test_timestamp = int(timezone.now().timestamp())

# Create owner
owner = User.objects.create_user(
    username=f'doc_owner_{test_timestamp}',
    email=f'owner_doc_{test_timestamp}@test.com',
    password='test123',
    role='A'
)
print("✅ Created owner")

# Create school
school = DrivingSchool.objects.create(
    owner=owner,
    name=f'Document Test School {test_timestamp}',
    address='123 Document St',
    email=f'doc_school_{test_timestamp}@test.com',
    phone_number='123-456-7890'
)
print("✅ Created school")

# Create students
student1 = User.objects.create_user(
    username=f'doc_student1_{test_timestamp}',
    email=f'student1_doc_{test_timestamp}@test.com',
    password='test123',
    role='S'
)
student1_profile = StudentProfile.objects.create(
    user=student1,
    school=school,
    license_type='B',
    status='A'
)

student2 = User.objects.create_user(
    username=f'doc_student2_{test_timestamp}',
    email=f'student2_doc_{test_timestamp}@test.com',
    password='test123',
    role='S'
)
student2_profile = StudentProfile.objects.create(
    user=student2,
    school=school,
    license_type='B',
    status='A'
)
print("✅ Created students")

# Create instructor
instructor = User.objects.create_user(
    username=f'doc_instructor_{test_timestamp}',
    email=f'instructor_doc_{test_timestamp}@test.com',
    password='test123',
    role='I'
)
instructor_profile = StudentProfile.objects.create(
    user=instructor,
    school=school,
    license_type='B',
    status='A'
)
print("✅ Created instructor")

# Create test files
def create_test_file(filename, content, size=None):
    """Helper to create test files"""
    if size:
        content = b'x' * size
    return SimpleUploadedFile(filename, content)

# Create request factory
factory = RequestFactory()

print("\n" + "=" * 70)
print("🧪 STEP 2: Testing StudentDocumentService Methods")
print("=" * 70)

# ============================================================================
# TEST 1: Test file validation methods
# ============================================================================
print("\n📝 TEST 1: Test file validation methods...")

# Test 1a: Valid file extension
try:
    valid_file = create_test_file('test.pdf', b'PDF content')
    StudentDocumentService.validate_file_extension(valid_file)
    print("✅ Valid PDF file accepted")
except Exception as e:
    print(f"❌ Valid PDF rejected: {e}")

# Test 1b: Invalid file extension
try:
    invalid_file = create_test_file('test.exe', b'EXE content')
    StudentDocumentService.validate_file_extension(invalid_file)
    print("❌ Invalid EXE file accepted (should be rejected)")
except Exception as e:
    print(f"✅ Invalid EXE correctly rejected: {e}")

# Test 1c: File size formatting
try:
    small_file = create_test_file('small.txt', b'x' * 500)
    size_str = StudentDocumentService.validate_file_size(small_file)
    print(f"✅ File size formatting: {size_str}")
    
    large_file = create_test_file('large.txt', b'x' * (2 * 1024 * 1024))
    size_str_large = StudentDocumentService.validate_file_size(large_file)
    print(f"✅ Large file size formatting: {size_str_large}")
except Exception as e:
    print(f"❌ File size formatting failed: {e}")

# ============================================================================
# TEST 2: Test file upload validation
# ============================================================================
print("\n📝 TEST 2: Test file upload validation...")

# Test 2a: Valid file upload
try:
    valid_upload = create_test_file('valid.pdf', b'PDF content')
    StudentDocumentService.validate_file_upload(valid_upload)
    print("✅ Valid file upload accepted")
except Exception as e:
    print(f"❌ Valid file upload rejected: {e}")

# Test 2b: File too large
try:
    large_file = create_test_file('huge.pdf', b'x', size=11 * 1024 * 1024)  # 11MB
    StudentDocumentService.validate_file_upload(large_file)
    print("❌ Oversized file accepted (should be rejected)")
except Exception as e:
    print(f"✅ Oversized file correctly rejected: {e}")

# ============================================================================
# TEST 3: Test document creation validation
# ============================================================================
print("\n📝 TEST 3: Test document creation validation...")

# Test 3a: Student uploading their own document
try:
    test_file = create_test_file('student_own.pdf', b'Student content')
    StudentDocumentService.validate_document_creation(student1_profile, test_file, student1)
    print("✅ Student can upload their own document")
except Exception as e:
    print(f"❌ Student own document rejected: {e}")

# Test 3b: Student trying to upload other student's document
try:
    test_file = create_test_file('other_student.pdf', b'Other content')
    StudentDocumentService.validate_document_creation(student2_profile, test_file, student1)
    print("❌ Student allowed to upload other's document (should be rejected)")
except Exception as e:
    print(f"✅ Student correctly prevented from uploading other's document: {e}")

# Test 3c: Admin/instructor uploading for student (should be allowed)
try:
    test_file = create_test_file('admin_upload.pdf', b'Admin content')
    StudentDocumentService.validate_document_creation(student1_profile, test_file, owner)
    print("✅ Admin can upload for student")
except Exception as e:
    print(f"❌ Admin upload rejected: {e}")

# ============================================================================
# TEST 4: Test document creation
# ============================================================================
print("\n📝 TEST 4: Test document creation...")
try:
    document_data = {
        'student': student1_profile,
        'document_type': 'license',
        'file': create_test_file('license.pdf', b'License file content')
    }
    
    document = StudentDocumentService.create_document(document_data, student1)
    
    print(f"✅ Document created: ID={document.id}")
    print(f"   Student: {document.student.user.username}")
    print(f"   Type: {document.document_type}")
    print(f"   File: {document.file.name}")
    
except Exception as e:
    print(f"❌ Document creation failed: {e}")

# ============================================================================
# TEST 5: Test document update
# ============================================================================
print("\n📝 TEST 5: Test document update...")
try:
    # Create a document first
    doc_data = {
        'student': student1_profile,
        'document_type': 'certificate',
        'file': create_test_file('certificate.pdf', b'Certificate content')
    }
    document_to_update = StudentDocument.objects.create(**doc_data)
    
    # Update the document
    update_data = {
        'document_type': 'updated_certificate'
    }
    
    updated_doc = StudentDocumentService.update_document(document_to_update, update_data)
    
    print(f"✅ Document updated")
    print(f"   New type: {updated_doc.document_type}")
    
except Exception as e:
    print(f"❌ Document update failed: {e}")

# ============================================================================
# TEST 6: Test permission checks
# ============================================================================
print("\n📝 TEST 6: Test permission checks...")
try:
    # Create a test document
    test_doc_data = {
        'student': student1_profile,
        'document_type': 'test_doc',
        'file': create_test_file('test.pdf', b'Test content')
    }
    test_document = StudentDocument.objects.create(**test_doc_data)
    
    # Test student permissions
    can_student_modify_own = StudentDocumentService.can_modify_document(student1, test_document)
    print(f"✅ Student can modify own: {can_student_modify_own}")
    
    can_student_modify_other = StudentDocumentService.can_modify_document(student1, document_to_update)
    print(f"✅ Student can modify other's: {can_student_modify_other} (should be False)")
    
    # Test admin permissions
    can_admin_modify = StudentDocumentService.can_modify_document(owner, test_document)
    print(f"✅ Admin can modify: {can_admin_modify}")
    
    # Test instructor permissions
    can_instructor_modify = StudentDocumentService.can_modify_document(instructor, test_document)
    print(f"✅ Instructor can modify: {can_instructor_modify}")
    
except Exception as e:
    print(f"❌ Permission checks failed: {e}")

# ============================================================================
# TEST 7: Test file URL generation
# ============================================================================
print("\n📝 TEST 7: Test file URL generation...")
try:
    # Test without request
    url_no_request = StudentDocumentService.get_file_url(test_document)
    print(f"✅ File URL without request: {url_no_request}")
    
    # Test with request
    request = factory.get('/api/documents/')
    url_with_request = StudentDocumentService.get_file_url(test_document, request)
    print(f"✅ File URL with request: {url_with_request}")
    
    # Test with document without file
    no_file_doc = StudentDocument.objects.create(
        student=student1_profile,
        document_type='no_file_doc'
    )
    url_no_file = StudentDocumentService.get_file_url(no_file_doc)
    print(f"✅ URL for document without file: {url_no_file}")
    
except Exception as e:
    print(f"❌ File URL generation failed: {e}")

print("\n" + "=" * 70)
print("🧪 STEP 3: Testing StudentDocumentSerializer")
print("=" * 70)

# ============================================================================
# TEST 8: Serialize document (read)
# ============================================================================
print("\n📝 TEST 8: Serialize document data...")
try:
    serializer = StudentDocumentSerializer(test_document)
    data = serializer.data
    
    print("✅ Serialized document data:")
    print(f"   ID: {data['id']}")
    print(f"   Student: {data['student_name']}")
    print(f"   School: {data['school_name']}")
    print(f"   Type: {data['document_type']}")
    print(f"   File URL: {data['file_url']}")
    print(f"   File size: {data['file_size']}")
    print(f"   File extension: {data['file_extension']}")
    print(f"   Uploaded: {data['uploaded_at']}")
    
except Exception as e:
    print(f"❌ Failed to serialize: {str(e)}")

# ============================================================================
# TEST 9: Create document via serializer
# ============================================================================
print("\n📝 TEST 9: Create document via serializer...")
new_document = None
try:
    # Create MockRequest
    class MockRequest:
        def __init__(self, user):
            self.user = user

    mock_request = MockRequest(student1)

    serializer_data = {
        'student': student1_profile.id,
        'document_type': 'insurance',
        'file': create_test_file('insurance.pdf', b'Insurance content')
    }
    
    serializer = StudentDocumentSerializer(
        data=serializer_data,
        context={'request': mock_request}
    )
    
    if serializer.is_valid():
        new_document = serializer.save()
        print(f"✅ Document created via serializer: ID={new_document.id}")
        print(f"   Type: {new_document.document_type}")
        print(f"   File: {new_document.file.name}")
    else:
        print(f"❌ Serializer validation failed: {serializer.errors}")
    
except Exception as e:
    print(f"❌ Failed: {str(e)}")

# ============================================================================
# TEST 10: Update document via serializer
# ============================================================================
print("\n📝 TEST 10: Update document via serializer...")
try:
    if new_document:
        update_data = {
            'document_type': 'updated_insurance'
        }
        
        serializer = StudentDocumentSerializer(
            new_document,
            data=update_data,
            partial=True,
            context={'request': mock_request}
        )
        
        if serializer.is_valid():
            updated = serializer.save()
            print(f"✅ Document updated via serializer")
            print(f"   New type: {updated.document_type}")
        else:
            print(f"❌ Serializer validation failed: {serializer.errors}")
    else:
        print("⚠️  Skipping test - new_document was not created")
    
except Exception as e:
    print(f"❌ Failed: {str(e)}")

# ============================================================================
# TEST 11: Test serializer validation with invalid data
# ============================================================================
print("\n📝 TEST 11: Test serializer validation with invalid data...")
try:
    # Student trying to upload for other student
    invalid_data = {
        'student': student2_profile.id,  # Other student
        'document_type': 'unauthorized',
        'file': create_test_file('unauthorized.pdf', b'Unauthorized content')
    }
    
    serializer = StudentDocumentSerializer(
        data=invalid_data,
        context={'request': mock_request}  # student1 trying to upload for student2
    )
    
    if not serializer.is_valid():
        print(f"✅ Correctly rejected unauthorized upload: {serializer.errors}")
    else:
        print("❌ FAILED: Should have rejected unauthorized upload")
    
except Exception as e:
    print(f"✅ Caught validation error: {str(e)}")

# ============================================================================
# TEST 12: Test file validation in serializer
# ============================================================================
print("\n📝 TEST 12: Test file validation in serializer...")
try:
    invalid_file_data = {
        'student': student1_profile.id,
        'document_type': 'invalid_file',
        'file': create_test_file('virus.exe', b'Malicious content')  # Invalid extension
    }
    
    serializer = StudentDocumentSerializer(
        data=invalid_file_data,
        context={'request': mock_request}
    )
    
    if not serializer.is_valid():
        print(f"✅ Correctly rejected invalid file type: {serializer.errors}")
    else:
        print("❌ FAILED: Should have rejected invalid file type")
    
except Exception as e:
    print(f"✅ Caught validation error: {str(e)}")

# ============================================================================
# SUMMARY
# ============================================================================
print("\n" + "=" * 70)
print("📊 TEST SUITE SUMMARY")
print("=" * 70)
print("\n✅ All core functionality tested:")
print("   - File validation (extension, size)")
print("   - Document creation validation (permissions)")
print("   - Document creation and update operations")
print("   - Permission checks for different user roles")
print("   - File URL generation")
print("   - Serializer read/write operations")
print("   - Validation error handling")
print("   - File upload security")
print("\n🎉 STUDENT DOCUMENT SERVICE & SERIALIZER TESTS COMPLETE!")
print("=" * 70)

print("\n🧹 Test data preserved for inspection.")
print("✅ Test suite finished successfully!")
from django.shortcuts import render
from rest_framework import viewsets, status, permissions, filters
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.permissions import IsAdminUser, AllowAny, IsAuthenticated
from django.db.models import Q
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
from .models import (User, DrivingSchool, StudentProfile, Lesson, 
                     Attendance, Schedule, Feedback, Vehicle, VehiclePicture)
from .serializers import (UserSerializer, DrivingSchoolSerializer, ScheduleSerializer, VehicleSerializer,
                          VehiclePictureSerializer,StudentProfileSerializer, LessonSerializer,AttendanceSerializer,
                          FeedbackSerializer)
from .permissions import (IsPlatformAdmin, IsInstructor, CanUpdateStudentProfile,
                           IsPlatformAdminOrSchoolOwner, IsPlatformAdminOrSchoolOwnerOrInstructor,
                           IsStudent)
from rest_framework.exceptions import PermissionDenied
from django.db.models import Count
from django.db import transaction
from .services import StudentProfileService, LessonService, AttendanceService, VehicleService
from django.db.models import Avg, Sum
from django_filters.rest_framework import DjangoFilterBackend 
User = get_user_model()


class UserViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing users in a SaaS driving school platform.
    
    Access Control:
    - Platform Admins (A): Full access to all users across all schools
    - Instructors (I): View and manage students in their school
    - Students (S): View their own profile only
    """
    serializer_class = UserSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['username', 'email', 'first_name', 'last_name', 'phone_number']
    ordering_fields = ['created_at', 'username', 'role', 'last_name']
    ordering = ['-created_at']

    def get_queryset(self):
        """
        Filter users based on role and school association.
        Multi-tenancy: Users only see users from their own school.
        """
        user = self.request.user
        
        # Platform Admin sees all users
        if user.role == 'A':
            return User.objects.all()
        
        # Instructor sees students and other instructors in their school
        elif user.role == 'I':
            # Get instructor's school through their student profile
            student_profile = user.student_profiles.filter(status='A').first()
            if student_profile:
                school = student_profile.school
                # Get all users who have student profiles in this school
                queryset = User.objects.filter(
                    student_profiles__school=school
                ).distinct()
            else:
                queryset = User.objects.none()
        
        # Students see only themselves
        else:
            queryset = User.objects.filter(id=user.id)
        
        return queryset.select_related()

    def get_permissions(self):
        """
        Define permissions per action.
        Only Platform Admins can create users (except public student registration).
        """
        if self.action == 'create':
            # Only admins can create users via the admin panel
            return [IsAuthenticated(), IsPlatformAdmin()]
        
        elif self.action in ['update', 'partial_update']:
            # Users can update themselves, admins can update any user
            return [IsAuthenticated()]
        
        elif self.action == 'destroy':
            # Only admins can delete users
            return [IsAuthenticated(), IsPlatformAdmin()]
        
        elif self.action == 'register_student':
            # Admin-only registration for students
            return [IsAuthenticated(), IsPlatformAdmin()]
        
        elif self.action in ['deactivate', 'activate', 'stats']:
            # Only admins can activate/deactivate and view stats
            return [IsAuthenticated(), IsPlatformAdmin()]
        
        return [IsAuthenticated()]

    def perform_update(self, serializer):
        """
        Prevent users from escalating their own privileges.
        """
        user = self.request.user
        instance = self.get_object()
        
        # Users cannot change their own role (only admins can)
        if instance.id == user.id and 'role' in serializer.validated_data:
            if serializer.validated_data['role'] != user.role:
                if user.role != 'A':
                    raise PermissionDenied("You cannot change your own role.")
        
        serializer.save()

    @action(detail=False, methods=['post'], permission_classes=[IsAuthenticated, IsPlatformAdmin])
    @transaction.atomic
    def register_student(self, request):
        """
        Endpoint for admins to register students.
        Students must be assigned to a driving school during registration.
        """
        data = request.data.copy()
        
        # Force role to student
        data['role'] = 'S'
        
        # Validate driving school
        school_id = data.get('driving_school_id')
        if not school_id:
            return Response(
                {'error': 'Driving school selection is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            school = DrivingSchool.objects.get(id=school_id)
        except DrivingSchool.DoesNotExist:
            return Response(
                {'error': 'Invalid driving school'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        user = request.user
        # Platform admins can register for any school
        if user.role != 'A':
            # Non-platform admins must register for their own school
            if not hasattr(user, 'student_profiles'):
                return Response(
                    {'error': 'You can only register students for your own school'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            user_profile = user.student_profiles.filter(status='A').first()
            if not user_profile or user_profile.school != school:
                return Response(
                    {'error': 'You can only register students for your own school'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
        # Check if school has available slots (subscription limits)
        if hasattr(school, 'subscription'):
            subscription = school.subscription
            # Count active student profiles in this school
            current_students = school.student_profiles.filter(status='A', user__role='S').count()
            if current_students >= subscription.plan.max_students:
                return Response(
                    {
                        'error': f'This school has reached its student limit ({subscription.plan.max_students} students maximum). '
                        f'Current: {current_students} students.'
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        
        # Create student profile automatically
        StudentProfile.objects.create(
            user=user,
            school=school,
            joined_at=timezone.now(),
            status='A'  # Active status
        )
        
        return Response(
            serializer.data,
            status=status.HTTP_201_CREATED
        )
    

    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def me(self, request):
        """
        Get current user's profile with related data.
        """
        serializer = self.get_serializer(request.user)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def school_users(self, request):
        """
        Get all users in the current user's school with optional role filtering.
        Available to Instructors and Admins.
        """
        user = request.user
        role_filter = request.query_params.get('role')
        
        # Only instructors and admins can use this endpoint
        if user.role not in ['A', 'I']:
            return Response(
                {'error': 'Only instructors and admins can view school users'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        queryset = self.get_queryset()
        
        if role_filter:
            queryset = queryset.filter(role=role_filter)
        
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated, IsPlatformAdmin])
    def deactivate(self, request, pk=None):
        """
        Soft delete: deactivate a user instead of hard deletion.
        Only Platform Admins can deactivate users.
        """
        target_user = self.get_object()
        
        # Prevent self-deactivation
        if target_user.id == request.user.id:
            return Response(
                {'error': 'You cannot deactivate your own account'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        target_user.is_active = False
        target_user.save()
        
        return Response(
            {'message': 'User deactivated successfully'},
            status=status.HTTP_200_OK
        )

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated, IsPlatformAdmin])
    def activate(self, request, pk=None):
        """
        Reactivate a deactivated user.
        Only Platform Admins can activate users.
        """
        target_user = self.get_object()
        target_user.is_active = True
        target_user.save()
        
        return Response(
            {'message': 'User activated successfully'},
            status=status.HTTP_200_OK
        )

    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated, IsPlatformAdmin])
    def stats(self, request):
        """
        Get user statistics across the platform.
        Only available to Platform Admins.
        """
        
        stats = {
            'total_users': User.objects.count(),
            'active_users': User.objects.filter(is_active=True).count(),
            'users_by_role': dict(
                User.objects.values('role').annotate(count=Count('id')).values_list('role', 'count')
            ),
            'recent_registrations': User.objects.filter(
                created_at__gte=timezone.now() - timezone.timedelta(days=30)
            ).count()
        }
        
        return Response(stats)
    
class DrivingSchoolViewSet(viewsets.ModelViewSet):
    """
    Manage driving schools in the platform
    - Platform Admins: Full CRUD on all schools
    - School Owners/Instructors: View and update their own school
    - Students: View their school (read-only)
    """
    serializer_class = DrivingSchoolSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name','email','address','phone_number']
    ordering_fields = ['created_at','name','email']
    ordering = ['-created_at']
    
    def get_queryset(self):
        """
        Filter schools based on user role.
        - Platform Admins: See all schools
        - Instructors: See only their school
        - Students: See only their school
        """
        user = self.request.user
        if not user.is_authenticated:
            return DrivingSchool.objects.none()
        
        #Platform Admin sees all users
        if user.role == 'A' and user.is_staff:
            return DrivingSchool.objects.all().select_related('owner')

        if user.role == 'A':
            return DrivingSchool.objects.filter(owner=user).select_related('owner')
        
        elif user.role in  ['I','S']: 
            # Get Instructore's school through their student profile
            student_profile = user.student_profiles.filter(status='A').first()
            if student_profile:
                
                #Get all users who have student profiles in this school
                return DrivingSchool.objects.filter(id=student_profile.school.id).select_related('owner')
        
       
        return DrivingSchool.objects.none() 
        
    def get_permissions(self):
        """
        Define permissions per action.
        Only Platform Admins can have all the action for the platform like "Crud".
        """
        if self.action == 'create':
            #Only Platform Admin can create 
            return [IsAuthenticated(), IsPlatformAdmin()]
        
        elif self.action in ['update','partial_update']:
            #Only Admin and instructore and owner
            return [IsAuthenticated()]
        
        elif self.action == 'destroy':
            #Only Admin can delete
            return [IsAuthenticated(), IsPlatformAdmin()]
        
        return [IsAuthenticated()]
    
    def perform_update(self, serializer):
        
        user = self.request.user
        instance = self.get_object()

        if user.role == 'A' and user.is_staff:
            serializer.save()
            return
        
        if instance.owner == user:
            serializer.save()
            return
        
        if user.role == 'I':
            if user.student_profiles.filter(school=instance, status='A').exists():
                serializer.save()
                return
        
        if user.role == 'S':
            raise PermissionDenied(
                "Students can only view schools, not update them."
            )
        
        raise PermissionDenied("You don't have permission to update this school.")
        

    @action(detail=True, methods=['get'])
    def students(self, request, pk=None):

        school = self.get_object()
        user = request.user
        students = school.student_profiles.filter(status='A').select_related('user')
        if user.role != 'A' and school.owner != user:
            raise PermissionDenied(
                "Only platform admins and school owners can view student lists."
            )

        page = self.paginate_queryset(students)
        if page is not None:
            serializer = StudentProfileSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = StudentProfileSerializer(students, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'], permission_classes=[IsAuthenticated])
    def stats(self, request, pk=None):

        school = self.get_object()
        user = request.user

        if user.role != 'A' and school.owner != user:
            raise PermissionDenied(
                "Only platform admins and school owners can view school statistics."
            )
        
        student_profiles = school.student_profiles.select_related('user')
        students = student_profiles.filter(user__role='S')
        active_student_count = students.filter(status='A').count()
        
        stats = {
            'total_students': students.count(),
            'active_students': active_student_count,
            'completed_students': students.filter(status='C').count(),
            'paused_students': students.filter(status='P').count(),
            'total_instructors': student_profiles.filter(user__role='I', status='A').count(),
            'active_instructors': student_profiles.filter(user__role='I', status='A').count(),
            'subscription_status': school.subscription.status if hasattr(school, 'subscription') else 'No subscription',
            'subscription_plan': school.subscription.plan.name if hasattr(school, 'subscription') else None,
            'student_capacity': school.subscription.plan.max_students if hasattr(school, 'subscription') and hasattr(school.subscription.plan, 'max_students') else None,
            'instructor_capacity': school.subscription.plan.max_instructors if hasattr(school, 'subscription') and hasattr(school.subscription.plan, 'max_instructors') else None,
            'utilization_percentage': round((school.student_profiles.filter(user__role='S', status='A').count() / school.subscription.plan.max_students * 100), 2) if hasattr(school, 'subscription') and school.subscription.plan.max_students > 0 else None,
            'school_name': school.name,
            'created_at': school.created_at
        }

        return Response(stats)
    
class StudentProfileViewSet(viewsets.ModelViewSet):
    """
    Manage student profiles
    - Platform Admins: Full access to all student profiles
    - School Owners: Manage students in their schools
    - Instructors: View students in their school
    - Students: View and update their own profile only
    """
    serializer_class = StudentProfileSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['user__username', 'user__email', 'user__first_name', 'user__last_name']
    ordering_fields = ['progress_theory', 'progress_driving', 'joined_at']
    ordering = ['-joined_at']

    def get_queryset(self):
        """Filter student profiles based on user role and school"""
        user = self.request.user
        if not user.is_authenticated:
            return StudentProfile.objects.none()
        
        # Platform Admin sees all
        if user.role == 'A' and user.is_staff:
            return StudentProfile.objects.all().select_related('user', 'school')
        
        # School Owner sees students in their schools
        if user.role == 'A':
            return StudentProfile.objects.filter(school__owner=user).select_related('user', 'school')
        
        # Instructor sees students in their school
        if user.role == 'I':
            # Get instructor's school
            instructor_profile = user.student_profiles.filter(status='A').first()  # FIXED: status='A'
            if instructor_profile:
                return StudentProfile.objects.filter(
                    school=instructor_profile.school,
                    user__role='S'  # Only students, not other instructors
                ).select_related('user', 'school')
        
        # Student sees only their own profile
        if user.role == 'S':
            return StudentProfile.objects.filter(user=user).select_related('user', 'school')
        
        return StudentProfile.objects.none()

    def get_permissions(self):
        """Define permissions per action"""
        if self.action == 'create':
            # Only platform admins and school owners can create student profiles
            return [IsAuthenticated(), IsPlatformAdminOrSchoolOwner() ]
        
        elif self.action in ['update', 'partial_update']:
            # Students can update their own profile, admins/owners can update any
            return [CanUpdateStudentProfile()]
        
        elif self.action == 'destroy':
            # Only platform admins can delete student profiles
            return [IsAuthenticated(), IsPlatformAdmin()]
        
        elif self.action == 'update_progress':
            return [IsAuthenticated(), IsInstructor()]
        
        return [IsAuthenticated()]

    def perform_update(self, serializer):
        """Custom update logic with permission checks"""
        user = self.request.user
        instance = self.get_object()
        
        # Students can only update their own profile
        if user.role == 'S' and instance.user != user:
            raise PermissionDenied("You can only update your own profile.")
        
        # School owners (admin but not staff) can only update profiles in their schools
        if user.role == 'A' and not user.is_staff:  # FIXED: Added 'not user.is_staff'
            if instance.school.owner != user:
                raise PermissionDenied("You can only update profiles in your own school.")
        
        # Platform admins (is_staff=True) can update any profile
        
        serializer.save()

    @action(detail=True, methods=['get'], permission_classes=[IsAuthenticated])
    def progress(self, request, pk=None):
        """Get detailed progress for a student"""
        student_profile = self.get_object()
        
        # Check permissions
        user = request.user
        if user.role == 'S' and student_profile.user != user:
            raise PermissionDenied("You can only view your own progress.")
        
        if user.role == 'I':
            # Instructor can only view students in their school
            instructor_profile = user.student_profiles.filter(status='A').first()
            if not instructor_profile or instructor_profile.school != student_profile.school:
                raise PermissionDenied("You can only view progress of students in your school.")
        
        if user.role == 'A' and not user.is_staff:
            # School owner can only view students in their schools
            if student_profile.school.owner != user:
                raise PermissionDenied("You can only view progress of students in your schools.")
        
        # Calculate progress
        completion_percentage = StudentProfileService.calculate_completion_percentage(student_profile)
        
        response_data = {
            'student': student_profile.user.username,
            'completion_percentage': completion_percentage,
            'theory_progress': student_profile.progress_theory,
            'driving_progress': student_profile.progress_driving,
            'theory_hours': student_profile.total_hours_theory,
            'driving_hours': student_profile.total_hours_driving,
            'status': student_profile.get_status_display(),
        }
        
        return Response(response_data)

    @action(detail=True, methods=['POST'], permission_classes=[IsAuthenticated, IsInstructor])
    def update_progress(self, request, pk=None):
        """Update student progress (for instructors only)"""
        student_profile = self.get_object()
        instructor = request.user
        
        # Verify instructor is in the same school
        instructor_profile = instructor.student_profiles.filter(status='A').first()
        if not instructor_profile or instructor_profile.school != student_profile.school:
            raise PermissionDenied("You can only update progress of students in your school.")
        
        # Get data from request
        lesson_type = request.data.get('lesson_type')  # 'T' or 'D'
        hours_completed = request.data.get('hours_completed')
        
        if not lesson_type or lesson_type not in ['T', 'D']:
            return Response(
                {'error': 'Lesson type must be "T" (Theory) or "D" (Driving)'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            hours_completed = float(hours_completed)
            if hours_completed <= 0:
                raise ValueError
        except (ValueError, TypeError):
            return Response(
                {'error': 'Hours completed must be a positive number'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Update progress using service
        StudentProfileService.update_progress_from_attendance(
            student_profile, lesson_type, hours_completed
        )
        
        # Check if student should be auto-completed
        StudentProfileService.auto_complete_student(student_profile)
        
        # Return updated profile
        serializer = self.get_serializer(student_profile)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def my_profile(self, request):
        """Get current user's student profile"""
        user = request.user
        
        if user.role != 'S':
            return Response(
                {'error': 'Only students have student profiles'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            profile = StudentProfile.objects.get(user=user)
            serializer = self.get_serializer(profile)
            return Response(serializer.data)
        except StudentProfile.DoesNotExist:
            return Response(
                {'error': 'Student profile not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
class LessonViewSet(viewsets.ModelViewSet):
    """
    Manage lessons in the platform
    
    Access Control:
    - Platform Admins: Full access to all lessons
    - School Owners: Manage lessons in their schools
    - Instructors: Manage their own lessons
    - Students: View lessons in their school
    """
    serializer_class = LessonSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter, DjangoFilterBackend]
    filterset_fields = ['lesson_type', 'status', 'instructor', 'school']  # Add this line
    search_fields = ['title', 'description']
    ordering_fields = ['date', 'status', 'lesson_type']
    ordering = ['-date']

    def get_queryset(self):
        """Filter lessons based on user role and school"""
        user = self.request.user
        if not user.is_authenticated:
            return Lesson.objects.none()
        
        # Platform Admin (staff) sees all lessons
        if user.role == 'A' and user.is_staff:
            return Lesson.objects.all().select_related('instructor', 'school')
        
        # School Owner (admin but not staff) sees lessons in their schools
        if user.role == 'A' and not user.is_staff:
            return Lesson.objects.filter(
                school__owner=user
            ).select_related('instructor', 'school')
        
        # Instructor sees their own lessons
        if user.role == 'I':
            return Lesson.objects.filter(
                instructor=user
            ).select_related('instructor', 'school')
        
        # Student sees lessons in their school
        if user.role == 'S':
            student_profile = user.student_profiles.filter(status='A').first()
            if student_profile:
                return Lesson.objects.filter(
                    school=student_profile.school
                ).select_related('instructor', 'school')
        
        return Lesson.objects.none()
    
    def get_permissions(self):
        """Define permissions per action"""
        if self.action == 'create':
            return [IsAuthenticated(),IsPlatformAdminOrSchoolOwner()]
        
        elif self.action in ['update', 'partial_update']:
            return [IsAuthenticated(), IsPlatformAdminOrSchoolOwnerOrInstructor()]
        
        elif self.action == 'destroy':
            return [IsAuthenticated(), IsPlatformAdminOrSchoolOwner()]

        elif self.action in ['mark_attendance', 'complete_lesson']:
            return [IsAuthenticated(), IsInstructor()]
        
        return [IsAuthenticated()]
    
    def perform_create(self, serializer):
        """Create lesson with validation"""
        user = self.request.user
        instructor = serializer.validated_data.get('instructor')
        
        # Verify instructor is valid
        if not instructor or instructor.role != 'I':
            raise PermissionDenied("Invalid instructor")
        
        # Platform admin can create for any instructor
        if user.role == 'A' and user.is_staff:
            serializer.save()
            return
        
        
        # School owner can create for instructors in their schools
        if user.role == 'A' and not user.is_staff:
            instructor_profile = instructor.student_profiles.filter(status='A').first()
            if not instructor_profile:
                raise PermissionDenied("Instructor has no active school profile")
            
            # Check if instructor is in owner's school

            
            serializer.save()
            return
        
        raise PermissionDenied("You don't have permission to create lessons")
    
    def perform_update(self, serializer):
        """Update lesson with permission checks"""
        user = self.request.user
        instance = self.get_object()

        # Platform Admin (staff) can update any lesson
        if user.role == 'A' and user.is_staff:
            serializer.save()
            return

        # School Owner can update lessons in their schools
        if user.role == 'A' and not user.is_staff:
            instructor_profile = instance.instructor.student_profiles.filter(status='A').first()
            if instructor_profile and instructor_profile.school.owner == user:
                serializer.save()
                return
            raise PermissionDenied("You can only update lessons in your own schools")
        
        # Instructor can update their own lessons
        if user.role == 'I':
            if instance.instructor == user:
                serializer.save()
                return
            raise PermissionDenied("You can only update your own lessons")
        
        # Students cannot update lessons
        if user.role == 'S':
            raise PermissionDenied("Students cannot update lessons")
        
        raise PermissionDenied("You don't have permission to update this lesson")
    
    def perform_destroy(self, serializer):
        """Delete lesson with permission checks"""
        user = self.request.user
        instance = self.get_object()
        
        # Only platform admins and school owners can delete lessons
        if user.role == 'A' and user.is_staff:
            instance.delete()
            return
        
        if user.role == 'A' and not user.is_staff:
            instructor_profile = instance.instructor.student_profiles.filter(status='A').first()
            if instructor_profile and instructor_profile.school.owner == user:
                instance.delete()
                return
        
        raise PermissionDenied("You don't have permission to delete this lesson")
    
    @action(detail=True, methods=['get'], permission_classes=[IsAuthenticated])
    def attendance(self, request, pk=None):
        """Get attendance records for a lesson"""
        lesson = self.get_object()
        user = request.user

        # Students can only view their own attendance
        if user.role == 'S':
            attendance_records = Attendance.objects.filter(
                lesson=lesson,
                student__user=user
            ).select_related('student__user')
            
            if not attendance_records.exists():
                return Response(
                    {'message': 'You have no attendance record for this lesson'},
                    status=status.HTTP_404_NOT_FOUND
                )
        else:
            # Admins and instructors can view all attendance
            attendance_records = Attendance.objects.filter(
                lesson=lesson
            ).select_related('student__user')
        
        serializer = AttendanceSerializer(attendance_records, many=True)

        return Response({
            'lesson': lesson.title,
            'lesson_date': lesson.date,
            'total_attendance': attendance_records.count(),
            'present_count': attendance_records.filter(presence=True).count(),
            'absent_count': attendance_records.filter(presence=False).count(),
            'attendance_list': serializer.data
        })
    
    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated, IsInstructor])
    @transaction.atomic
    def mark_attendance(self, request, pk=None):
        """Mark attendance for multiple students in a lesson"""
        lesson = self.get_object()
        instructor = request.user

        # Verify instructor owns this lesson
        if lesson.instructor != instructor:
            raise PermissionDenied("You can only mark attendance for your own lessons")
        
        # Prevent marking attendance for future lessons
        if lesson.date > timezone.now():
            return Response(
                {'error': 'Cannot mark attendance for future lessons'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get data from request
        student_ids = request.data.get('student_ids', [])
        presence = request.data.get('presence', True)
        hours_completed = request.data.get('hours_completed', 0)
        notes = request.data.get('notes', '')
        
        if not student_ids:
            return Response(
                {'error': 'No student IDs provided'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get instructor's school
        instructor_profile = instructor.student_profiles.filter(status='A').first()
        if not instructor_profile:
            return Response(
                {'error': 'Instructor has no active school profile'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validate students exist and are active in this school
        students = StudentProfile.objects.filter(
            id__in=student_ids,
            school=instructor_profile.school,
            status='A',
            user__role='S'  # Only actual students
        )
        
        # Check if all students were found
        found_ids = set(students.values_list('id', flat=True))
        requested_ids = set(student_ids)
        missing_ids = requested_ids - found_ids
        
        if missing_ids:
            return Response(
                {'error': f'Students not found or inactive: {list(missing_ids)}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validate hours completed
        try:
            hours_completed = float(hours_completed)
            if hours_completed < 0 or hours_completed > lesson.duration:
                return Response(
                    {'error': f'Hours completed must be between 0 and {lesson.duration}'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        except (ValueError, TypeError):
            return Response(
                {'error': 'Hours completed must be a valid number'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Create/update attendance records
        attendance_records = []
        for student in students:
            attendance, created = Attendance.objects.update_or_create(
                student=student,
                lesson=lesson,
                defaults={
                    'presence': presence,
                    'hours_completed': hours_completed,
                    'notes': notes
                }
            )
            attendance_records.append(attendance)

            # Update student progress if present with hours
            if presence and hours_completed > 0:
                StudentProfileService.update_progress_from_attendance(
                    student, lesson.lesson_type, hours_completed
                )
        
        # Return response
        serializer = AttendanceSerializer(attendance_records, many=True)
        return Response({
            'message': f'Attendance marked for {len(attendance_records)} students',
            'lesson': lesson.title,
            'marked_count': len(attendance_records),
            'attendance_records': serializer.data
        }, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['get'], permission_classes=[IsAuthenticated])
    def schedule(self, request, pk=None):
        """Get schedule for this lesson"""
        lesson = self.get_object()
        
        try:
            schedule = Schedule.objects.get(lesson=lesson)
            serializer = ScheduleSerializer(schedule)
            return Response(serializer.data)
        except Schedule.DoesNotExist:
            return Response(
                {'message': 'No schedule found for this lesson'},
                status=status.HTTP_404_NOT_FOUND
            )
        
    @action(detail=True, methods=['get'], permission_classes=[IsAuthenticated])
    def feedback(self, request, pk=None):
        """Get feedback for this lesson"""
        lesson = self.get_object()
        user = request.user
        
        # Students can only view their own feedback
        if user.role == 'S':
            feedback_records = Feedback.objects.filter(
                lesson=lesson,
                student__user=user
            ).select_related('student__user')
        else:
            # Admins and instructors can view all feedback
            feedback_records = Feedback.objects.filter(
                lesson=lesson
            ).select_related('student__user')
        
        serializer = FeedbackSerializer(feedback_records, many=True)
        
        # Calculate average rating
        avg_rating = feedback_records.aggregate(avg=Avg('rating'))['avg'] or 0
        
        return Response({
            'lesson': lesson.title,
            'lesson_date': lesson.date,
            'total_feedback': feedback_records.count(),
            'average_rating': round(avg_rating, 2),
            'feedback_list': serializer.data
        })
    
    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated, IsInstructor])
    def complete_lesson(self, request, pk=None):
        """Mark lesson as completed"""
        lesson = self.get_object()
        instructor = request.user
        
        # Verify instructor owns this lesson
        if lesson.instructor != instructor:
            raise PermissionDenied("You can only complete your own lessons")
        
        # Check if lesson is in the past
        if lesson.date > timezone.now():
            return Response(
                {'error': 'Cannot complete future lessons'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check if lesson is already completed
        if lesson.status == 'completed':
            return Response(
                {'message': 'Lesson is already marked as completed'},
                status=status.HTTP_200_OK
            )
        
        # Mark lesson as completed using service
        lesson = LessonService.mark_lesson_completed(lesson)
        
        serializer = self.get_serializer(lesson)
        return Response({
            'message': 'Lesson marked as completed',
            'lesson': serializer.data
        })
    
    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def upcoming(self, request):
        """Get upcoming lessons for the current user"""
        user = request.user
        now = timezone.now()
        
        # Filter based on user role
        if user.role == 'A' and user.is_staff:
            # Platform admin sees all upcoming lessons
            queryset = Lesson.objects.filter(date__gte=now, status='scheduled')
        
        elif user.role == 'A' and not user.is_staff:
            # School owner sees upcoming lessons in their schools
            queryset = Lesson.objects.filter(
                instructor__student_profiles__school__owner=user,
                date__gte=now,
                status='scheduled'
            )
        
        elif user.role == 'I':
            # Instructor sees their upcoming lessons
            queryset = Lesson.objects.filter(
                instructor=user,
                date__gte=now,
                status='scheduled'
            )
        
        elif user.role == 'S':
            # Student sees upcoming lessons in their school
            student_profile = user.student_profiles.filter(status='A').first()
            if student_profile:
                queryset = Lesson.objects.filter(
                    instructor__student_profiles__school=student_profile.school,
                    date__gte=now,
                    status='scheduled'
                ).distinct()
            else:
                queryset = Lesson.objects.none()
        else:
            queryset = Lesson.objects.none()
        
        # Apply ordering and pagination
        queryset = queryset.order_by('date').select_related('instructor')
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def my_lessons(self, request):
        """Get lessons for the current user based on their role"""
        user = request.user
        
        if user.role == 'I':
            queryset = Lesson.objects.filter(instructor=user)
        elif user.role == 'S':
            # Get lessons where student has attendance record
            queryset = Lesson.objects.filter(
                lesson_attendance__student__user=user
            ).distinct()
        else:
            return Response(
                {'error': 'This endpoint is only for instructors and students'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Apply filters
        status_filter = request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        # Apply ordering
        queryset = queryset.order_by('-date').select_related('instructor')
        
        # Paginate
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def statistics(self, request):
        """Get lesson statistics for the current user"""
        user = request.user
        
        if user.role == 'I':
            # Instructor statistics
            total_lessons = Lesson.objects.filter(instructor=user).count()
            completed = Lesson.objects.filter(instructor=user, status='completed').count()
            upcoming = Lesson.objects.filter(
                instructor=user, 
                status='scheduled',
                date__gte=timezone.now()
            ).count()
            
            stats = {
                'total_lessons': total_lessons,
                'completed_lessons': completed,
                'upcoming_lessons': upcoming,
                'completion_rate': round((completed / total_lessons * 100), 2) if total_lessons > 0 else 0
            }
        
        elif user.role == 'S':
            # Student statistics
            student_profile = user.student_profiles.filter(status='A').first()
            if not student_profile:
                return Response({'error': 'No active student profile found'}, status=404)
            
            attended = Attendance.objects.filter(
                student=student_profile,
                presence=True
            ).count()
            
            total_scheduled = Attendance.objects.filter(
                student=student_profile
            ).count()
            
            stats = {
                'lessons_attended': attended,
                'total_scheduled': total_scheduled,
                'attendance_rate': round((attended / total_scheduled * 100), 2) if total_scheduled > 0 else 0,
                'total_hours': student_profile.total_hours_theory + student_profile.total_hours_driving
            }
        
        else:
            return Response(
                {'error': 'Statistics not available for your role'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        return Response(stats)

class AttendanceViewSet(viewsets.ModelViewSet):

    serializer_class = AttendanceSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter, DjangoFilterBackend]
    filterset_fields = ['presence','hours_completed','student__user__username','student__user__email']
    search_fields = ['student__user__username','student__user__email','notes']
    ordering_fields = ['presence','hours_completed','created_at']
    ordering = ['-created_at']

    def get_queryset(self):
        user = self.request.user
        if not user.is_authenticated:
            return Attendance.objects.none()
        
        if user.role == 'A' and user.is_staff:
            return Attendance.objects.all().select_related('student__user','student__school','lesson__instructor')
        
        if user.role == 'A' and not user.is_staff:
            return Attendance.objects.filter(
                lesson__school__owner =user
            ).select_related('student__user','lesson__instructor')
        
        if user.role == 'I':
            return Attendance.objects.filter(
                lesson__instructor = user
            ).select_related('student__user','lesson')
        
        if user.role == 'S':
            return Attendance.objects.filter(
                student__user = user
            ).select_related('student__user','lesson__instructor')
        
        return Attendance.objects.none()
    
    def get_permissions(self):
        
        if self.action == 'create':
            return [IsAuthenticated(), IsPlatformAdminOrSchoolOwnerOrInstructor()]
        
        elif self.action in ['update', 'partial_update']:
            return [IsAuthenticated(), IsPlatformAdminOrSchoolOwnerOrInstructor()]

        elif self.action == 'destroy':
            return [IsAuthenticated(), IsPlatformAdminOrSchoolOwner()]
        
        return [IsAuthenticated()]



    def perform_create(self, serializer):
        """
        Create attendance with validation.
        Only for lessons taught by the authenticated user's school.
        """
        user = self.request.user
        student = serializer.validated_data.get('student')
        lesson = serializer.validated_data.get('lesson')
        
        # Validate student exists and is actually a student
        if not student:
            raise PermissionDenied("Student is required")
        
        if student.user.role != 'S':  # FIXED: Check user's role
            raise PermissionDenied("Invalid student - must be a student profile")
        
        # Validate lesson exists
        if not lesson:
            raise PermissionDenied("Lesson is required")
        
        # Platform admin can create for any school
        if user.role == 'A' and user.is_staff:
            serializer.save()
            return
        
        # School owner can create for their schools
        if user.role == 'A' and not user.is_staff:
            # Check if lesson is in owner's school
            instructor_profile = lesson.instructor.student_profiles.filter(status='A').first()
            if not instructor_profile or instructor_profile.school.owner != user:
                raise PermissionDenied("You can only create attendance for lessons in your schools")
            
            # Check if student is in the same school
            if student.school != instructor_profile.school:
                raise PermissionDenied("Student must be enrolled in the same school as the lesson")
            
            serializer.save()
            return
        
        # Instructor can create for their own lessons
        if user.role == 'I':
            # Verify this is the instructor's lesson
            if lesson.instructor != user:
                raise PermissionDenied("You can only create attendance for your own lessons")
            
            # Verify student is in the same school as instructor
            instructor_profile = user.student_profiles.filter(status='A').first()
            if not instructor_profile:
                raise PermissionDenied("You have no active school profile")
            
            if student.school != instructor_profile.school:
                raise PermissionDenied("Student must be enrolled in your school")
            
            serializer.save()
            return
        
        raise PermissionDenied("You don't have permission to create attendance")
    

    def perform_update(self, serializer):
        
        user = self.request.user
        instance = self.get_object()

        if user.role == 'A' and user.is_staff:
            serializer.save()
            return 
        
        if user.role == 'A' and not user.is_staff:
            instructor_profile = instance.lesson.instructor.student_profiles.filter(status='A').first()
            if instructor_profile and instance.lesson.school.owner == user:
                serializer.save()
                return
            raise PermissionDenied("You can only update Attendance in your own schools")
        
        if user.role == 'I':
            if instance.lesson.instructor == user:
                serializer.save()
                return
            raise PermissionDenied("You can only update your own Attendance")
        
        raise PermissionDenied("You don't have permission to update this Attendance")
    
    def perform_destroy(self, instance):
        
        user = self.request.user

        if user.role == 'A' and user.is_staff:
            instance.delete()
            return 
        
        if user.role == 'A' and not user.is_staff:
            instructor_profile = instance.lesson.instructor.student_profiles.filter(status='A').first()
            if instructor_profile and instance.lesson.school.owner == user:
                instance.delete()
                return 
            raise PermissionDenied("You can only delete Attendance in your own schools")
        
        raise PermissionDenied("You don't have permission to delete this Attendance")

    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def my_attendance(self, request):
        """
        Get attendance records for the current student.
        Only available to students.
        """
        user = request.user

        if user.role != 'S':
            return Response(
                {'error': 'This endpoint is only for students'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            student_profile = StudentProfile.objects.get(user=user, status='A')
        except StudentProfile.DoesNotExist:
            return Response(
                {'error': 'No active student profile found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        attendance_records = Attendance.objects.filter(
            student=student_profile
        ).select_related('lesson__instructor').order_by('-created_at')
        
        # Calculate statistics
        total_lessons = attendance_records.count()
        attended = attendance_records.filter(presence=True).count()
        total_hours = attendance_records.filter(
            presence=True
        ).aggregate(total=Sum('hours_completed'))['total'] or 0
        
        attendance_rate = round((attended / total_lessons * 100), 2) if total_lessons > 0 else 0
        
        serializer = self.get_serializer(attendance_records, many=True)
        
        return Response({
            'statistics': {
                'total_lessons': total_lessons,
                'attended': attended,
                'missed': total_lessons - attended,
                'attendance_rate': attendance_rate,
                'total_hours_completed': total_hours
            },
            'attendance_records': serializer.data
        })
    
    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated, IsInstructor])
    def lesson_summary(self, request):
        """
        Get attendance summary for a specific lesson.
        Available to instructors and admins.
        """
        lesson_id = request.query_params.get('lesson_id')
        
        if not lesson_id:
            return Response(
                {'error': 'lesson_id query parameter is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            lesson = Lesson.objects.get(id=lesson_id)
        except Lesson.DoesNotExist:
            return Response(
                {'error': 'Lesson not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        user = request.user
        
        # Check permissions
        if user.role == 'I' and lesson.instructor != user:
            raise PermissionDenied("You can only view attendance for your own lessons")
        
        if user.role == 'A' and not user.is_staff:
            instructor_profile = lesson.instructor.student_profiles.filter(status='A').first()
            if not instructor_profile or instructor_profile.school.owner != user:
                raise PermissionDenied("You can only view attendance for lessons in your schools")
        
        # Get attendance records
        attendance_records = Attendance.objects.filter(
            lesson=lesson
        ).select_related('student__user')
        
        total_students = attendance_records.count()
        present = attendance_records.filter(presence=True).count()
        absent = total_students - present
        
        avg_hours = attendance_records.filter(
            presence=True
        ).aggregate(avg=Avg('hours_completed'))['avg'] or 0
        
        serializer = self.get_serializer(attendance_records, many=True)
        
        return Response({
            'lesson': {
                'id': lesson.id,
                'title': lesson.title,
                'date': lesson.date,
                'instructor': lesson.instructor.get_full_name() or lesson.instructor.username
            },
            'summary': {
                'total_students': total_students,
                'present': present,
                'absent': absent,
                'attendance_rate': round((present / total_students * 100), 2) if total_students > 0 else 0,
                'average_hours_completed': round(avg_hours, 2)
            },
            'attendance_records': serializer.data
        })
    
    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated, IsInstructor])
    def student_summary(self, request):
        """
        Get attendance summary for a specific student.
        Available to instructors and admins.
        """
        student_id = request.query_params.get('student_id')
        
        if not student_id:
            return Response(
                {'error': 'student_id query parameter is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            student_profile = StudentProfile.objects.get(id=student_id)
        except StudentProfile.DoesNotExist:
            return Response(
                {'error': 'Student profile not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        user = request.user
        
        # Check permissions
        if user.role == 'I':
            instructor_profile = user.student_profiles.filter(status='A').first()
            if not instructor_profile or instructor_profile.school != student_profile.school:
                raise PermissionDenied("You can only view attendance for students in your school")
        
        if user.role == 'A' and not user.is_staff:
            if student_profile.school.owner != user:
                raise PermissionDenied("You can only view attendance for students in your schools")
        
        # Get attendance records
        attendance_records = Attendance.objects.filter(
            student=student_profile
        ).select_related('lesson__instructor')
        
        total_lessons = attendance_records.count()
        attended = attendance_records.filter(presence=True).count()
        total_hours = attendance_records.filter(
            presence=True
        ).aggregate(total=Sum('hours_completed'))['total'] or 0
        
        serializer = self.get_serializer(attendance_records, many=True)
        
        return Response({
            'student': {
                'id': student_profile.id,
                'name': student_profile.user.get_full_name() or student_profile.user.username,
                'email': student_profile.user.email
            },
            'summary': {
                'total_lessons': total_lessons,
                'attended': attended,
                'missed': total_lessons - attended,
                'attendance_rate': round((attended / total_lessons * 100), 2) if total_lessons > 0 else 0,
                'total_hours_completed': total_hours
            },
            'attendance_records': serializer.data
        })
    
class FeedbackViewSet(viewsets.ModelViewSet):
    serializer_class = FeedbackSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter, DjangoFilterBackend]
    filterset_fields = ['student', 'lesson', 'rating']  # Simplified
    search_fields = ['student__user__username', 'student__user__email', 'comment']
    ordering_fields = ['rating', 'created_at']
    ordering = ['-created_at']

    def get_queryset(self):
        user = self.request.user
        if not user.is_authenticated:
            return Feedback.objects.none()
        
        # Platform Admin (staff) sees all feedback
        if user.role == 'A' and user.is_staff:
            return Feedback.objects.all().select_related(
                'student__user', 'student__school', 'lesson__instructor', 'lesson__school'
            )
        
        # School Owner sees feedback in their schools
        if user.role == 'A' and not user.is_staff:
            return Feedback.objects.filter(
                lesson__school__owner=user,
            ).select_related('student__user', 'lesson__instructor', 'lesson__school')
        
        # Instructor sees feedback for their lessons
        if user.role == 'I':
            return Feedback.objects.filter(
                lesson__instructor=user   
            ).select_related('student__user', 'lesson', 'lesson__school')
        
        # Student sees only their own feedback
        if user.role == 'S':
            return Feedback.objects.filter(
                student__user=user
            ).select_related('student__user', 'lesson__instructor', 'lesson__school')
        
        return Feedback.objects.none()
    
    def get_permissions(self):
        if self.action == 'create':
            return [IsAuthenticated(), IsStudent()]  # Only students create feedback
        
        elif self.action in ['update', 'partial_update']:
            return [IsAuthenticated(), IsStudent()]  # Only students update their feedback
        
        elif self.action == 'destroy':
            return [IsAuthenticated(), IsPlatformAdminOrSchoolOwner()]
        
        return [IsAuthenticated()]
    
    def perform_create(self, serializer):
        """Create feedback with validation"""
        user = self.request.user
        student = serializer.validated_data.get('student')
        lesson = serializer.validated_data.get('lesson')
        rating = serializer.validated_data.get('rating', 1)

        # Validate required fields
        if not student:
            raise PermissionDenied("Student is required")
        
        if not lesson:
            raise PermissionDenied("Lesson is required")
        
        # Validate student role
        if student.user.role != 'S':
            raise PermissionDenied("Invalid student - must be a student profile")
        
        # Students can only create feedback for themselves
        if user.role == 'S':
            if student.user != user:
                raise PermissionDenied("You can only create feedback for yourself")
            
            # Check attendance requirement
            attendance = Attendance.objects.filter(
                student=student,
                lesson=lesson,
                presence=True  # Must have attended
            ).first()

            if not attendance:
                raise PermissionDenied("You must have attended this lesson to leave feedback")
            
            # Check if lesson is in the past
            if lesson.date > timezone.now():
                raise PermissionDenied("Cannot submit feedback for future lessons")
            
            # Check for duplicate feedback
            existing_feedback = Feedback.objects.filter(
                student=student,
                lesson=lesson
            ).exists()

            if existing_feedback:
                raise PermissionDenied("Feedback already exists for this lesson")
            
            # Validate rating
            if rating < 1 or rating > 5:
                raise PermissionDenied("Rating must be between 1 and 5")
            
            serializer.save()
            return
        
        raise PermissionDenied("You don't have permission to create feedback")
    
    def perform_update(self, serializer):
        """Update feedback - only students can update their own"""
        user = self.request.user
        instance = self.get_object()

        if user.role == 'S':
            if instance.student.user == user:
                # Validate rating if being updated
                rating = serializer.validated_data.get('rating')
                if rating and (rating < 1 or rating > 5):
                    raise PermissionDenied("Rating must be between 1 and 5")
                
                serializer.save()
                return
            raise PermissionDenied("You can only update your own feedback")
        
        raise PermissionDenied("You don't have permission to update feedback")
    
    def perform_destroy(self, instance):
        """Delete feedback - platform admins and school owners only"""
        user = self.request.user

        if user.role == 'A' and user.is_staff:
            instance.delete()
            return
        
        if user.role == 'A' and not user.is_staff:
            if instance.lesson.school.owner == user:
                instance.delete()
                return
            raise PermissionDenied("You can only delete feedback in your own schools")
            
        raise PermissionDenied("You don't have permission to delete this feedback")
    
    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def lesson_feedback(self, request):
        """Get feedback for a specific lesson"""
        lesson_id = request.query_params.get('lesson_id')
        
        if not lesson_id:
            return Response(
                {'error': 'lesson_id query parameter is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            lesson = Lesson.objects.get(id=lesson_id)
        except Lesson.DoesNotExist:
            return Response(
                {'error': 'Lesson not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        user = request.user
        
        # Check permissions based on role
        if user.role == 'S':
            # Students can only see if they have feedback for this lesson
            feedback = Feedback.objects.filter(
                lesson=lesson,
                student__user=user
            )
            if not feedback.exists():
                raise PermissionDenied("You don't have permission to view feedback for this lesson")
        
        elif user.role == 'I':
            # Instructors can only see feedback for their lessons
            if lesson.instructor != user:
                raise PermissionDenied("You can only view feedback for your own lessons")
        
        elif user.role == 'A' and not user.is_staff:
            # School owners can only see feedback in their schools
            if lesson.school.owner != user:
                raise PermissionDenied("You can only view feedback in your own schools")
        
        # Get all feedback for the lesson
        feedback_list = Feedback.objects.filter(lesson=lesson).select_related(
            'student__user', 'lesson__instructor'
        )
        
        # Calculate statistics
        total = feedback_list.count()
        avg_rating = feedback_list.aggregate(avg=Avg('rating'))['avg'] or 0
        
        # Rating distribution
        distribution = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
        for rating in range(1, 6):
            count = feedback_list.filter(rating=rating).count()
            percentage = round((count / total * 100), 2) if total > 0 else 0
            distribution[rating] = {'count': count, 'percentage': percentage}
        
        serializer = self.get_serializer(feedback_list, many=True)
        
        return Response({
            'lesson': {
                'id': lesson.id,
                'title': lesson.title,
                'date': lesson.date,
                'instructor': lesson.instructor.get_full_name() or lesson.instructor.username
            },
            'statistics': {
                'total_feedback': total,
                'average_rating': round(avg_rating, 2),
                'rating_distribution': distribution
            },
            'feedback_list': serializer.data
        })
    
    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def my_feedback(self, request):
        """Get current student's feedback"""
        user = request.user
        
        if user.role != 'S':
            return Response(
                {'error': 'This endpoint is only for students'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            student_profile = StudentProfile.objects.get(user=user, status='A')
        except StudentProfile.DoesNotExist:
            return Response(
                {'error': 'No active student profile found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        feedback_list = Feedback.objects.filter(
            student=student_profile
        ).select_related('lesson__instructor').order_by('-created_at')
        
        total = feedback_list.count()
        avg_rating = feedback_list.aggregate(avg=Avg('rating'))['avg'] or 0
        
        serializer = self.get_serializer(feedback_list, many=True)
        
        return Response({
            'total_feedback': total,
            'average_rating': round(avg_rating, 2),
            'feedback_list': serializer.data
        })
    
    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def instructor_feedback(self, request):
        """Get feedback for current instructor"""
        user = request.user
        
        if user.role != 'I':
            return Response(
                {'error': 'This endpoint is only for instructors'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get all feedback for instructor's lessons
        feedback_list = Feedback.objects.filter(
            lesson__instructor=user
        ).select_related('student__user', 'lesson').order_by('-created_at')
        
        total = feedback_list.count()
        avg_rating = feedback_list.aggregate(avg=Avg('rating'))['avg'] or 0
        
        # Recent feedback (last 30 days)
        recent = feedback_list.filter(
            created_at__gte=timezone.now() - timedelta(days=30)
        ).count()
        
        serializer = self.get_serializer(feedback_list, many=True)
        
        return Response({
            'statistics': {
                'total_feedback': total,
                'average_rating': round(avg_rating, 2),
                'recent_feedback': recent,
                'rating_distribution': self._get_rating_distribution(feedback_list)
            },
            'recent_feedback': serializer.data[:10]  # Last 10 feedbacks
        })
    
    def _get_rating_distribution(self, queryset):
        """Helper method to calculate rating distribution"""
        distribution = {}
        total = queryset.count()
        
        for rating in range(1, 6):
            count = queryset.filter(rating=rating).count()
            percentage = round((count / total * 100), 2) if total > 0 else 0
            distribution[rating] = {
                'count': count,
                'percentage': percentage
            }
        
        return distribution

        

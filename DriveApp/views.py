from django.shortcuts import render
from rest_framework import viewsets, status, permissions, filters
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from django.contrib.auth import get_user_model
from django.utils import timezone
from .models import (User, DrivingSchool, StudentProfile, Lesson, 
                     Attendance, Schedule, Feedback, Vehicle, VehiclePicture,
                     Achievement, CommunicationTemplate, AutomatedMessage,
                     SchoolAnalytics)
from .serializers import (UserSerializer, DrivingSchoolSerializer, ScheduleSerializer, VehicleSerializer,
                          VehiclePictureSerializer,StudentProfileSerializer, LessonSerializer,AttendanceSerializer,
                          FeedbackSerializer, AchievementSerializer, CommunicationTemplateSerializer, 
                          AutomatedMessageSerializer, SchoolAnalyticsSerializer)
from .permissions import (IsPlatformAdmin, IsInstructor, CanUpdateStudentProfile,
                           IsPlatformAdminOrSchoolOwner, IsPlatformAdminOrSchoolOwnerOrInstructor,
                           IsStudent)
from rest_framework.exceptions import PermissionDenied
from django.db import transaction
from .services import (StudentProfileService, LessonService, AttendanceService, VehicleService, AchievementService, 
                       CommunicationService, CommunicationTemplateService, AnalyticsService, ReportService)
from django.db.models import Avg, Sum, Q, Count, F, Max, Min
from django_filters.rest_framework import DjangoFilterBackend 
from datetime import datetime, timedelta, date
from rest_framework.pagination import PageNumberPagination
from django.utils.dateparse import parse_datetime
from django.http import HttpResponse
import csv
from django.core.cache import cache
from django.db import connection
import io


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

#DSS-8-create-Vehicle-views
class VehicleViewSet(viewsets.ModelViewSet):
    """
    DSS-8-create-Vehicle-views
    ViewSet for managing vehicles in driving schools.
    
    Access Control:
    - Platform Admins (A + is_staff): Full access to all vehicles
    - School Owners (A): Manage vehicles in their schools
    - Instructors (I): View vehicles in their school
    - Students (S): View vehicles in their school (read-only)
    """
    
    serializer_class = VehicleSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter, DjangoFilterBackend]
    filterset_fields = ['school', 'status', 'transmission', 'make', 'year']
    search_fields = ['school__name', 'make', 'model', 'color', 'plate_number']
    ordering_fields = ['year', 'created_at', 'next_maintenance', 'make', 'model']
    ordering = ['-created_at']

    def get_queryset(self):
        """
        Filter vehicles based on user role and school association.
        Multi-tenancy: Users only see vehicles from their own school.
        """
        user = self.request.user
        if not user.is_authenticated:
            return Vehicle.objects.none()
        
        # Platform Admin (staff) sees all vehicles
        if user.role == 'A' and user.is_staff:
            queryset = Vehicle.objects.all()
        
        # School Owner sees vehicles in their schools
        elif user.role == 'A' and not user.is_staff:
            queryset = Vehicle.objects.filter(school__owner=user)
        
        # Instructor sees vehicles in their school
        elif user.role == 'I':
            instructor_profile = user.student_profiles.filter(status='A').first()
            if instructor_profile:
                queryset = Vehicle.objects.filter(school=instructor_profile.school)
            else:
                queryset = Vehicle.objects.none()
        
        # Student sees vehicles in their school
        elif user.role == 'S':
            student_profile = user.student_profiles.filter(status='A').first()
            if student_profile:
                queryset = Vehicle.objects.filter(school=student_profile.school)
            else:
                queryset = Vehicle.objects.none()
        
        else:
            queryset = Vehicle.objects.none()
        
        # Prefetch related data for performance
        return queryset.select_related('school').prefetch_related('pictures')

    def get_permissions(self):
        """Define permissions per action"""
        if self.action == 'create':
            # Only platform admins and school owners can add vehicles
            return [IsAuthenticated(), IsPlatformAdminOrSchoolOwner()]
        
        elif self.action in ['update', 'partial_update']:
            # Platform admins, school owners, and instructors can update
            return [IsAuthenticated(), IsPlatformAdminOrSchoolOwnerOrInstructor()]
        
        elif self.action == 'destroy':
            # Only platform admins and school owners can delete
            return [IsAuthenticated(), IsPlatformAdminOrSchoolOwner()]
        
        elif self.action in ['upload_pictures', 'delete_picture', 'set_primary_picture']:
            # Image management: admins, owners, instructors
            return [IsAuthenticated(), IsPlatformAdminOrSchoolOwnerOrInstructor()]
        
        elif self.action in ['schedule_maintenance', 'complete_maintenance']:
            # Maintenance: admins, owners, instructors
            return [IsAuthenticated(), IsPlatformAdminOrSchoolOwnerOrInstructor()]
        
        return [IsAuthenticated()]

    def get_serializer_context(self):
        """Add request to serializer context"""
        context = super().get_serializer_context()
        
        # Control image loading for list view (optimization)
        if self.action == 'list':
            context['include_images'] = self.request.query_params.get('include_images', 'false').lower() == 'true'
        else:
            context['include_images'] = True
        
        return context

    def perform_create(self, serializer):
        """Create vehicle with permission checks"""
        user = self.request.user
        school = serializer.validated_data.get('school')
        
        # Platform admin can create for any school
        if user.role == 'A' and user.is_staff:
            serializer.save()
            return

        # School owner can only create for their own schools
        if user.role == 'A' and not user.is_staff:
            if school.owner != user:
                raise PermissionDenied("You can only add vehicles to your own schools")
            serializer.save()
            return
        
        raise PermissionDenied("You don't have permission to create vehicles")

    def perform_update(self, serializer):
        """Update vehicle with permission checks"""
        user = self.request.user
        instance = self.get_object()

        # Platform admin can update any vehicle
        if user.role == 'A' and user.is_staff:
            serializer.save()
            return

        # School owner can update vehicles in their schools
        if user.role == 'A' and not user.is_staff:
            if instance.school.owner != user:
                raise PermissionDenied("You can only update vehicles in your own schools")
            serializer.save()
            return
        
        # Instructor can update vehicles in their school (limited fields)
        if user.role == 'I':
            instructor_profile = user.student_profiles.filter(status='A').first()
            if not instructor_profile or instructor_profile.school != instance.school:
                raise PermissionDenied("You can only update vehicles in your school")
            
            # Instructors can only update status and maintenance dates
            allowed_fields = {'status', 'last_maintenance', 'next_maintenance'}
            requested_fields = set(serializer.validated_data.keys())
            
            if not requested_fields.issubset(allowed_fields):
                raise PermissionDenied(f"Instructors can only update: {', '.join(allowed_fields)}")
            
            serializer.save()
            return
        
        raise PermissionDenied("You don't have permission to update this vehicle")

    def perform_destroy(self, instance):
        """Delete vehicle with permission checks"""
        user = self.request.user

        # Platform admin can delete any vehicle
        if user.role == 'A' and user.is_staff:
            instance.delete()
            return

        # School owner can delete vehicles in their schools
        if user.role == 'A' and not user.is_staff:
            if instance.school.owner != user:
                raise PermissionDenied("You can only delete vehicles in your own schools")
            instance.delete()
            return
        
        raise PermissionDenied("You don't have permission to delete this vehicle")

    # ==================== CUSTOM ACTIONS ====================

    @action(detail=True, methods=['get'], permission_classes=[IsAuthenticated])
    def pictures(self, request, pk=None):
        """Get all pictures for a vehicle"""
        vehicle = self.get_object()
        pictures = vehicle.pictures.all()
        serializer = VehiclePictureSerializer(pictures, many=True, context={'request': request})
        
        return Response({
            'vehicle': {
                'id': vehicle.id,
                'plate_number': vehicle.plate_number,
                'make': vehicle.make,
                'model': vehicle.model
            },
            'total_pictures': pictures.count(),
            'pictures': serializer.data
        })

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated, IsPlatformAdminOrSchoolOwnerOrInstructor])
    @transaction.atomic
    def upload_pictures(self, request, pk=None):
        """
        Upload multiple pictures for a vehicle
        POST /api/vehicles/{id}/upload_pictures/
        Body: multipart/form-data with 'images' field containing files
        """
        vehicle = self.get_object()
        user = request.user
        
        # Check permissions
        if not VehicleService.can_modify_vehicle(user, vehicle):
            raise PermissionDenied("You don't have permission to upload pictures for this vehicle")
        
        # Get uploaded files
        images = request.FILES.getlist('images')
        
        if not images:
            return Response(
                {'error': 'No images provided. Please upload at least one image.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validate images
        is_valid, error = VehicleService.validate_multiple_images(images, vehicle)
        if not is_valid:
            return Response({'error': error}, status=status.HTTP_400_BAD_REQUEST)
        
        # Get captions if provided
        captions = request.data.getlist('captions', [])
        
        # Upload images
        uploaded_pictures = []
        current_count = vehicle.pictures.count()
        has_primary = vehicle.pictures.filter(is_primary=True).exists()
        
        for idx, image in enumerate(images):
            # Validate individual image
            is_valid, error = VehicleService.validate_image_file(image)
            if not is_valid:
                return Response(
                    {'error': f'Image {idx + 1}: {error}'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Create picture
            caption = captions[idx] if idx < len(captions) else f"Image {current_count + idx + 1}"
            
            picture = VehiclePicture.objects.create(
                vehicle=vehicle,
                image=image,
                caption=caption,
                is_primary=(not has_primary and idx == 0),
                uploaded_by=user
            )
            uploaded_pictures.append(picture)
        
        # Serialize and return
        serializer = VehiclePictureSerializer(uploaded_pictures, many=True, context={'request': request})
        
        return Response({
            'message': f'Successfully uploaded {len(uploaded_pictures)} images',
            'pictures': serializer.data
        }, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['delete'], permission_classes=[IsAuthenticated, IsPlatformAdminOrSchoolOwnerOrInstructor])
    @transaction.atomic
    def delete_picture(self, request, pk=None):
        """
        Delete a specific picture
        DELETE /api/vehicles/{id}/delete_picture/?picture_id=123
        """
        vehicle = self.get_object()
        picture_id = request.query_params.get('picture_id')
        
        if not picture_id:
            return Response(
                {'error': 'picture_id query parameter is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        success, message = VehicleService.delete_picture(vehicle, picture_id, request.user)
        
        if success:
            return Response({'message': message}, status=status.HTTP_200_OK)
        else:
            return Response({'error': message}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated, IsPlatformAdminOrSchoolOwnerOrInstructor])
    @transaction.atomic
    def set_primary_picture(self, request, pk=None):
        """
        Set a picture as primary
        POST /api/vehicles/{id}/set_primary_picture/
        Body: {"picture_id": 123}
        """
        vehicle = self.get_object()
        picture_id = request.data.get('picture_id')
        
        if not picture_id:
            return Response(
                {'error': 'picture_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check permissions
        if not VehicleService.can_modify_vehicle(request.user, vehicle):
            raise PermissionDenied("You don't have permission to modify this vehicle")
        
        success, message = VehicleService.set_primary_picture(vehicle, picture_id)#this line it's make a problem 
        
        if success:
            return Response({'message': message}, status=status.HTTP_200_OK)
        else:
            return Response({'error': message}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def available(self, request):
        """
        Get all available vehicles for the user's school
        GET /api/vehicles/available/
        """
        queryset = self.get_queryset().filter(status='available')
        
        # Apply additional filters if provided
        date = request.query_params.get('date')  # Future: check schedule conflicts
        transmission = request.query_params.get('transmission')
        
        if transmission:
            queryset = queryset.filter(transmission=transmission)
        
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def maintenance_due(self, request):
        """
        Get vehicles that need maintenance soon (within 30 days)
        GET /api/vehicles/maintenance_due/
        """
        user = request.user
        today = timezone.now().date()
        threshold_date = today + timedelta(days=30)
        
        queryset = self.get_queryset().filter(
            Q(next_maintenance__lte=threshold_date, next_maintenance__gte=today) |
            Q(next_maintenance__lt=today)  # Overdue
        ).order_by('next_maintenance')
        
        # Categorize
        overdue = queryset.filter(next_maintenance__lt=today)
        upcoming = queryset.filter(next_maintenance__gte=today, next_maintenance__lte=threshold_date)
        
        return Response({
            'overdue': {
                'count': overdue.count(),
                'vehicles': self.get_serializer(overdue, many=True).data
            },
            'upcoming': {
                'count': upcoming.count(),
                'vehicles': self.get_serializer(upcoming, many=True).data
            }
        })

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated, IsPlatformAdminOrSchoolOwnerOrInstructor])
    @transaction.atomic
    def schedule_maintenance(self, request, pk=None):
        """
        Schedule maintenance for a vehicle
        POST /api/vehicles/{id}/schedule_maintenance/
        Body: {"next_maintenance": "2024-12-31"}
        """
        vehicle = self.get_object()
        user = request.user
        
        # Check permissions
        if not VehicleService.can_modify_vehicle(user, vehicle):
            raise PermissionDenied("You don't have permission to schedule maintenance")
        
        next_maintenance = request.data.get('next_maintenance')
        notes = request.data.get('notes', '')
        
        if not next_maintenance:
            return Response(
                {'error': 'next_maintenance date is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Update vehicle
        vehicle.status = 'maintenance'
        vehicle.next_maintenance = next_maintenance
        vehicle.save()
        
        serializer = self.get_serializer(vehicle)
        return Response({
            'message': 'Maintenance scheduled successfully',
            'vehicle': serializer.data
        })

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated, IsPlatformAdminOrSchoolOwnerOrInstructor])
    @transaction.atomic
    def complete_maintenance(self, request, pk=None):
        """
        Mark maintenance as completed
        POST /api/vehicles/{id}/complete_maintenance/
        Body: {"next_maintenance": "2025-06-30"} (optional)
        """
        vehicle = self.get_object()
        user = request.user
        
        # Check permissions
        if not VehicleService.can_modify_vehicle(user, vehicle):
            raise PermissionDenied("You don't have permission to complete maintenance")
        
        # Update vehicle
        vehicle.status = 'available'
        vehicle.last_maintenance = timezone.now().date()
        
        # Set next maintenance if provided
        next_maintenance = request.data.get('next_maintenance')
        if next_maintenance:
            vehicle.next_maintenance = next_maintenance
        
        vehicle.save()
        
        serializer = self.get_serializer(vehicle)
        return Response({
            'message': 'Maintenance completed successfully',
            'vehicle': serializer.data
        })

    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def statistics(self, request):
        """
        Get vehicle statistics for the user's accessible schools
        GET /api/vehicles/statistics/
        """
        queryset = self.get_queryset()
        
        total = queryset.count()
        by_status = dict(queryset.values('status').annotate(count=Count('id')).values_list('status', 'count'))
        by_transmission = dict(queryset.values('transmission').annotate(count=Count('id')).values_list('transmission', 'count'))
        
        # Average age
        current_year = timezone.now().year
        ages = [current_year - v.year for v in queryset]
        avg_age = sum(ages) / len(ages) if ages else 0
        
        # Maintenance stats
        today = timezone.now().date()
        overdue_maintenance = queryset.filter(next_maintenance__lt=today).count()
        upcoming_maintenance = queryset.filter(
            next_maintenance__gte=today,
            next_maintenance__lte=today + timedelta(days=30)
        ).count()
        
        return Response({
            'total_vehicles': total,
            'by_status': by_status,
            'by_transmission': by_transmission,
            'average_age': round(avg_age, 1),
            'maintenance': {
                'overdue': overdue_maintenance,
                'upcoming_30_days': upcoming_maintenance
            }
        })

    @action(detail=True, methods=['get'], permission_classes=[IsAuthenticated])
    def history(self, request, pk=None):
        """
        Get vehicle usage history (lessons/schedules)
        GET /api/vehicles/{id}/history/
        """
        vehicle = self.get_object()
        
        # Get schedules for this vehicle
        from .models import Schedule
        schedules = Schedule.objects.filter(vehicle=vehicle).select_related(
            'lesson__instructor', 'instructor'
        ).order_by('-start_time')[:20]
        
        from .serializers import ScheduleSerializer
        schedule_data = ScheduleSerializer(schedules, many=True, context={'request': request}).data
        
        return Response({
            'vehicle': {
                'id': vehicle.id,
                'plate_number': vehicle.plate_number,
                'make': vehicle.make,
                'model': vehicle.model
            },
            'total_lessons': schedules.count(),
            'recent_lessons': schedule_data
        })

    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def my_school_vehicles(self, request):
        """Get vehicles in current user's school (shortcut endpoint)"""
        user = request.user
        
        # Handle different user types
        if user.role == 'A' and user.is_staff:
            # Platform admin sees all vehicles
            queryset = self.get_queryset()
        
        elif user.role == 'A' and not user.is_staff:
            # School owner sees vehicles in their schools
            queryset = self.get_queryset().filter(school__owner=user)
        
        elif user.role in ['I', 'S']:
            # Instructor/Student - get their school via profile
            profile = user.student_profiles.filter(status='A').first()
            if not profile:
                return Response(
                    {'error': 'You are not associated with any active school'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            queryset = self.get_queryset().filter(school=profile.school)
        
        else:
            return Response(
                {'error': 'Invalid user role'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

#DSS-8-create-schedule-views

class ScheduleViewSet(viewsets.ModelViewSet):
    serializer_class = ScheduleSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter, DjangoFilterBackend]
    filterset_fields = ['vehicle', 'instructor', 'lesson__school', 'lesson__status']
    search_fields = ['vehicle__plate_number', 'instructor__username', 'lesson__title', 'start_time']
    ordering_fields = ['start_time', 'end_time', 'lesson__title']
    ordering = ['start_time']  # Changed to ascending for better UX

    def get_queryset(self):
        user = self.request.user
        if not user.is_authenticated:
            return Schedule.objects.none()
        
        # Platform Admin (staff) sees all schedules
        if user.role == 'A' and user.is_staff:
            return Schedule.objects.all().select_related(
                'lesson', 'lesson__school', 'lesson__instructor',
                'vehicle', 'instructor'
            )
        
        # School Owner (admin but not staff) sees schedules in their schools
        if user.role == 'A' and not user.is_staff:
            return Schedule.objects.filter(
                lesson__school__owner=user
            ).select_related(
                'lesson', 'lesson__school', 'lesson__instructor',
                'vehicle', 'instructor'
            )
        
        # Instructor sees their own schedules
        if user.role == 'I':
            return Schedule.objects.filter(
                instructor=user
            ).select_related(
                'lesson', 'lesson__school', 'vehicle'
            )
        
        # Student sees schedules in their school
        if user.role == 'S':
            student_profile = user.student_profiles.filter(status='A').first()
            if student_profile:
                return Schedule.objects.filter(
                    lesson__school=student_profile.school
                ).select_related(
                    'lesson', 'lesson__instructor', 'vehicle', 'instructor'
                )
        
        return Schedule.objects.none()
    
    def get_permissions(self):
        if self.action == 'create':
            return [IsAuthenticated(), IsPlatformAdminOrSchoolOwner()]
        
        elif self.action in ['update', 'partial_update']:
            return [IsAuthenticated(), IsPlatformAdminOrSchoolOwner()]
        
        elif self.action == 'destroy':
            return [IsAuthenticated(), IsPlatformAdminOrSchoolOwner()]
        
        elif self.action in ['cancel_schedule', 'reschedule']:
            return [IsAuthenticated(), IsPlatformAdminOrSchoolOwnerOrInstructor()]
        
        elif self.action in ['check_conflicts', 'my_schedule', 'upcoming', 
                            'instructor_availability', 'vehicle_availability']:
            return [IsAuthenticated()]
        
        return [IsAuthenticated()]
    
    @transaction.atomic
    def perform_create(self, serializer):
        """Create schedule with validation"""
        user = self.request.user
        lesson = serializer.validated_data.get('lesson')
        instructor = serializer.validated_data.get('instructor')
        vehicle = serializer.validated_data.get('vehicle')
        start_time = serializer.validated_data.get('start_time')
        end_time = serializer.validated_data.get('end_time')

        # Validate time slot
        if end_time <= start_time:
            raise PermissionDenied("End time must be after start time")

        if start_time < timezone.now():
            raise PermissionDenied("Cannot schedule in the past")

        if lesson and lesson.status == 'C':
            raise Response({
            'lesson': 'Cannot create schedule for a completed lesson'
        })

        # Check scheduling conflicts
        conflicts = self._check_scheduling_conflicts(
            instructor, vehicle, start_time, end_time
        )
        if conflicts:
            raise PermissionDenied(f"Scheduling conflict: {conflicts}")

        # Platform admin can create for any school
        if user.role == 'A' and user.is_staff:
            serializer.save()
            return

        # School owner can create for their schools
        if user.role == 'A' and not user.is_staff:
            if lesson.school.owner != user:
                raise PermissionDenied("You can only create schedules in your own school!")
            
            # Verify instructor belongs to school
            if instructor and not instructor.student_profiles.filter(
                school=lesson.school, status='A'
            ).exists():
                raise PermissionDenied("Instructor is not assigned to this school")
            
            # Verify vehicle belongs to school
            if vehicle and vehicle.school != lesson.school:
                raise PermissionDenied("Vehicle does not belong to this school")
            
            serializer.save()
            return 
        
        raise PermissionDenied("You don't have permission to create schedules!")
    
    @transaction.atomic
    def perform_update(self, serializer):
        """Update schedule with permission checks"""
        user = self.request.user
        instance = self.get_object()
        lesson = serializer.validated_data.get('lesson', instance.lesson)
        
        # Prevent lesson change
        if 'lesson' in serializer.validated_data and serializer.validated_data['lesson'] != instance.lesson:
            raise PermissionDenied("Cannot change the lesson of an existing schedule")

        # Platform admin can update any schedule
        if user.role == 'A' and user.is_staff:
            # Check for conflicts if time is changing
            if any(field in serializer.validated_data for field in ['start_time', 'end_time', 'instructor', 'vehicle']):
                conflicts = self._check_scheduling_conflicts(
                    serializer.validated_data.get('instructor', instance.instructor),
                    serializer.validated_data.get('vehicle', instance.vehicle),
                    serializer.validated_data.get('start_time', instance.start_time),
                    serializer.validated_data.get('end_time', instance.end_time),
                    exclude_id=instance.id
                )
                if conflicts:
                    raise PermissionDenied(f"Scheduling conflict: {conflicts}")
            serializer.save()
            return 
        
        # School owner can update schedules in their schools
        if user.role == 'A' and not user.is_staff:
            if lesson.school.owner != user:
                raise PermissionDenied("You can only update schedules in your own school!")
            
            # Check for conflicts
            if any(field in serializer.validated_data for field in ['start_time', 'end_time', 'instructor', 'vehicle']):
                conflicts = self._check_scheduling_conflicts(
                    serializer.validated_data.get('instructor', instance.instructor),
                    serializer.validated_data.get('vehicle', instance.vehicle),
                    serializer.validated_data.get('start_time', instance.start_time),
                    serializer.validated_data.get('end_time', instance.end_time),
                    exclude_id=instance.id
                )
                if conflicts:
                    raise PermissionDenied(f"Scheduling conflict: {conflicts}")
            serializer.save()
            return 
        
        raise PermissionDenied("You don't have permission to update this schedule!!")
        
    @transaction.atomic
    def perform_destroy(self, instance):
        """Delete schedule with permission checks"""
        user = self.request.user
        lesson = instance.lesson

        # Prevent deleting schedules in the past
        if instance.start_time < timezone.now():
            raise PermissionDenied("Cannot delete past schedules")

        # Platform admin can delete any schedule
        if user.role == 'A' and user.is_staff:
            instance.delete()
            return

        # School owner can delete schedules in their schools
        if user.role == 'A' and not user.is_staff:
            if lesson.school.owner != user:
                raise PermissionDenied("You can only delete schedules in your own school")
            instance.delete()
            return 
        
        raise PermissionDenied("You don't have permission to delete this schedule!!")
    
    # ==================== HELPER METHODS ====================
    
    def _check_scheduling_conflicts(self, instructor, vehicle, start_time, end_time, exclude_id=None):
        """Check for scheduling conflicts"""
        buffer_minutes = 15  # 15 minutes buffer between lessons
        buffer_time = timedelta(minutes=buffer_minutes)
        
        conflicts = []
        
        # Check instructor conflicts
        if instructor:
            instructor_query = Schedule.objects.filter(
                instructor=instructor,
                start_time__lt=end_time + buffer_time,
                end_time__gt=start_time - buffer_time
            )
            
            if exclude_id:
                instructor_query = instructor_query.exclude(id=exclude_id)
            
            if instructor_query.exists():
                conflict = instructor_query.first()
                conflicts.append(f"Instructor busy from {conflict.start_time} to {conflict.end_time}")
        
        # Check vehicle conflicts
        if vehicle:
            vehicle_query = Schedule.objects.filter(
                vehicle=vehicle,
                start_time__lt=end_time + buffer_time,
                end_time__gt=start_time - buffer_time
            )
            
            if exclude_id:
                vehicle_query = vehicle_query.exclude(id=exclude_id)
            
            if vehicle_query.exists():
                conflict = vehicle_query.first()
                conflicts.append(f"Vehicle booked from {conflict.start_time} to {conflict.end_time}")
        
        return "; ".join(conflicts) if conflicts else None
    
    # ==================== CUSTOM ACTIONS ====================

    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def my_schedule(self, request):
        """Get schedules for the authenticated user"""
        user = request.user
        queryset = self.get_queryset()
        
        # Get query parameters
        range_filter = request.query_params.get('range', 'upcoming').lower()
        date_from = request.query_params.get('date_from')
        date_to = request.query_params.get('date_to')
        include_past = request.query_params.get('include_past', 'false').lower() == 'true'
        status_filter = request.query_params.get('status')
        limit = int(request.query_params.get('limit', 50))
        ordering = request.query_params.get('ordering', 'start_time')
        
        # Validate ordering
        if ordering not in ['start_time', '-start_time']:
            ordering = 'start_time'
        
        # Apply date filtering
        now = timezone.now()
        
        if date_from or date_to:
            # Use explicit date range
            try:
                if date_from:
                    date_from_dt = datetime.strptime(date_from, '%Y-%m-%d').date()
                    date_from_dt = timezone.make_aware(datetime.combine(date_from_dt, datetime.min.time()))
                    queryset = queryset.filter(start_time__gte=date_from_dt)
                
                if date_to:
                    date_to_dt = datetime.strptime(date_to, '%Y-%m-%d').date()
                    date_to_dt = timezone.make_aware(datetime.combine(date_to_dt, datetime.max.time()))
                    queryset = queryset.filter(start_time__lte=date_to_dt)
            except ValueError:
                return Response(
                    {'error': 'Invalid date format. Use YYYY-MM-DD'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        else:
            # Apply range-based filtering
            if range_filter == 'today':
                today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
                today_end = today_start + timedelta(days=1)
                queryset = queryset.filter(start_time__range=[today_start, today_end])
            
            elif range_filter == 'week':
                week_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
                week_end = week_start + timedelta(days=7)
                queryset = queryset.filter(start_time__range=[week_start, week_end])
            
            elif range_filter == 'month':
                month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
                if month_start.month == 12:
                    month_end = month_start.replace(year=month_start.year + 1, month=1)
                else:
                    month_end = month_start.replace(month=month_start.month + 1)
                queryset = queryset.filter(start_time__range=[month_start, month_end])
            
            elif range_filter == 'upcoming':
                # Default: upcoming schedules only
                queryset = queryset.filter(start_time__gte=now)
            else:
                return Response(
                    {'error': 'Invalid range parameter. Use: today, week, month, or upcoming'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        # Filter out past schedules unless explicitly requested
        if not include_past and not (date_from or date_to or range_filter):
            queryset = queryset.filter(start_time__gte=now)
        
        # Apply status filter
        if status_filter:
            queryset = queryset.filter(lesson__status=status_filter)
        
        # Apply ordering
        queryset = queryset.order_by(ordering)

        
        # Prefetch related data
        queryset = queryset.select_related(
            'lesson__instructor',
            'lesson__school',
            'vehicle',
            'instructor'
        )
        
        # Serialize data
        serializer = ScheduleSerializer(queryset, many=True, context={'request': request})
        
        # Calculate summary statistics
        total_schedules = queryset.count()
        completed = queryset.filter(lesson__status='C').count() 
        cancelled = queryset.filter(lesson__status='X').count()  # Assuming 'X' for cancelled
        scheduled = queryset.filter(lesson__status='S').count()
        
        # For instructors: calculate workload hours
        workload_hours = 0
        if user.role == 'I':
            instructor_schedules = queryset.filter(instructor=user)
            for schedule in instructor_schedules:
                if schedule.end_time and schedule.start_time:
                    duration = schedule.end_time - schedule.start_time
                    workload_hours += duration.total_seconds() / 3600
        
        response_data = {
            'summary': {
                'total_schedules': total_schedules,
                'completed': completed,
                'cancelled': cancelled,
                'scheduled': scheduled,
                'user_role': user.role,
                'date_range_applied': {
                    'range': range_filter,
                    'date_from': date_from,
                    'date_to': date_to,
                    'include_past': include_past
                }
            },
            'schedules': serializer.data
        }
        
        # Add this to your my_schedule action, right after the instructor workload calculation:

        # For students: calculate their attendance
        attendance_stats = {}
        if user.role == 'S':
            student_profile = user.student_profiles.filter(status='A').first()
            if student_profile:
                # Get schedules where student has attendance record
                student_schedule_ids = Schedule.objects.filter(
                    lesson__lesson_attendance__student=student_profile
                ).values_list('id', flat=True)
                
                present_count = Attendance.objects.filter(
                    student=student_profile,
                    lesson__schedule__in=queryset,
                    presence=True
                ).count()
                
                total_scheduled_for_student = queryset.filter(id__in=student_schedule_ids).count()
                
                attendance_stats = {
                    'total_scheduled': total_scheduled_for_student,
                    'present_count': present_count,
                    'attendance_rate': round((present_count / total_scheduled_for_student * 100), 2) if total_scheduled_for_student > 0 else 0
                }

        # Add role-specific stats
        if user.role == 'I':
            response_data['summary']['workload_hours'] = round(workload_hours, 2)
            response_data['summary']['schedules_count'] = queryset.filter(instructor=user).count()
        
        # ADD THIS FOR STUDENTS:
        if user.role == 'S' and attendance_stats:
            response_data['summary']['attendance'] = attendance_stats
        # Add next important schedule
        if total_schedules > 0:
            next_schedule = queryset.filter(start_time__gte=now).order_by('start_time').first()
            if next_schedule:
                response_data['next_schedule'] = {
                    'id': next_schedule.id,
                    'title': next_schedule.lesson.title if next_schedule.lesson else 'No title',
                    'start_time': next_schedule.start_time,
                    'instructor': next_schedule.instructor.get_full_name() or next_schedule.instructor.username,
                    'location': next_schedule.lesson.school.name if next_schedule.lesson and next_schedule.lesson.school else 'Not specified'
                }
        

        # Apply limit
        if limit > 0:
            queryset = queryset[:limit]

        return Response(response_data)


    @action(detail=False, methods=['post'], permission_classes=[IsAuthenticated])
    def check_conflicts(self, request):
        """Check for scheduling conflicts"""
        instructor_id = request.data.get('instructor_id')
        vehicle_id = request.data.get('vehicle_id')
        start_time_str = request.data.get('start_time')
        end_time_str = request.data.get('end_time')
        exclude_schedule_id = request.data.get('exclude_schedule_id')
        
        # Validate required fields
        if not start_time_str or not end_time_str:
            return Response(
                {'error': 'start_time and end_time are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            start_time = parse_datetime(start_time_str)
            end_time = parse_datetime(end_time_str)
            if start_time is None or end_time is None:
                return Response(
                    {'error': 'Invalid datetime format. Use ISO format (YYYY-MM-DDTHH:MM:SS[±HH:MM])'},
                    status=status.HTTP_400_BAD_REQUEST
                )            
            if timezone.is_naive(start_time):
                start_time = timezone.make_aware(start_time)
            if timezone.is_naive(end_time):
                end_time = timezone.make_aware(end_time)

        except (ValueError, TypeError):
            return Response(
                {'error': 'Invalid datetime format. Use ISO format (YYYY-MM-DDTHH:MM:SS)'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validate time slot
        if end_time <= start_time:
            return Response(
                {'error': 'End time must be after start time'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get objects
        instructor = None
        vehicle = None
        
        if instructor_id:
            try:
                from .models import User
                instructor = User.objects.get(id=instructor_id, role='I')
            except User.DoesNotExist:
                return Response(
                    {'error': 'Instructor not found'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        if vehicle_id:
            try:
                vehicle = Vehicle.objects.get(id=vehicle_id)
            except Vehicle.DoesNotExist:
                return Response(
                    {'error': 'Vehicle not found'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        # Check conflicts
        conflicts = []
        buffer_minutes = 15
        buffer_time = timedelta(minutes=buffer_minutes)
        
        # Check instructor conflicts
        if instructor:
            instructor_query = Schedule.objects.filter(
                instructor=instructor,
                start_time__lt=end_time + buffer_time,
                end_time__gt=start_time - buffer_time
            )
            
            if exclude_schedule_id:
                instructor_query = instructor_query.exclude(id=exclude_schedule_id)
            
            if instructor_query.exists():
                for conflict in instructor_query:
                    conflicts.append({
                        'type': 'instructor',
                        'schedule_id': conflict.id,
                        'start_time': conflict.start_time,
                        'end_time': conflict.end_time,
                        'lesson_title': conflict.lesson.title if conflict.lesson else 'No title'
                    })
        
        # Check vehicle conflicts
        if vehicle:
            vehicle_query = Schedule.objects.filter(
                vehicle=vehicle,
                start_time__lt=end_time + buffer_time,
                end_time__gt=start_time - buffer_time
            )
            
            if exclude_schedule_id:
                vehicle_query = vehicle_query.exclude(id=exclude_schedule_id)
            
            if vehicle_query.exists():
                for conflict in vehicle_query:
                    conflicts.append({
                        'type': 'vehicle',
                        'schedule_id': conflict.id,
                        'start_time': conflict.start_time,
                        'end_time': conflict.end_time,
                        'lesson_title': conflict.lesson.title if conflict.lesson else 'No title'
                    })
        
        return Response({
            'has_conflicts': len(conflicts) > 0,
            'conflicts': conflicts,
            'available': len(conflicts) == 0,
            'time_slot': {
                'start_time': start_time,
                'end_time': end_time,
                'duration_minutes': (end_time - start_time).total_seconds() / 60
            }
        })

    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def instructor_availability(self, request):
        """Get available time slots for an instructor"""
        instructor_id = request.query_params.get('instructor_id')
        date_str = request.query_params.get('date')
        duration_minutes = int(request.query_params.get('duration', 60))
        
        if not instructor_id or not date_str:
            return Response(
                {'error': 'instructor_id and date are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            from .models import User
            instructor = User.objects.get(id=instructor_id, role='I')
        except User.DoesNotExist:
            return Response(
                {'error': 'Instructor not found'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
            date_start = timezone.make_aware(datetime.combine(date_obj, datetime.min.time()))
            date_end = timezone.make_aware(datetime.combine(date_obj, datetime.max.time()))
        except ValueError:
            return Response(
                {'error': 'Invalid date format. Use YYYY-MM-DD'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get instructor's schedules for the day
        schedules = Schedule.objects.filter(
            instructor=instructor,
            start_time__date=date_obj
        ).order_by('start_time')
        
        # Define working hours (8 AM to 6 PM)
        working_start = date_start.replace(hour=8, minute=0, second=0, microsecond=0)
        working_end = date_start.replace(hour=18, minute=0, second=0, microsecond=0)
        
        # Generate time slots
        slot_duration = timedelta(minutes=duration_minutes)
        buffer = timedelta(minutes=15)  # Buffer between lessons
        available_slots = []
        
        current_time = working_start
        while current_time + slot_duration <= working_end:
            slot_end = current_time + slot_duration
            
            # Check if this slot conflicts with existing schedules
            conflict = False
            for schedule in schedules:
                schedule_start = schedule.start_time
                schedule_end = schedule.end_time
                
                # Check for overlap (with buffer)
                if (current_time < schedule_end + buffer and 
                    slot_end > schedule_start - buffer):
                    conflict = True
                    break
            
            if not conflict:
                available_slots.append({
                    'start_time': current_time,
                    'end_time': slot_end,
                    'duration_minutes': duration_minutes
                })
            
            # Move to next slot (30-minute increments)
            current_time += timedelta(minutes=30)
        
        return Response({
            'instructor': {
                'id': instructor.id,
                'name': instructor.get_full_name() or instructor.username
            },
            'date': date_obj,
            'working_hours': {
                'start': working_start.time(),
                'end': working_end.time()
            },
            'scheduled_lessons': ScheduleSerializer(schedules, many=True).data,
            'available_slots': available_slots,
            'total_available_slots': len(available_slots)
        })

    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def vehicle_availability(self, request):
        """Get available time slots for a vehicle"""
        vehicle_id = request.query_params.get('vehicle_id')
        date_str = request.query_params.get('date')
        duration_minutes = int(request.query_params.get('duration', 60))
        
        if not vehicle_id or not date_str:
            return Response(
                {'error': 'vehicle_id and date are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            vehicle = Vehicle.objects.get(id=vehicle_id)
        except Vehicle.DoesNotExist:
            return Response(
                {'error': 'Vehicle not found'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check vehicle status
        if vehicle.status != 'available':
            return Response({
                'available': False,
                'reason': f'Vehicle is {vehicle.get_status_display()}',
                'suggested_action': 'Select a different vehicle or change vehicle status'
            })
        
        try:
            date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
            date_start = timezone.make_aware(datetime.combine(date_obj, datetime.min.time()))
            date_end = timezone.make_aware(datetime.combine(date_obj, datetime.max.time()))
        except ValueError:
            return Response(
                {'error': 'Invalid date format. Use YYYY-MM-DD'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get vehicle's schedules for the day
        schedules = Schedule.objects.filter(
            vehicle=vehicle,
            start_time__date=date_obj
        ).order_by('start_time')
        
        # Define working hours (8 AM to 6 PM)
        working_start = date_start.replace(hour=8, minute=0, second=0, microsecond=0)
        working_end = date_start.replace(hour=18, minute=0, second=0, microsecond=0)
        
        # Generate time slots
        slot_duration = timedelta(minutes=duration_minutes)
        buffer = timedelta(minutes=30)  # Buffer for vehicle maintenance/cleaning
        available_slots = []
        
        current_time = working_start
        while current_time + slot_duration <= working_end:
            slot_end = current_time + slot_duration
            
            # Check if this slot conflicts with existing schedules
            conflict = False
            for schedule in schedules:
                schedule_start = schedule.start_time
                schedule_end = schedule.end_time
                
                # Check for overlap (with buffer)
                if (current_time < schedule_end + buffer and 
                    slot_end > schedule_start - buffer):
                    conflict = True
                    break
            
            if not conflict:
                available_slots.append({
                    'start_time': current_time,
                    'end_time': slot_end,
                    'duration_minutes': duration_minutes
                })
            
            # Move to next slot (30-minute increments)
            current_time += timedelta(minutes=30)
        
        return Response({
            'vehicle': {
                'id': vehicle.id,
                'plate_number': vehicle.plate_number,
                'make': vehicle.make,
                'model': vehicle.model,
                'status': vehicle.status
            },
            'date': date_obj,
            'working_hours': {
                'start': working_start.time(),
                'end': working_end.time()
            },
            'scheduled_lessons': ScheduleSerializer(schedules, many=True).data,
            'available_slots': available_slots,
            'total_available_slots': len(available_slots)
        })

    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def upcoming(self, request):
        """Get upcoming schedules (next 7 days)"""
        user = request.user
        now = timezone.now()
        next_week = now + timedelta(days=7)
        
        queryset = self.get_queryset().filter(
            start_time__gte=now,
            start_time__lte=next_week
        ).order_by('start_time')
        
        # Apply role-specific filtering
        if user.role == 'I':
            queryset = queryset.filter(instructor=user)
        elif user.role == 'S':
            student_profile = user.student_profiles.filter(status='A').first()
            if student_profile:
                # FIXED: Only show schedules for lessons the student attended
                from .models import Attendance
                attended_lesson_ids = Attendance.objects.filter(
                    student=student_profile,
                    presence=True
                ).values_list('lesson_id', flat=True)
                
                queryset = queryset.filter(lesson_id__in=attended_lesson_ids)

        # Group by day
        schedules_by_day = {}
        for schedule in queryset:
            day_key = schedule.start_time.date().isoformat()
            if day_key not in schedules_by_day:
                schedules_by_day[day_key] = []
            schedules_by_day[day_key].append(ScheduleSerializer(schedule).data)
        
        # Calculate daily counts
        daily_counts = {
            day: len(schedules) for day, schedules in schedules_by_day.items()
        }
        
        return Response({
            'period': {
                'start': now.date(),
                'end': next_week.date(),
                'days': 7
            },
            'total_schedules': queryset.count(),
            'daily_counts': daily_counts,
            'schedules_by_day': schedules_by_day,
            'today': now.date().isoformat(),
            'tomorrow': (now.date() + timedelta(days=1)).isoformat()
        })

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated, IsPlatformAdminOrSchoolOwnerOrInstructor])
    @transaction.atomic
    def cancel_schedule(self, request, pk=None):
        """Cancel a schedule"""
        schedule = self.get_object()
        user = request.user
        
        # Check permissions
        if user.role == 'I' and schedule.instructor != user:
            raise PermissionDenied("You can only cancel your own schedules")
        
        if user.role == 'A' and not user.is_staff:
            if schedule.lesson.school.owner != user:
                raise PermissionDenied("You can only cancel schedules in your school")
        
        # Check if schedule is in the past
        if schedule.start_time < timezone.now():
            return Response(
                {'error': 'Cannot cancel past schedules'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Update lesson status to cancelled
        lesson = schedule.lesson
        lesson.status = 'X'  # Assuming 'X' is cancelled
        lesson.save()
        
        # Delete the schedule
        schedule_id = schedule.id
        schedule.delete()
        
        return Response({
            'message': 'Schedule cancelled successfully',
            'cancelled_schedule_id': schedule_id,
            'lesson_id': lesson.id,
            'lesson_status': 'cancelled',
            'cancelled_at': timezone.now()
        })

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated, IsPlatformAdminOrSchoolOwnerOrInstructor])
    @transaction.atomic
    def reschedule(self, request, pk=None):
        """Reschedule a lesson to a new time"""
        schedule = self.get_object()
        user = request.user
        
        # Check permissions
        if user.role == 'I' and schedule.instructor != user:
            raise PermissionDenied("You can only reschedule your own lessons")
        
        if user.role == 'A' and not user.is_staff:
            if schedule.lesson.school.owner != user:
                raise PermissionDenied("You can only reschedule lessons in your school")
        
        # Get new time slot
        new_start_time_str = request.data.get('start_time')
        new_end_time_str = request.data.get('end_time')
        
        if not new_start_time_str or not new_end_time_str:
            return Response(
                {'error': 'start_time and end_time are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            new_start_time = parse_datetime(new_start_time_str)
            new_end_time = parse_datetime(new_end_time_str)
            if new_start_time is None or new_end_time is None:
                return Response({'error': 'Invalid datetime format'},status=status.HTTP_400_BAD_REQUEST)

            if timezone.is_naive(new_start_time):
                new_start_time = timezone.make_aware(new_start_time)
            if timezone.is_naive(new_end_time):
                new_end_time = timezone.make_aware(new_end_time)

        except (ValueError, TypeError):
            return Response(
                {'error': 'Invalid datetime format. Use ISO format (YYYY-MM-DDTHH:MM:SS)'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validate new time slot
        if new_end_time <= new_start_time:
            return Response(
                {'error': 'End time must be after start time'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if new_start_time < timezone.now():
            return Response(
                {'error': 'Cannot reschedule to a past time'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check for conflicts
        conflicts = self._check_scheduling_conflicts(
            schedule.instructor,
            schedule.vehicle,
            new_start_time,
            new_end_time,
            exclude_id=schedule.id
        )
        
        if conflicts:
            return Response({
                'error': 'Scheduling conflict',
                'conflicts': conflicts,
                'available': False
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Update schedule
        old_start_time = schedule.start_time
        old_end_time = schedule.end_time
        
        schedule.start_time = new_start_time
        schedule.end_time = new_end_time
        schedule.save()
        
        # Update lesson date if it's different day
        if schedule.lesson.date.date() != new_start_time.date():
            schedule.lesson.date = new_start_time
            schedule.lesson.save()
        
        serializer = ScheduleSerializer(schedule, context={'request': request})
        
        return Response({
            'message': 'Schedule updated successfully',
            'schedule': serializer.data,
            'changes': {
                'old_start_time': old_start_time,
                'old_end_time': old_end_time,
                'new_start_time': new_start_time,
                'new_end_time': new_end_time
            }
        })

    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def my_schedule_mobile(self, request):
        """Mobile-optimized schedule endpoint"""
        user = request.user
        queryset = self.get_queryset()
        
        # Filter upcoming only
        now = timezone.now()
        queryset = queryset.filter(start_time__gte=now)
        
        # Apply date filter if provided
        date_str = request.query_params.get('date')
        if date_str:
            try:
                date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
                date_start = timezone.make_aware(datetime.combine(date_obj, datetime.min.time()))
                date_end = timezone.make_aware(datetime.combine(date_obj, datetime.max.time()))
                queryset = queryset.filter(start_time__range=[date_start, date_end])
            except ValueError:
                return Response(
                    {'error': 'Invalid date format. Use YYYY-MM-DD'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        # Order by start time
        queryset = queryset.order_by('start_time')
        
        # Pagination
        page_size = min(int(request.query_params.get('page_size', 10)), 50)
        paginator = PageNumberPagination()
        paginator.page_size = page_size
        
        page = paginator.paginate_queryset(queryset, request)
        if page is not None:
            serializer = ScheduleSerializer(page, many=True, context={'request': request})
            
            # Get counts for today and tomorrow
            today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            today_end = today_start + timedelta(days=1)
            tomorrow_end = today_end + timedelta(days=1)
            
            today_count = queryset.filter(start_time__range=[today_start, today_end]).count()
            tomorrow_count = queryset.filter(start_time__range=[today_end, tomorrow_end]).count()
            
            response_data = {
                'today_count': today_count,
                'tomorrow_count': tomorrow_count,
                'total_upcoming': queryset.count(),
                'user_role': user.role,
                'schedules': serializer.data
            }
            
            return paginator.get_paginated_response(response_data)
        
        serializer = ScheduleSerializer(queryset, many=True, context={'request': request})
        return Response(serializer.data)

#Dss-11-create-Achievement-view     
class AchievemtViewSet(viewsets.ModelViewSet):
    serializer_class =  AchievementSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter, DjangoFilterBackend]
    filterset_fields = ['student__school','type','title','points']
    search_fields = ['student__user__username','type','title','points','description','icon','earned_at']
    ordering_fields = ['type','earned_at','points','student__user__username']
    ordering = ['-earned_at']

    def get_queryset(self):
        user = self.request.user
        if not user.is_authenticated:
            return Achievement.objects.none()
        
        # Platform Admin (staff) sees all Achievment
        if user.role == 'A' and user.is_staff:
            return Achievement.objects.all().select_related('student__user','student__school')
        
        # School Owner (admin but not staff) sees Achievement in their schools
        if user.role == 'A' and not user.is_staff:
            return Achievement.objects.filter(
                student__school__owner=user
            ).select_related('student__user','student__school')
        
        # Instructor sees their own school Achievement
        if user.role == 'I':
            instructor_profile = user.student_profiles.filter(status='A').first()
            if instructor_profile:
                return Achievement.objects.filter(
                    student__school=instructor_profile.school
                ).select_related('student__user','student__school')
            return Achievement.objects.none()
        
        # Student sees schedules in their school
        if user.role == 'S':
            return Achievement.objects.filter(
                student__user = user
            ).select_related('student__user','student__school')
        
        return Achievement.objects.none()
    
    def get_permissions(self):
        if self.action == 'create':
            return [IsAuthenticated(), IsPlatformAdminOrSchoolOwner()]

        elif self.action in ['update','partial_update']:
            return [IsAuthenticated(), IsPlatformAdmin()]
        
        elif self.action == 'destroy':
            return [IsAuthenticated(), IsPlatformAdmin()]
        
        elif self.action in ['award_achievement', 'bulk_award', 'check_milestones']:
            return [IsAuthenticated(), IsPlatformAdminOrSchoolOwnerOrInstructor()]
        
        elif self.action in ['my_achievements', 'leaderboard', 'statistics','student_progress', 'available_achievements']:
            return [IsAuthenticated()]
        
        return [IsAuthenticated()]
    
    def get_serializer_context(self):
        """Add request to serializer context"""
        context = super().get_serializer_context()
        context['request'] = self.request
        return context
    
    @transaction.atomic
    def perform_create(self, serializer):
        """Create Achievement with validation"""
        user =self.request.user
        student = serializer.validated_data.get('student')

        if user.role == 'A' and user.is_staff:
            serializer.save()
            return 
        
        if user.role == 'A' and not user.is_staff:
            if student.school.owner != user:
                raise PermissionDenied("You can only award achievements to students in your schools")
            serializer.save()
            return
        
        raise PermissionDenied("You don't have permission to create achievements!")
    
    @transaction.atomic
    def perform_update(self, serializer):
        user = self.request.user

        if user.role == 'A' and user.is_staff:
            serializer.save()
            return
        
        raise PermissionDenied("Only platform administrators can update achievements")
    
    @transaction.atomic
    def perform_destroy(self, instance):
        user = self.request.user

        if user.role == 'A' and user.is_staff:
            instance.delete()
            return
        
        raise PermissionDenied("Only platform administrators can delete achievements")

    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def my_achievements(self, request):
        """
        Get achievements for the current student.
        Returns achievements with progress tracking.
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
        
        # Get student's achievements
        achievements = Achievement.objects.filter(student=student_profile).order_by('-earned_at')
        serializer = self.get_serializer(achievements, many=True)
        
        # Calculate statistics
        total_achievements = achievements.count()
        total_points = achievements.aggregate(total=Sum('points'))['total'] or 0
        
        # Get available achievements (not yet earned)
        earned_types = set(achievements.values_list('type', flat=True))
        available = [
            {
                'type': key,
                'title': value['title'],
                'description': value['description'],
                'points': value['points'],
                'icon': value['icon'],
                'progress': self._calculate_progress(student_profile, key)
            }
            for key, value in AchievementService.ACHIEVEMENT_RULES.items()
            if key not in earned_types
        ]
        
        # Recent achievements (last 7 days)
        week_ago = timezone.now() - timedelta(days=7)
        recent_achievements = achievements.filter(earned_at__gte=week_ago)
        
        return Response({
            'student': {
                'id': student_profile.id,
                'name': user.get_full_name() or user.username,
                'school': student_profile.school.name
            },
            'summary': {
                'total_achievements': total_achievements,
                'total_points': total_points,
                'recent_count': recent_achievements.count(),
                'completion_rate': round(
                    (total_achievements / len(AchievementService.ACHIEVEMENT_RULES) * 100), 2
                )
            },
            'earned_achievements': serializer.data,
            'available_achievements': available,
            'recent_achievements': AchievementSerializer(recent_achievements, many=True).data
        })
    
    @action(detail=False, methods=['post'], permission_classes=[IsAuthenticated, IsPlatformAdminOrSchoolOwnerOrInstructor])
    @transaction.atomic
    def award_achievement(self, request):
        """
        Manually award an achievement to a student.
        
        Body:
        {
            "student_id": 123,
            "achievement_type": "first_lesson",
            "custom_title": "Optional custom title",
            "custom_description": "Optional custom description"
        }
        """
        student_id = request.data.get('student_id')
        achievement_type = request.data.get('achievement_type')
        custom_title = request.data.get('custom_title')
        custom_description = request.data.get('custom_description')
        
        # Validate input
        if not student_id or not achievement_type:
            return Response(
                {'error': 'student_id and achievement_type are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get student
        try:
            student = StudentProfile.objects.select_related('school', 'user').get(id=student_id)
        except StudentProfile.DoesNotExist:
            return Response(
                {'error': 'Student not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Check permissions
        user = request.user
        if user.role == 'I':
            instructor_profile = user.student_profiles.filter(status='A').first()
            if not instructor_profile or instructor_profile.school != student.school:
                raise PermissionDenied("You can only award achievements to students in your school")
        
        if user.role == 'A' and not user.is_staff:
            if student.school.owner != user:
                raise PermissionDenied("You can only award achievements to students in your schools")
        
        # Check if achievement already exists
        if Achievement.objects.filter(student=student, type=achievement_type).exists():
            return Response(
                {'error': 'Student already has this achievement'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get achievement details from rules
        rule = AchievementService.ACHIEVEMENT_RULES.get(achievement_type)
        if not rule:
            return Response(
                {'error': f'Invalid achievement type: {achievement_type}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Create achievement
        achievement = Achievement.objects.create(
            student=student,
            type=achievement_type,
            title=custom_title or rule['title'],
            description=custom_description or rule['description'],
            icon=rule['icon'],
            points=rule['points']
        )
        
        serializer = self.get_serializer(achievement)
        
        return Response({
            'message': 'Achievement awarded successfully',
            'achievement': serializer.data,
            'awarded_to': {
                'id': student.id,
                'name': student.user.get_full_name() or student.user.username,
                'school': student.school.name
            }
        }, status=status.HTTP_201_CREATED)
    
    @action(detail=False, methods=['post'], permission_classes=[IsAuthenticated, IsPlatformAdminOrSchoolOwner])
    @transaction.atomic
    def bulk_award(self, request):
        """
        Award achievement to multiple students.
        
        Body:
        {
            "student_ids": [1, 2, 3],
            "achievement_type": "first_lesson"
        }
        """
        student_ids = request.data.get('student_ids', [])
        achievement_type = request.data.get('achievement_type')
        
        if not student_ids or not achievement_type:
            return Response(
                {'error': 'student_ids (array) and achievement_type are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validate achievement type
        rule = AchievementService.ACHIEVEMENT_RULES.get(achievement_type)
        if not rule:
            return Response(
                {'error': f'Invalid achievement type: {achievement_type}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get students
        students = StudentProfile.objects.filter(id__in=student_ids).select_related('school', 'user')
        
        if not students.exists():
            return Response(
                {'error': 'No valid students found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Check permissions
        user = request.user
        if user.role == 'A' and not user.is_staff:
            # School owner can only award to their students
            students = students.filter(school__owner=user)
        
        # Award achievements
        awarded = []
        skipped = []
        
        for student in students:
            # Skip if already has this achievement
            if Achievement.objects.filter(student=student, type=achievement_type).exists():
                skipped.append({
                    'student_id': student.id,
                    'name': student.user.username,
                    'reason': 'Already has this achievement'
                })
                continue
            
            # Create achievement
            achievement = Achievement.objects.create(
                student=student,
                type=achievement_type,
                title=rule['title'],
                description=rule['description'],
                icon=rule['icon'],
                points=rule['points']
            )
            
            awarded.append({
                'student_id': student.id,
                'name': student.user.get_full_name() or student.user.username,
                'achievement_id': achievement.id
            })
        
        return Response({
            'message': f'Awarded achievement to {len(awarded)} students',
            'summary': {
                'requested': len(student_ids),
                'awarded': len(awarded),
                'skipped': len(skipped)
            },
            'awarded_to': awarded,
            'skipped': skipped
        }, status=status.HTTP_201_CREATED)
    
    @action(detail=False, methods=['post'], permission_classes=[IsAuthenticated, IsPlatformAdminOrSchoolOwnerOrInstructor])
    def check_milestones(self, request):
        """
        Check and automatically award achievements based on student progress.
        
        Body:
        {
            "student_id": 123  # Optional, checks all students if not provided
        }
        """
        student_id = request.data.get('student_id')
        user = request.user
        
        if student_id:
            # Check specific student
            try:
                student = StudentProfile.objects.get(id=student_id)
            except StudentProfile.DoesNotExist:
                return Response(
                    {'error': 'Student not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Permission check
            if user.role == 'I':
                instructor_profile = user.student_profiles.filter(status='A').first()
                if not instructor_profile or instructor_profile.school != student.school:
                    raise PermissionDenied("You can only check students in your school")
            
            if user.role == 'A' and not user.is_staff:
                if student.school.owner != user:
                    raise PermissionDenied("You can only check students in your schools")
            
            students = [student]
        else:
            # Check all students based on user role
            if user.role == 'A' and user.is_staff:
                students = StudentProfile.objects.filter(status='A')
            elif user.role == 'A' and not user.is_staff:
                students = StudentProfile.objects.filter(school__owner=user, status='A')
            elif user.role == 'I':
                instructor_profile = user.student_profiles.filter(status='A').first()
                if instructor_profile:
                    students = StudentProfile.objects.filter(
                        school=instructor_profile.school,
                        status='A'
                    )
                else:
                    students = []
            else:
                return Response(
                    {'error': 'Invalid user role'},
                    status=status.HTTP_403_FORBIDDEN
                )
        
        # Check milestones for each student
        results = []
        for student in students:
            before_count = Achievement.objects.filter(student=student).count()
            
            # Use AchievementService to check and award
            AchievementService.check_and_award(student)
            
            after_count = Achievement.objects.filter(student=student).count()
            new_achievements = after_count - before_count
            
            if new_achievements > 0:
                results.append({
                    'student_id': student.id,
                    'name': student.user.get_full_name() or student.user.username,
                    'new_achievements': new_achievements
                })
        
        return Response({
            'message': f'Checked {len(students)} students',
            'students_checked': len(students),
            'achievements_awarded': sum(r['new_achievements'] for r in results),
            'results': results
        })
    
    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def leaderboard(self, request):
        """
        Get achievement leaderboard.
        
        Query params:
        - scope: 'school' or 'platform' (default: school for non-admins)
        - limit: number of top students (default: 10)
        - time_period: 'all_time', 'month', 'week' (default: all_time)
        """
        user = request.user
        scope = request.query_params.get('scope', 'school')
        limit = min(int(request.query_params.get('limit', 10)), 100)
        time_period = request.query_params.get('time_period', 'all_time')
        
        # Determine queryset based on scope and permissions
        if scope == 'platform':
            if user.role != 'A' or not user.is_staff:
                return Response(
                    {'error': 'Only platform admins can view platform-wide leaderboard'},
                    status=status.HTTP_403_FORBIDDEN
                )
            queryset = Achievement.objects.all()
        else:  # school scope
            if user.role == 'A' and user.is_staff:
                # Platform admin can view any school, but need school_id
                school_id = request.query_params.get('school_id')
                if school_id:
                    queryset = Achievement.objects.filter(student__school_id=school_id)
                else:
                    return Response(
                        {'error': 'school_id required for platform admin viewing school leaderboard'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            elif user.role == 'A' and not user.is_staff:
                queryset = Achievement.objects.filter(student__school__owner=user)
            elif user.role == 'I':
                instructor_profile = user.student_profiles.filter(status='A').first()
                if instructor_profile:
                    queryset = Achievement.objects.filter(student__school=instructor_profile.school)
                else:
                    queryset = Achievement.objects.none()
            elif user.role == 'S':
                student_profile = user.student_profiles.filter(status='A').first()
                if student_profile:
                    queryset = Achievement.objects.filter(student__school=student_profile.school)
                else:
                    queryset = Achievement.objects.none()
            else:
                queryset = Achievement.objects.none()
        
        # Apply time filter
        if time_period == 'week':
            week_ago = timezone.now() - timedelta(days=7)
            queryset = queryset.filter(earned_at__gte=week_ago)
        elif time_period == 'month':
            month_ago = timezone.now() - timedelta(days=30)
            queryset = queryset.filter(earned_at__gte=month_ago)
        # 'all_time' - no filter
        
        # Aggregate points by student
        from django.db.models import Sum, Count
        leaderboard = queryset.values(
            'student__id',
            'student__user__username',
            'student__user__first_name',
            'student__user__last_name',
            'student__school__name'
        ).annotate(
            total_points=Sum('points'),
            achievement_count=Count('id')
        ).order_by('-total_points')[:limit]
        
        # Format response
        ranked_students = []
        for rank, entry in enumerate(leaderboard, 1):
            full_name = f"{entry['student__user__first_name']} {entry['student__user__last_name']}".strip()
            ranked_students.append({
                'rank': rank,
                'student_id': entry['student__id'],
                'name': full_name or entry['student__user__username'],
                'username': entry['student__user__username'],
                'school': entry['student__school__name'],
                'total_points': entry['total_points'],
                'achievement_count': entry['achievement_count']
            })
        
        # Get current user's rank (if student)
        user_rank = None
        if user.role == 'S':
            student_profile = user.student_profiles.filter(status='A').first()
            if student_profile:
                user_rank_queryset = queryset.filter(student=student_profile).aggregate(
                    total_points=Sum('points'),
                    achievement_count=Count('id')
                )
                
                # Find rank
                better_students = queryset.values('student').annotate(
                    total_points=Sum('points')
                ).filter(
                    total_points__gt=user_rank_queryset['total_points'] or 0
                ).count()
                
                user_rank = {
                    'rank': better_students + 1,
                    'total_points': user_rank_queryset['total_points'] or 0,
                    'achievement_count': user_rank_queryset['achievement_count'] or 0
                }
        
        return Response({
            'leaderboard': ranked_students,
            'metadata': {
                'scope': scope,
                'time_period': time_period,
                'limit': limit,
                'total_students': queryset.values('student').distinct().count()
            },
            'your_rank': user_rank
        })
    
    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def statistics(self, request):
        """
        Get achievement statistics.
        Scope depends on user role.
        """
        user = request.user
        
        # Determine queryset based on role
        if user.role == 'A' and user.is_staff:
            queryset = Achievement.objects.all()
            scope = 'platform'
        elif user.role == 'A' and not user.is_staff:
            queryset = Achievement.objects.filter(student__school__owner=user)
            scope = 'schools'
        elif user.role == 'I':
            instructor_profile = user.student_profiles.filter(status='A').first()
            if instructor_profile:
                queryset = Achievement.objects.filter(student__school=instructor_profile.school)
                scope = 'school'
            else:
                queryset = Achievement.objects.none()
                scope = 'none'
        elif user.role == 'S':
            student_profile = user.student_profiles.filter(status='A').first()
            if student_profile:
                queryset = Achievement.objects.filter(student=student_profile)
                scope = 'personal'
            else:
                queryset = Achievement.objects.none()
                scope = 'none'
        else:
            queryset = Achievement.objects.none()
            scope = 'none'
        
        # Calculate statistics
        from django.db.models import Sum, Count, Avg
        
        total_achievements = queryset.count()
        total_points = queryset.aggregate(total=Sum('points'))['total'] or 0
        unique_students = queryset.values('student').distinct().count()
        
        # Achievements by type
        by_type = dict(
            queryset.values('type').annotate(count=Count('id')).values_list('type', 'count')
        )
        
        # Recent achievements (last 30 days)
        month_ago = timezone.now() - timedelta(days=30)
        recent_achievements = queryset.filter(earned_at__gte=month_ago).count()
        
        # Most popular achievement
        most_popular = queryset.values('type', 'title').annotate(
            count=Count('id')
        ).order_by('-count').first()
        
        # Average points per student
        avg_points_per_student = queryset.values('student').annotate(
            total=Sum('points')
        ).aggregate(average=Avg('total'))['average'] or 0
        
        return Response({
            'scope': scope,
            'summary': {
                'total_achievements': total_achievements,
                'total_points_awarded': total_points,
                'unique_students': unique_students,
                'recent_achievements_30days': recent_achievements,
                'average_points_per_student': round(avg_points_per_student, 2)
            },
            'by_type': by_type,
            'most_popular': most_popular,
            'achievement_types_available': len(AchievementService.ACHIEVEMENT_RULES)
        })
    
    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def student_progress(self, request):
        """
        Get detailed progress for a specific student.
        Shows earned and available achievements with progress.
        
        Query params:
        - student_id: required (admins/owners/instructors)
        - For students, shows their own progress
        """
        user = request.user
        student_id = request.query_params.get('student_id')
        
        # Determine which student to check
        if user.role == 'S':
            # Students can only check their own progress
            try:
                student_profile = StudentProfile.objects.get(user=user, status='A')
            except StudentProfile.DoesNotExist:
                return Response(
                    {'error': 'No active student profile found'},
                    status=status.HTTP_404_NOT_FOUND
                )
        else:
            # Admins/owners/instructors need student_id
            if not student_id:
                return Response(
                    {'error': 'student_id is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            try:
                student_profile = StudentProfile.objects.select_related('school', 'user').get(id=student_id)
            except StudentProfile.DoesNotExist:
                return Response(
                    {'error': 'Student not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Permission check
            if user.role == 'I':
                instructor_profile = user.student_profiles.filter(status='A').first()
                if not instructor_profile or instructor_profile.school != student_profile.school:
                    raise PermissionDenied("You can only view students in your school")
            
            if user.role == 'A' and not user.is_staff:
                if student_profile.school.owner != user:
                    raise PermissionDenied("You can only view students in your schools")
        
        # Get earned achievements
        earned_achievements = Achievement.objects.filter(student=student_profile).order_by('-earned_at')
        earned_serialized = self.get_serializer(earned_achievements, many=True).data
        
        # Get progress for all available achievements
        earned_types = set(earned_achievements.values_list('type', flat=True))
        
        available_with_progress = []
        for achievement_type, rule in AchievementService.ACHIEVEMENT_RULES.items():
            progress_data = self._calculate_progress(student_profile, achievement_type)
            
            available_with_progress.append({
                'type': achievement_type,
                'title': rule['title'],
                'description': rule['description'],
                'icon': rule['icon'],
                'points': rule['points'],
                'earned': achievement_type in earned_types,
                'progress': progress_data
            })
        
        # Summary statistics
        total_points = earned_achievements.aggregate(total=Sum('points'))['total'] or 0
        completion_rate = round((len(earned_types) / len(AchievementService.ACHIEVEMENT_RULES) * 100), 2)
        
        return Response({
            'student': {
                'id': student_profile.id,
                'name': student_profile.user.get_full_name() or student_profile.user.username,
                'school': student_profile.school.name,
                'status': student_profile.get_status_display()
            },
            'summary': {
                'earned_count': earned_achievements.count(),
                'total_available': len(AchievementService.ACHIEVEMENT_RULES),
                'completion_rate': completion_rate,
                'total_points': total_points
            },
            'earned_achievements': earned_serialized,
            'all_achievements_progress': available_with_progress
        })
    
    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def available_achievements(self, request):
        """
        Get list of all available achievement types with their requirements.
        """
        achievements_info = []
        
        for achievement_type, rule in AchievementService.ACHIEVEMENT_RULES.items():
            achievements_info.append({
                'type': achievement_type,
                'title': rule['title'],
                'description': rule['description'],
                'icon': rule['icon'],
                'points': rule['points'],
                'requirements': self._get_achievement_requirements(achievement_type)
            })
        
        return Response({
            'total_types': len(achievements_info),
            'achievements': achievements_info
        })
    
        # ==================== HELPER METHODS ====================
    
    def _calculate_progress(self, student, achievement_type):
        """
        Calculate progress towards a specific achievement.
        Returns dict with current value, target, and percentage.
        """
        from .models import Attendance
        
        if achievement_type == 'first_lesson':
            attended = Attendance.objects.filter(student=student, presence=True).exists()
            return {
                'current': 1 if attended else 0,
                'target': 1,
                'percentage': 100 if attended else 0,
                'unit': 'lesson'
            }
        
        elif achievement_type == 'theory_master':
            current = float(student.total_hours_theory)
            target = 50
            return {
                'current': current,
                'target': target,
                'percentage': min(round((current / target * 100), 2), 100),
                'unit': 'hours'
            }
        
        elif achievement_type == 'driving_ace':
            current = float(student.total_hours_driving)
            target = 40
            return {
                'current': current,
                'target': target,
                'percentage': min(round((current / target * 100), 2), 100),
                'unit': 'hours'
            }
        
        elif achievement_type == 'perfect_attendance':
            total_lessons = Attendance.objects.filter(student=student).count()
            present = Attendance.objects.filter(student=student, presence=True).count()
            
            if total_lessons >= 10:
                percentage = round((present / total_lessons * 100), 2) if total_lessons > 0 else 0
            else:
                percentage = 0
            
            return {
                'current': f"{present}/{total_lessons}",
                'target': "10 lessons with 100% attendance",
                'percentage': percentage if total_lessons >= 10 else round((total_lessons / 10 * 100), 2),
                'unit': 'lessons'
            }
        
        # Add more achievement types as needed
        else:
            return {
                'current': 0,
                'target': 1,
                'percentage': 0,
                'unit': 'unknown'
            }

    def _get_achievement_requirements(self, achievement_type):
        """
        Get human-readable requirements for an achievement.
        """
        requirements_map = {
            'first_lesson': 'Complete your first driving lesson',
            'theory_master': 'Complete 50 hours of theory lessons',
            'driving_ace': 'Complete 40 hours of driving practice',
            'perfect_attendance': 'Maintain 100% attendance for 10 consecutive lessons'
        }
        
        return requirements_map.get(achievement_type, 'Complete the requirements')
    
    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated, IsPlatformAdminOrSchoolOwner])
    def export(self, request):
        """
        Export achievements to CSV/Excel.
        """
        user = self.request.user
        queryset = self.get_queryset()
        

        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="achievements.csv"'
        
        writer = csv.writer(response)
        writer.writerow(['Student', 'School', 'Achievement', 'Points', 'Date Earned'])
        
    
        for achievement in queryset.select_related('student__user', 'student__school'):
            writer.writerow([
                achievement.student.user.get_full_name() or achievement.student.user.username,
                achievement.student.school.name,
                achievement.title,
                achievement.points,
                achievement.earned_at.strftime('%Y-%m-%d %H:%M')
            ])

            
        if user.role == 'A' and user.is_staff:
            return response
        elif user.role == 'A' and not user.is_staff:
            return response
        else:
            return Response(
                {'eroor':'You cannot export achievements to CSV/Excel'},
                status=status.HTTP_403_FORBIDDEN
            )

    
    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def badges(self, request):
        """
        Get visual badges for achievements.
        """
        user = request.user
        
        if user.role == 'S':
            try:
                student_profile = StudentProfile.objects.get(user=user, status='A')
                achievements = Achievement.objects.filter(student=student_profile)
            except StudentProfile.DoesNotExist:
                return Response({'error': 'Student profile not found'}, status=404)
        else:
            # Admins/instructors can see badges for a specific student
            student_id = request.query_params.get('student_id')
            if not student_id:
                return Response({'error': 'student_id required for non-students'}, status=400)
            
            try:
                student_profile = StudentProfile.objects.get(id=student_id)
                achievements = Achievement.objects.filter(student=student_profile)
            except StudentProfile.DoesNotExist:
                return Response({'error': 'Student not found'}, status=404)
        
        badges = []
        for achievement in achievements:
            badges.append({
                'id': achievement.id,
                'type': achievement.type,
                'title': achievement.title,
                'icon': achievement.icon,
                'earned_date': achievement.earned_at,
                'description': achievement.description,
                'badge_url': f'/static/badges/{achievement.type}.png'  # Customize this
            })
        
        return Response({
            'student': student_profile.user.username,
            'total_badges': len(badges),
            'badges': badges
        })


# DSS-12-create-CommunicationViewSet
class CommunicationTemplateViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing communication templates.
     
    Templates are reusable message formats for various notifications.
    
    Access Control:
    - Platform Admins: Full access to all templates
    - School Owners: Manage templates in their schools
    - Instructors: View templates in their school
    - Students: Cannot access templates
    """
    
    serializer_class = CommunicationTemplateSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter, DjangoFilterBackend]
    filterset_fields = ['school', 'template_type', 'is_active']
    search_fields = ['name', 'subject', 'body', 'template_type']
    ordering_fields = ['name', 'created_at', 'template_type']
    ordering = ['-created_at']

    def get_queryset(self):
        """Filter templates based on user role and school"""
        user = self.request.user
        if not user.is_authenticated:
            return CommunicationTemplate.objects.none()
        
        # Platform Admin (staff) sees all templates
        if user.role == 'A' and user.is_staff:
            return CommunicationTemplate.objects.all().select_related('school')
        
        # School Owner sees templates in their schools
        if user.role == 'A' and not user.is_staff:
            return CommunicationTemplate.objects.filter(
                school__owner=user
            ).select_related('school')
        
        # Instructor sees templates in their school
        if user.role == 'I':
            instructor_profile = user.student_profiles.filter(status='A').first()
            if instructor_profile:
                return CommunicationTemplate.objects.filter(
                    school=instructor_profile.school
                ).select_related('school')
        
        
        # Students cannot access templates
        return CommunicationTemplate.objects.none()
    
    def get_permissions(self):
        """Define permissions per action"""
        if self.action == 'create':
            return [IsAuthenticated(), IsPlatformAdminOrSchoolOwner()]
        
        elif self.action in ['update', 'partial_update']:
            return [IsAuthenticated(), IsPlatformAdminOrSchoolOwner()]
        
        elif self.action == 'destroy':
            return [IsAuthenticated(), IsPlatformAdminOrSchoolOwner()]
        
        elif self.action in ['duplicate', 'preview', 'toggle_active']:
            return [IsAuthenticated(), IsPlatformAdminOrSchoolOwner()]
        
        elif self.action in ['available_variables', 'by_type', 'usage_stats']:
            return [IsAuthenticated()]
        
        return [IsAuthenticated()]
    
    def perform_create(self, serializer):
        """Create template with validation"""
        user = self.request.user
        school = serializer.validated_data.get('school')
        
        # Platform admin can create for any school
        if user.role == 'A' and user.is_staff:
            serializer.save()
            return
        
        # School owner can only create for their own schools
        if user.role == 'A' and not user.is_staff:
            if school.owner != user:
                raise PermissionDenied("You can only create templates for your own schools")
            serializer.save()
            return
        
        raise PermissionDenied("You don't have permission to create templates")
    
    def perform_update(self, serializer):
        """Update template with permission checks"""
        user = self.request.user
        instance = self.get_object()
        
        # Platform admin can update any template
        if user.role == 'A' and user.is_staff:
            serializer.save()
            return
        
        # School owner can update templates in their schools
        if user.role == 'A' and not user.is_staff:
            if instance.school.owner != user:
                raise PermissionDenied("You can only update templates in your own schools")
            serializer.save()
            return
        
        raise PermissionDenied("You don't have permission to update this template")
    
    def perform_destroy(self, instance):
        """Delete template with permission checks"""
        user = self.request.user
        
        # Check if template is in use
        usage_count = instance.messages.filter(status='pending').count()
        if usage_count > 0:
            raise PermissionDenied(
                f"Cannot delete template. It has {usage_count} pending messages. "
                f"Please cancel or send those messages first, or set template to inactive."
            )
        
        # Platform admin can delete any template
        if user.role == 'A' and user.is_staff:
            instance.delete()
            return
        
        # School owner can delete templates in their schools
        if user.role == 'A' and not user.is_staff:
            if instance.school.owner != user:
                raise PermissionDenied("You can only delete templates in your own schools")
            instance.delete()
            return
        
        raise PermissionDenied("You don't have permission to delete this template")
    
    # ==================== CUSTOM ACTIONS ====================
    
    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def available_variables(self, request):
        """
        Get all available template variables with descriptions.
        
        GET /api/communication-templates/available_variables/
        """
        variables = CommunicationTemplateService.get_available_variables()
        
        return Response({
            'variables': variables,
            'total_variables': len(variables),
            'usage_example': {
                'subject': 'Hello {student_name}!',
                'body': 'Your progress in {school_name} is {progress_theory}% for theory.'
            }
        })
    
    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated, IsPlatformAdminOrSchoolOwner])
    @transaction.atomic
    def duplicate(self, request, pk=None):
        """
        Duplicate an existing template.
        
        POST /api/communication-templates/{id}/duplicate/
        Body: {"new_name": "Copy of Template Name"} (optional)
        """
        template = self.get_object()
        user = request.user
        

        # Check permissions
        if user.role == 'A' and not user.is_staff:
            if template.school.owner != user:
                raise PermissionDenied("You can only duplicate templates from your own schools")
        
        # Get new name
        new_name = request.data.get('new_name', f"Copy of {template.name}")
        
        # Check for duplicate name
        if CommunicationTemplate.objects.filter(
            school=template.school,
            name=new_name
        ).exists():
            return Response(
                {'error': 'A template with this name already exists in this school'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Create duplicate
        new_template = CommunicationTemplate.objects.create(
            school=template.school,
            name=new_name,
            template_type=template.template_type,
            subject=template.subject,
            body=template.body,
            is_active=False  # Start as inactive
        )
        
        serializer = self.get_serializer(new_template)
        
        return Response({
            'message': 'Template duplicated successfully',
            'original_template': template.id,
            'new_template': serializer.data
        }, status=status.HTTP_201_CREATED)
    
    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated, IsPlatformAdminOrSchoolOwner])
    def preview(self, request, pk=None):
        """
        Preview template with sample data.
        
        POST /api/communication-templates/{id}/preview/
        Body: {
            "student_id": 123  (optional - uses sample data if not provided)
        }
        """
        template = self.get_object()
        student_id = request.data.get('student_id')
        
        # Get student data or use sample data
        if student_id:
            try:
                student = StudentProfile.objects.select_related('user', 'school').get(id=student_id)
                
                # Check permissions
                user = request.user
                if user.role == 'A' and not user.is_staff:
                    if student.school.owner != user:
                        raise PermissionDenied("You can only preview with students from your schools")
                
                if user.role == 'I':
                    instructor_profile = user.student_profiles.filter(status='A').first()
                    if not instructor_profile or instructor_profile.school != student.school:
                        raise PermissionDenied("You can only preview with students from your school")
                
                # Real data
                data = {
                    'student_name': student.user.get_full_name() or student.user.username,
                    'progress_theory': f"{student.progress_theory}%",
                    'progress_driving': f"{student.progress_driving}%",
                    'school_name': student.school.name,
                    'license_type': student.get_license_type_display() if student.license_type else 'Not specified',
                    'total_hours_theory': student.total_hours_theory,
                    'total_hours_driving': student.total_hours_driving,
                    'instructor_name': 'Your Instructor',
                    'lesson_date': 'Next scheduled lesson',
                    'completion_date': student.completion_date or 'To be determined',
                }
            except StudentProfile.DoesNotExist:
                return Response(
                    {'error': 'Student not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
        else:
            # Sample data
            data = {
                'student_name': 'John Doe',
                'progress_theory': '75%',
                'progress_driving': '60%',
                'school_name': template.school.name,
                'license_type': 'Car',
                'total_hours_theory': 30,
                'total_hours_driving': 20,
                'instructor_name': 'Jane Smith',
                'lesson_date': (timezone.now() + timedelta(days=2)).strftime('%Y-%m-%d'),
                'completion_date': (timezone.now() + timedelta(days=60)).strftime('%Y-%m-%d'),
            }
        
        # Render template
        try:
            rendered_subject = template.subject.format(**data)
            rendered_body = template.body.format(**data)
        except KeyError as e:
            return Response(
                {'error': f'Template contains invalid variable: {str(e)}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        return Response({
            'template': {
                'id': template.id,
                'name': template.name,
                'type': template.template_type
            },
            'preview': {
                'subject': rendered_subject,
                'body': rendered_body
            },
            'data_used': data,
            'is_sample_data': not student_id
        })
    
    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated, IsPlatformAdminOrSchoolOwner])
    @transaction.atomic
    def toggle_active(self, request, pk=None):
        """
        Toggle template active status.
        
        POST /api/communication-templates/{id}/toggle_active/
        """
        template = self.get_object()
        user = request.user
        
        # Check permissions
        if user.role == 'A' and not user.is_staff:
            if template.school.owner != user:
                raise PermissionDenied("You can only toggle templates in your own schools")
        
        # Toggle status
        template.is_active = not template.is_active
        template.save()
        
        serializer = self.get_serializer(template)
        
        return Response({
            'message': f"Template {'activated' if template.is_active else 'deactivated'} successfully",
            'template': serializer.data
        })
    
    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def by_type(self, request):
        """
        Get templates grouped by type.
        
        GET /api/communication-templates/by_type/
        Query params:
        - school_id: Filter by school (admins only)
        """
        queryset = self.get_queryset()
        
        # Filter by school if provided (admin only)
        school_id = request.query_params.get('school_id')
        if school_id:
            user = request.user
            if user.role == 'A' and user.is_staff:
                queryset = queryset.filter(school_id=school_id)
            else:
                return Response(
                    {'error': 'Only platform admins can filter by school_id'},
                    status=status.HTTP_403_FORBIDDEN
                )
        
        # Group by type
        template_types = CommunicationTemplate.TEMPLATE_TYPES
        grouped = {}
        
        for type_code, type_name in template_types:
            templates = queryset.filter(template_type=type_code)
            serializer = self.get_serializer(templates, many=True)
            
            grouped[type_code] = {
                'type_name': type_name,
                'count': templates.count(),
                'active_count': templates.filter(is_active=True).count(),
                'templates': serializer.data
            }
        
        return Response({
            'grouped_templates': grouped,
            'total_types': len(template_types),
            'total_templates': queryset.count()
        })
    
    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def usage_stats(self, request):
        """
        Get template usage statistics.
        
        GET /api/communication-templates/usage_stats/
        """
        queryset = self.get_queryset()
        
        # Overall stats
        total_templates = queryset.count()
        active_templates = queryset.filter(is_active=True).count()
        
        # Usage by template
        templates_with_usage = queryset.annotate(
            message_count=Count('messages'),
            pending_count=Count('messages', filter=Q(messages__status='pending')),
            sent_count=Count('messages', filter=Q(messages__status='sent'))
        ).order_by('-message_count')[:10]
        
        most_used = []
        for template in templates_with_usage:
            most_used.append({
                'id': template.id,
                'name': template.name,
                'type': template.template_type,
                'total_messages': template.message_count,
                'pending_messages': template.pending_count,
                'sent_messages': template.sent_count
            })
        
        # Templates never used
        never_used = queryset.filter(messages__isnull=True).count()
        
        return Response({
            'summary': {
                'total_templates': total_templates,
                'active_templates': active_templates,
                'inactive_templates': total_templates - active_templates,
                'never_used': never_used
            },
            'most_used_templates': most_used,
            'total_messages_created': queryset.aggregate(
                total=Count('messages')
            )['total'] or 0
        })
    
    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated, IsPlatformAdminOrSchoolOwner])
    def my_school_templates(self, request):
        """
        Get templates for current user's school.
        Convenience endpoint for school owners and instructors.
        
        GET /api/communication-templates/my_school_templates/
        Query params:
        - template_type: Filter by type
        - active_only: true/false (default: false)
        """
        user = request.user
        
        # Get user's school
        if user.role == 'A' and not user.is_staff:
            # School owner - get all their schools' templates
            queryset = self.get_queryset()
        elif user.role == 'I':
            # Instructor - get their school's templates
            instructor_profile = user.student_profiles.filter(status='A').first()
            if not instructor_profile:
                return Response(
                    {'error': 'You are not associated with any active school'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            queryset = CommunicationTemplate.objects.filter(school=instructor_profile.school)
        else:
            return Response(
                {'error': 'This endpoint is only for school owners and instructors'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Apply filters
        template_type = request.query_params.get('template_type')
        if template_type:
            queryset = queryset.filter(template_type=template_type)
        
        active_only = request.query_params.get('active_only', 'false').lower() == 'true'
        if active_only:
            queryset = queryset.filter(is_active=True)
        
        # Serialize
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

# DSS-27-AutomatedMessageViewSet
class AutomatedMessageViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing automated messages.
    
    Messages are scheduled communications sent to students.
    
    Access Control:
    - Platform Admins: Full access to all messages
    - School Owners: Manage messages in their schools
    - Instructors: View and create messages for students in their school
    - Students: View their own messages (read-only)
    """
    
    serializer_class = AutomatedMessageSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter, DjangoFilterBackend]
    filterset_fields = ['student', 'template', 'status', 'template__school']
    search_fields = ['student__user__username', 'student__user__email', 'template__name']
    ordering_fields = ['scheduled_for', 'sent_at', 'created_at', 'status']
    ordering = ['-scheduled_for']

    def get_queryset(self):
        """Filter messages based on user role and school"""
        user = self.request.user
        if not user.is_authenticated:
            return AutomatedMessage.objects.none()
        
        # Platform Admin (staff) sees all messages
        if user.role == 'A' and user.is_staff:
            return AutomatedMessage.objects.all().select_related(
                'student__user', 'student__school', 'template'
            )
        
        # School Owner sees messages in their schools
        if user.role == 'A' and not user.is_staff:
            return AutomatedMessage.objects.filter(
                template__school__owner=user
            ).select_related('student__user', 'student__school', 'template')
        
        # Instructor sees messages for students in their school
        if user.role == 'I':
            instructor_profile = user.student_profiles.filter(status='A').first()
            if instructor_profile:
                return AutomatedMessage.objects.filter(
                    student__school=instructor_profile.school
                ).select_related('student__user', 'template')
        
        # Student sees only their own messages
        if user.role == 'S':
            student_profile = user.student_profiles.filter(status='A').first()
            if student_profile:
                return AutomatedMessage.objects.filter(
                    student=student_profile
                ).select_related('template')
        
        return AutomatedMessage.objects.none()
    
    def get_permissions(self):
        """Define permissions per action"""
        if self.action == 'create':
            return [IsAuthenticated(), IsPlatformAdminOrSchoolOwnerOrInstructor()]
        
        elif self.action in ['update', 'partial_update']:
            return [IsAuthenticated(), IsPlatformAdminOrSchoolOwnerOrInstructor()]
        
        elif self.action == 'destroy':
            return [IsAuthenticated(), IsPlatformAdminOrSchoolOwner()]
        
        elif self.action in ['cancel', 'pending', 'send_now', 'reschedule', 'bulk_create', 'bulk_cancel']:
            return [IsAuthenticated(), IsPlatformAdminOrSchoolOwnerOrInstructor()]
        
        elif self.action in ['my_messages', 'sent', 'failed', 'statistics']:
            return [IsAuthenticated()]
        
        return [IsAuthenticated()]
    
    def perform_create(self, serializer):
        """Create message with validation"""
        user = self.request.user
        student = serializer.validated_data.get('student')
        template = serializer.validated_data.get('template')
        
        # Platform admin can create for any student
        if user.role == 'A' and user.is_staff:
            serializer.save()
            return
        
        # School owner can create for students in their schools
        if user.role == 'A' and not user.is_staff:
            if student.school.owner != user or template.school.owner != user:
                raise PermissionDenied("Student and template must be from your schools")
            serializer.save()
            return
        
        # Instructor can create for students in their school
        if user.role == 'I':
            instructor_profile = user.student_profiles.filter(status='A').first()
            if not instructor_profile:
                raise PermissionDenied("You have no active school profile")
            
            if student.school != instructor_profile.school:
                raise PermissionDenied("You can only create messages for students in your school")
            
            if template.school != instructor_profile.school:
                raise PermissionDenied("Template must be from your school")
            
            serializer.save()
            return
        
        raise PermissionDenied("You don't have permission to create messages")
    
    def perform_update(self, serializer):
        """Update message with permission checks"""
        user = self.request.user
        instance = self.get_object()
        
        # Cannot update sent, delivered, or read messages
        if instance.status in ['sent', 'delivered', 'read']:
            raise PermissionDenied(f"Cannot update {instance.status} messages")
        
        # Platform admin can update any message
        if user.role == 'A' and user.is_staff:
            serializer.save()
            return
        
        # School owner can update messages in their schools
        if user.role == 'A' and not user.is_staff:
            if instance.template.school.owner != user:
                raise PermissionDenied("You can only update messages in your schools")
            serializer.save()
            return
        
        # Instructor can update messages in their school
        if user.role == 'I':
            instructor_profile = user.student_profiles.filter(status='A').first()
            if not instructor_profile or instructor_profile.school != instance.student.school:
                raise PermissionDenied("You can only update messages in your school")
            serializer.save()
            return
        
        raise PermissionDenied("You don't have permission to update this message")
    
    def perform_destroy(self, instance):
        """Delete message with permission checks"""
        user = self.request.user
        
        # Cannot delete sent messages
        if instance.status in ['sent', 'delivered', 'read']:
            raise PermissionDenied(f"Cannot delete {instance.status} messages")
        
        # Platform admin can delete any message
        if user.role == 'A' and user.is_staff:
            instance.delete()
            return
        
        # School owner can delete messages in their schools
        if user.role == 'A' and not user.is_staff:
            if instance.template.school.owner != user:
                raise PermissionDenied("You can only delete messages in your schools")
            instance.delete()
            return
        
        raise PermissionDenied("You don't have permission to delete this message")
    
    # ==================== CUSTOM ACTIONS ====================
    
    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def my_messages(self, request):
        """
        Get messages for the current student.
        
        GET /api/automated-messages/my_messages/
        Query params:
        - status: Filter by status
        - limit: Number of messages (default: 20)
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
        
        # Get messages
        queryset = AutomatedMessage.objects.filter(
            student=student_profile
        ).select_related('template').order_by('-scheduled_for')
        
        # Apply filters
        status_filter = request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        # Get statistics
        total_messages = queryset.count()
        pending_count = queryset.filter(status='pending').count()
        sent_count = queryset.filter(status='sent').count()
        
        # Paginate
        limit = min(int(request.query_params.get('limit', 20)), 100)
        queryset = queryset[:limit]
        
        serializer = self.get_serializer(queryset, many=True)
        
        return Response({
            'statistics': {
                'total_messages': total_messages,
                'pending': pending_count,
                'sent': sent_count
            },
            'messages': serializer.data
        })
    
    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated, IsPlatformAdminOrSchoolOwnerOrInstructor])
    def pending(self, request):
        """
        Get all pending messages.
        
        GET /api/automated-messages/pending/
        """
        queryset = self.get_queryset().filter(status='pending').order_by('scheduled_for')
        user = self.request.user
        # Separate overdue and upcoming
        now = timezone.now()
        overdue = queryset.filter(scheduled_for__lt=now)
        upcoming = queryset.filter(scheduled_for__gte=now)
        
        return Response({
            'overdue': {
                'count': overdue.count(),
                'messages': self.get_serializer(overdue[:10], many=True).data
            },
            'upcoming': {
                'count': upcoming.count(),
                'messages': self.get_serializer(upcoming[:20], many=True).data
            },
            'total_pending': queryset.count()
        })
    
    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated, IsPlatformAdminOrSchoolOwnerOrInstructor])
    def sent(self, request):
        """
        Get recently sent messages.
        
        GET /api/automated-messages/sent/
        Query params:
        - days: Number of days to look back (default: 7, max: 30)
        """
        days = min(int(request.query_params.get('days', 7)), 30)
        since = timezone.now() - timedelta(days=days)
        
        queryset = self.get_queryset().filter(
            status__in=['sent', 'delivered', 'read'],
            sent_at__gte=since
        ).order_by('-sent_at')
        
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated, IsPlatformAdminOrSchoolOwnerOrInstructor])
    def failed(self, request):
        """
        Get failed messages that need attention.
        
        GET /api/automated-messages/failed/
        """
        queryset = self.get_queryset().filter(status='failed').order_by('-created_at')
        
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response({
            'total_failed': queryset.count(),
            'messages': serializer.data
        })
    
    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated, IsPlatformAdminOrSchoolOwnerOrInstructor])
    @transaction.atomic
    def cancel(self, request, pk=None):
        """
        Cancel a pending message.
        
        POST /api/automated-messages/{id}/cancel/
        """
        message = self.get_object()
        user = request.user
        
        # Check permissions
        if user.role == 'I':
            instructor_profile = user.student_profiles.filter(status='A').first()
            if not instructor_profile or instructor_profile.school != message.student.school:
                raise PermissionDenied("You can only cancel messages in your school")
        
        if user.role == 'A' and not user.is_staff:
            if message.template.school.owner != user:
                raise PermissionDenied("You can only cancel messages in your schools")
        
        # Can only cancel pending messages
        if message.status != 'pending':
            return Response(
                {'error': f'Cannot cancel {message.status} message'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Delete the message
        message_id = message.id
        message.delete()
        
        return Response({
            'message': 'Message cancelled successfully',
            'cancelled_message_id': message_id
        })
    
    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated, IsPlatformAdminOrSchoolOwner])
    @transaction.atomic
    def send_now(self, request, pk=None):
        """
        Send a message immediately.
        
        POST /api/automated-messages/{id}/send_now/
        """
        message = self.get_object()
        user = request.user
        
        # Check permissions
        if user.role == 'A' and not user.is_staff:
            if message.template.school.owner != user:
                raise PermissionDenied("You can only send messages in your schools")
        
        if user.role == 'I':
            raise PermissionDenied("You cannot send messages")

        # Can only send pending messages
        if message.status != 'pending':
            return Response(
                {'error': f'Cannot send {message.status} message'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            # Send the message
            CommunicationService._send_single_message(message)
            
            # Update message status
            message.status = 'sent'
            message.sent_at = timezone.now()
            message.save()
            
            serializer = self.get_serializer(message)
            
            return Response({
                'message': 'Message sent successfully',
                'sent_message': serializer.data,
                'sent_at': message.sent_at
            })
            
        except Exception as e:
            message.status = 'failed'
            message.delivery_error = str(e)
            message.save()
            
            return Response({
                'error': f'Failed to send message: {str(e)}',
                'message_status': 'failed'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated, IsPlatformAdminOrSchoolOwnerOrInstructor])
    @transaction.atomic
    def reschedule(self, request, pk=None):
        """
        Reschedule a pending message.
        
        POST /api/automated-messages/{id}/reschedule/
        Body: {"new_time": "2024-12-31T10:00:00"}
        """
        message = self.get_object()
        user = request.user
        
        # Check permissions
        if user.role == 'I':
            instructor_profile = user.student_profiles.filter(status='A').first()
            if not instructor_profile or instructor_profile.school != message.student.school:
                raise PermissionDenied("You can only reschedule messages in your school")
        
        if user.role == 'A' and not user.is_staff:
            if message.template.school.owner != user:
                raise PermissionDenied("You can only reschedule messages in your schools")
        
        # Can only reschedule pending messages
        if message.status != 'pending':
            return Response(
                {'error': f'Cannot reschedule {message.status} message'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get new time
        new_time_str = request.data.get('new_time')
        if not new_time_str:
            return Response(
                {'error': 'new_time is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            new_time = timezone.datetime.fromisoformat(new_time_str.replace('Z', '+00:00'))
            if timezone.is_naive(new_time):
                new_time = timezone.make_aware(new_time)
        except (ValueError, TypeError):
            return Response(
                {'error': 'Invalid datetime format. Use ISO format (YYYY-MM-DDTHH:MM:SS)'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validate new time is in the future
        if new_time < timezone.now():
            return Response(
                {'error': 'Cannot reschedule to a past time'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Update message
        old_time = message.scheduled_for
        message.scheduled_for = new_time
        message.save()
        
        serializer = self.get_serializer(message)
        
        return Response({
            'message': 'Message rescheduled successfully',
            'rescheduled_message': serializer.data,
            'old_time': old_time,
            'new_time': new_time
        })
    
    @action(detail=False, methods=['post'], permission_classes=[IsAuthenticated, IsPlatformAdminOrSchoolOwnerOrInstructor])
    @transaction.atomic
    def bulk_create(self, request):
        """
        Create multiple messages at once.
        
        POST /api/automated-messages/bulk_create/
        Body: {
            "student_ids": [1, 2, 3],
            "template_id": 123,
            "scheduled_for": "2024-12-31T10:00:00",
            "custom_subject": "Optional custom subject",
            "custom_body": "Optional custom body"
        }
        """
        student_ids = request.data.get('student_ids', [])
        template_id = request.data.get('template_id')
        scheduled_for_str = request.data.get('scheduled_for')
        custom_subject = request.data.get('custom_subject')
        custom_body = request.data.get('custom_body')
        
        # Validate required fields
        if not student_ids:
            return Response(
                {'error': 'student_ids (array) is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if not template_id:
            return Response(
                {'error': 'template_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if not scheduled_for_str:
            return Response(
                {'error': 'scheduled_for is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Parse scheduled time
        try:
            scheduled_for = timezone.datetime.fromisoformat(scheduled_for_str.replace('Z', '+00:00'))
            if timezone.is_naive(scheduled_for):
                scheduled_for = timezone.make_aware(scheduled_for)
        except (ValueError, TypeError):
            return Response(
                {'error': 'Invalid datetime format for scheduled_for'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validate time is in the future
        if scheduled_for < timezone.now():
            return Response(
                {'error': 'scheduled_for must be in the future'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get template
        try:
            template = CommunicationTemplate.objects.get(id=template_id)
        except CommunicationTemplate.DoesNotExist:
            return Response(
                {'error': 'Template not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Get students
        students = StudentProfile.objects.filter(id__in=student_ids).select_related('user', 'school')
        
        if not students.exists():
            return Response(
                {'error': 'No valid students found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Check permissions
        user = request.user
        if user.role == 'I':
            instructor_profile = user.student_profiles.filter(status='A').first()
            if not instructor_profile:
                return Response(
                    {'error': 'You have no active school profile'},
                    status=status.HTTP_403_FORBIDDEN
                )
            
            invalid_students = students.exclude(school=instructor_profile.school)
            if invalid_students.exists():
                return Response(
                    {'error': 'You cannot create messages for students from another school'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Filter students to only those in instructor's school
            #student = students.filter(school=instructor_profile.school)
            if template.school != instructor_profile.school:
                return Response(
                    {'error': 'Template must be from your school'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        elif user.role == 'A' and not user.is_staff:
            # School owner - check all students and template are from their schools
            for student in students:
                if student.school.owner != user:
                    return Response(
                        {'error': f'Student {student.id} is not from your school'},
                        status=status.HTTP_403_FORBIDDEN
                    )
            
            if template.school.owner != user:
                return Response(
                    {'error': 'Template is not from your school'},
                    status=status.HTTP_403_FORBIDDEN
                )
        
        # Create messages
        created_messages = []
        skipped_students = []
        
        for student in students:
            # Check if similar message already exists
            existing = AutomatedMessage.objects.filter(
                student=student,
                template=template,
                scheduled_for=scheduled_for
            ).exists()
            
            if existing:
                skipped_students.append({
                    'student_id': student.id,
                    'reason': 'Similar message already scheduled'
                })
                continue
            
            # Create message
            message = AutomatedMessage.objects.create(
                student=student,
                template=template,
                scheduled_for=scheduled_for,
                status='pending'
            )
            
            created_messages.append({
                'student_id': student.id,
                'student_name': student.user.get_full_name() or student.user.username,
                'message_id': message.id
            })
        
        return Response({
            'message': f'Created {len(created_messages)} messages',
            'summary': {
                'requested': len(student_ids),
                'created': len(created_messages),
                'skipped': len(skipped_students)
            },
            'created_messages': created_messages,
            'skipped_students': skipped_students,
            'scheduled_for': scheduled_for,
            'template': template.name
        }, status=status.HTTP_201_CREATED)
    
    @action(detail=False, methods=['post'], permission_classes=[IsAuthenticated, IsPlatformAdminOrSchoolOwner])
    @transaction.atomic
    def bulk_cancel(self, request):
        """
        Cancel multiple messages.
        
        POST /api/automated-messages/bulk_cancel/
        Body: {
            "message_ids": [1, 2, 3],
            "reason": "Optional reason"
        }
        """
        message_ids = request.data.get('message_ids', [])
        reason = request.data.get('reason', 'No reason provided')
        
        if not message_ids:
            return Response(
                {'error': 'message_ids (array) is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get messages
        messages = AutomatedMessage.objects.filter(id__in=message_ids).select_related(
            'student', 'template'
        )
        
        if not messages.exists():
            return Response(
                {'error': 'No messages found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Check permissions
        user = request.user
        cancelled_messages = []
        failed_messages = []
        
        for message in messages:
            # Check if user can cancel this message
            can_cancel = False
            if user.role == 'A' and user.is_staff:
                can_cancel = True
            elif user.role == 'A' and not user.is_staff:
                can_cancel = message.template.school.owner == user
            
            if not can_cancel:
                failed_messages.append({
                    'message_id': message.id,
                    'reason': 'Permission denied'
                })
                continue
            
            # Can only cancel pending messages
            if message.status != 'pending':
                failed_messages.append({
                    'message_id': message.id,
                    'reason': f'Message status is {message.status}'
                })
                continue
            
            # Cancel message
            message_id = message.id
            message.delete()
            
            cancelled_messages.append({
                'message_id': message_id,
                'student_id': message.student.id,
                'template_id': message.template.id
            })
        
        return Response({
            'message': f'Cancelled {len(cancelled_messages)} messages',
            'summary': {
                'requested': len(message_ids),
                'cancelled': len(cancelled_messages),
                'failed': len(failed_messages)
            },
            'cancelled_messages': cancelled_messages,
            'failed_messages': failed_messages,
            'cancellation_reason': reason
        })
    
    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def statistics(self, request):
        """
        Get messaging statistics.
        
        GET /api/automated-messages/statistics/
        Query params:
        - school_id: Filter by school (admins only)
        - days: Number of days to analyze (default: 30, max: 90)
        """
        queryset = self.get_queryset()
        
        # Filter by school if provided (admin only)
        school_id = request.query_params.get('school_id')
        if school_id:
            user = request.user
            if user.role == 'A' and user.is_staff:
                queryset = queryset.filter(template__school_id=school_id)
            else:
                return Response(
                    {'error': 'Only platform admins can filter by school_id'},
                    status=status.HTTP_403_FORBIDDEN
                )
        
        # Time range
        days = min(int(request.query_params.get('days', 30)), 90)
        since = timezone.now() - timedelta(days=days)
        
        # Overall statistics
        total_messages = queryset.filter(created_at__gte=since).count()
        
        # Messages by status
        by_status = dict(
            queryset.filter(created_at__gte=since)
            .values('status')
            .annotate(count=Count('id'))
            .values_list('status', 'count')
        )
        
        # Messages by template type
        by_template_type = dict(
            queryset.filter(created_at__gte=since)
            .values('template__template_type')
            .annotate(count=Count('id'))
            .values_list('template__template_type', 'count')
        )
        
        # Daily message volume (last 7 days)
        daily_volume = []
        for i in range(7):
            day = timezone.now() - timedelta(days=i)
            day_start = day.replace(hour=0, minute=0, second=0, microsecond=0)
            day_end = day.replace(hour=23, minute=59, second=59, microsecond=999999)
            
            count = queryset.filter(
                created_at__range=[day_start, day_end]
            ).count()
            
            daily_volume.append({
                'date': day.date(),
                'messages_created': count
            })
        
        # Delivery success rate
        successful = queryset.filter(
            status__in=['sent', 'delivered', 'read'],
            created_at__gte=since
        ).count()
        
        total_with_status = sum(by_status.values()) if by_status else 0
        delivery_rate = round((successful / total_with_status * 100), 2) if total_with_status > 0 else 0
        
        # Templates with most messages
        top_templates = queryset.filter(created_at__gte=since).values(
            'template__id',
            'template__name',
            'template__template_type'
        ).annotate(
            message_count=Count('id')
        ).order_by('-message_count')[:5]
        
        return Response({
            'period': {
                'days': days,
                'since': since.date(),
                'until': timezone.now().date()
            },
            'summary': {
                'total_messages': total_messages,
                'delivery_success_rate': f'{delivery_rate}%',
                'pending_messages': by_status.get('pending', 0),
                'failed_messages': by_status.get('failed', 0)
            },
            'by_status': by_status,
            'by_template_type': by_template_type,
            'daily_volume': daily_volume,
            'top_templates': list(top_templates),
            'successful_messages': successful,
            'total_analyzed': total_with_status
        })
    
    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated, IsPlatformAdminOrSchoolOwnerOrInstructor])
    def upcoming_schedule(self, request):
        """
        Get upcoming message schedule.
        
        GET /api/automated-messages/upcoming_schedule/
        Query params:
        - days: Number of days ahead (default: 7, max: 30)
        - student_id: Filter by student (optional)
        - template_type: Filter by template type (optional)
        """
        days = min(int(request.query_params.get('days', 7)), 30)
        end_date = timezone.now() + timedelta(days=days)
        
        queryset = self.get_queryset().filter(
            status='pending',
            scheduled_for__lte=end_date
        ).order_by('scheduled_for')
        
        # Apply additional filters
        student_id = request.query_params.get('student_id')
        if student_id:
            queryset = queryset.filter(student_id=student_id)
        
        template_type = request.query_params.get('template_type')
        if template_type:
            queryset = queryset.filter(template__template_type=template_type)
        
        # Group by day
        schedule_by_day = {}
        for message in queryset:
            day_key = message.scheduled_for.date().isoformat()
            if day_key not in schedule_by_day:
                schedule_by_day[day_key] = []
            
            schedule_by_day[day_key].append({
                'id': message.id,
                'scheduled_for': message.scheduled_for,
                'student': {
                    'id': message.student.id,
                    'name': message.student.user.get_full_name() or message.student.user.username
                },
                'template': {
                    'id': message.template.id,
                    'name': message.template.name,
                    'type': message.template.template_type
                }
            })
        
        # Calculate daily counts
        daily_counts = {
            day: len(messages) for day, messages in schedule_by_day.items()
        }
        
        # Today's count
        today = timezone.now().date()
        today_count = sum(
            1 for message in queryset 
            if message.scheduled_for.date() == today
        )
        
        return Response({
            'period': {
                'days': days,
                'start': timezone.now().date(),
                'end': end_date.date()
            },
            'summary': {
                'total_scheduled': queryset.count(),
                'scheduled_today': today_count,
                'days_with_schedule': len(schedule_by_day)
            },
            'daily_counts': daily_counts,
            'schedule_by_day': schedule_by_day,
            'today': today.isoformat()
        })
    
    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def summary(self, request):
        """
        Get summary of messages for the current user.
        Role-specific summary.
        
        GET /api/automated-messages/summary/
        """
        user = request.user

        if user.role == 'S':
            # Student summary
            try:
                student_profile = StudentProfile.objects.get(user=user, status='A')
            except StudentProfile.DoesNotExist:
                return Response(
                    {'error': 'No active student profile found'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            messages = AutomatedMessage.objects.filter(student=student_profile)

            recent_unread_qs = messages.filter(
                status__in=['sent', 'delivered'],
                sent_at__isnull=False
            ).order_by('-sent_at')[:5]

            serializer = self.get_serializer(recent_unread_qs, many=True)

            summary = {
                'statistics': {
                    'total_messages': messages.count(),
                    'pending': messages.filter(status='pending').count(),
                    'read': messages.filter(status='read').count(),
                    'unread_sent': messages.filter(status='sent').count(),
                },
                'recent_unread': serializer.data
            }

            return Response(summary)

        
        elif user.role == 'I':
            # Instructor summary
            instructor_profile = user.student_profiles.filter(status='A').first()
            if not instructor_profile:
                return Response(
                    {'error': 'You are not associated with any active school'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            messages = AutomatedMessage.objects.filter(
                student__school=instructor_profile.school
            )
            
            # Messages by template type for instructor's school
            by_type = dict(
                messages.values('template__template_type')
                .annotate(count=Count('id'))
                .values_list('template__template_type', 'count')
            )
            
            # Recent messages to students taught by this instructor
            from .models import Attendance
            students_taught = Attendance.objects.filter(
                lesson__instructor=user,
                presence=True
            ).values_list('student', flat=True).distinct()
            
            recent_to_my_students = messages.filter(
                student__in=students_taught
            ).order_by('-created_at')[:10]
            
            summary = {
                'school': instructor_profile.school.name,
                'total_messages_in_school': messages.count(),
                'pending_in_school': messages.filter(status='pending').count(),
                'messages_by_type': by_type,
                'my_students': {
                    'total_students': len(students_taught),
                    'recent_messages': self.get_serializer(recent_to_my_students, many=True).data
                }
            }
            
            return Response(summary)
        
        elif user.role == 'A' and not user.is_staff:
            # School owner summary
            messages = AutomatedMessage.objects.filter(
                template__school__owner=user
            )
            
            # School-level statistics
            schools = DrivingSchool.objects.filter(owner=user)
            school_stats = []
            
            for school in schools:
                school_messages = messages.filter(template__school=school)
                school_stats.append({
                    'school_id': school.id,
                    'school_name': school.name,
                    'total_messages': school_messages.count(),
                    'pending': school_messages.filter(status='pending').count(),
                    'failed': school_messages.filter(status='failed').count(),
                    'top_template': school_messages.values('template__name')
                        .annotate(count=Count('id'))
                        .order_by('-count')
                        .first()
                })
            
            summary = {
                'total_messages_across_schools': messages.count(),
                'total_schools': schools.count(),
                'school_statistics': school_stats,
                'pending_messages': messages.filter(status='pending').count(),
                'failed_messages': messages.filter(status='failed').count(),
                'recent_messages': self.get_serializer(
                    messages.order_by('-created_at')[:10], many=True
                ).data
            }
            
            return Response(summary)
        
        else:
            # Platform admin summary
            messages = AutomatedMessage.objects.all()
            
            summary = {
                'total_messages': messages.count(),
                'messages_today': messages.filter(
                    created_at__date=timezone.now().date()
                ).count(),
                'by_status': dict(
                    messages.values('status')
                    .annotate(count=Count('id'))
                    .values_list('status', 'count')
                ),
                'by_school': dict(
                    messages.values('template__school__name')
                    .annotate(count=Count('id'))
                    .values_list('template__school__name', 'count')
                ),
                'recent_activity': self.get_serializer(
                    messages.order_by('-created_at')[:20], many=True
                ).data
            }
            
            return Response(summary)

# DSS-13-Create-AnalyticsViewSet
class SchoolAnalyticsViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing school analytics.
    
    Provides comprehensive analytics and reporting for driving schools.
    
    Access Control:
    - Platform Admins: Full access to all school analytics
    - School Owners: View and manage analytics for their schools
    - Instructors: View analytics for their school (read-only)
    - Students: Cannot access analytics
    """
    
    serializer_class = SchoolAnalyticsSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter, DjangoFilterBackend]
    filterset_fields = ['school', 'date']
    search_fields = ['school__name']
    ordering_fields = ['date', 'total_students', 'active_students', 'completion_rate', 'revenue']
    ordering = ['-date']

    def get_queryset(self):
        """Filter analytics based on user role and school"""
        user = self.request.user
        if not user.is_authenticated:
            return SchoolAnalytics.objects.none()
        
        # Platform Admin (staff) sees all analytics
        if user.role == 'A' and user.is_staff:
            return SchoolAnalytics.objects.all().select_related('school')
        
        # School Owner sees analytics for their schools
        if user.role == 'A' and not user.is_staff:
            return SchoolAnalytics.objects.filter(
                school__owner=user
            ).select_related('school')
        
        # Instructor sees analytics for their school
        if user.role == 'I':
            instructor_profile = user.student_profiles.filter(status='A').first()
            if instructor_profile:
                return SchoolAnalytics.objects.filter(
                    school=instructor_profile.school
                ).select_related('school')
        

        # Students cannot access analytics
        if user.role == 'S':
            return Response("Students cannot access analytics")
        
    
        return SchoolAnalytics.objects.none()
    
    def get_permissions(self):
        """Define permissions per action"""
        if self.action == 'create':
            return [IsAuthenticated(), IsPlatformAdminOrSchoolOwner()]
        
        elif self.action in ['update', 'partial_update']:
            return [IsAuthenticated(), IsPlatformAdminOrSchoolOwner()]
        
        elif self.action == 'destroy':
            return [IsAuthenticated(), IsPlatformAdmin()]
        
        elif self.action in ['generate_daily', 'refresh', 'bulk_generate','export','predictions','system_health','comparison']:
            return [IsAuthenticated(), IsPlatformAdminOrSchoolOwner()]
        
        elif self.action in ['dashboard', 'trends']:
            return [IsAuthenticated(), IsPlatformAdminOrSchoolOwnerOrInstructor()]
        
        elif self.action == 'system_health':
            return [IsAuthenticated(), IsPlatformAdmin()]

        return [IsAuthenticated()]
    
    def perform_create(self, serializer):
        """Create analytics with validation"""
        user = self.request.user
        school = serializer.validated_data.get('school')
        
        # Platform admin can create for any school
        if user.role == 'A' and user.is_staff:
            serializer.save()
            return
        
        # School owner can only create for their own schools
        if user.role == 'A' and not user.is_staff:
            if school.owner != user:
                raise PermissionDenied("You can only create analytics for your own schools")
            serializer.save()
            return
        
        raise PermissionDenied("You don't have permission to create analytics")
    
    def perform_update(self, serializer):
        """Update analytics with permission checks"""
        user = self.request.user
        instance = self.get_object()
        
        # Platform admin can update any analytics
        if user.role == 'A' and user.is_staff:
            serializer.save()
            return
        
        # School owner can update analytics for their schools
        if user.role == 'A' and not user.is_staff:
            if instance.school.owner != user:
                raise PermissionDenied("You can only update analytics for your own schools")
            serializer.save()
            return
        
        raise PermissionDenied("You don't have permission to update this analytics record")
    
    def perform_destroy(self, instance):
        """Delete analytics with permission checks"""
        user = self.request.user
        
        # Only platform admin can delete analytics
        if user.role == 'A' and user.is_staff:
            instance.delete()
            return
        
        raise PermissionDenied("Only platform administrators can delete analytics records")
    
    # ==================== CUSTOM ACTIONS ====================
    
    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated, IsPlatformAdminOrSchoolOwnerOrInstructor])
    def dashboard(self, request):
        """
        Get comprehensive dashboard data for a school.
        
        GET /api/school-analytics/dashboard/
        Query params:
        - school_id: Required for platform admins, optional for school owners
        - date_range: 'today', 'week', 'month', 'year' (default: 'month')
        """
        user = request.user
        school_id = request.query_params.get('school_id')
        date_range = request.query_params.get('date_range', 'month')
        
        # Determine school
        if user.role == 'A' and user.is_staff:
            # Platform admin must provide school_id
            if not school_id:
                return Response(
                    {'error': 'school_id is required for platform admins'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            try:
                school = DrivingSchool.objects.get(id=school_id)
            except DrivingSchool.DoesNotExist:
                return Response(
                    {'error': 'School not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
        
        elif user.role == 'A' and not user.is_staff:
            # School owner - use provided school_id or their first school
            if school_id:
                try:
                    school = DrivingSchool.objects.get(id=school_id, owner=user)
                except DrivingSchool.DoesNotExist:
                    return Response(
                        {'error': 'School not found or you do not own this school'},
                        status=status.HTTP_404_NOT_FOUND
                    )
            else:
                school = DrivingSchool.objects.filter(owner=user).first()
                if not school:
                    return Response(
                        {'error': 'You do not own any schools'},
                        status=status.HTTP_404_NOT_FOUND
                    )
        
        elif user.role == 'I':
            # Instructor - use their school
            instructor_profile = user.student_profiles.filter(status='A').first()
            if not instructor_profile:
                return Response(
                    {'error': 'You are not associated with any active school'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            school = instructor_profile.school
        
        else:
            return Response(
                {'error': 'Invalid user role for this endpoint'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Calculate date range
        today = timezone.now().date()
        if date_range == 'today':
            start_date = today
            end_date = today
        elif date_range == 'week':
            start_date = today - timedelta(days=7)
            end_date = today
        elif date_range == 'year':
            start_date = today - timedelta(days=365)
            end_date = today
        else:  # month (default)
            start_date = today - timedelta(days=30)
            end_date = today
        
        # Get analytics data
        analytics_records = SchoolAnalytics.objects.filter(
            school=school,
            date__range=[start_date, end_date]
        ).order_by('date')
        
        # Current metrics (most recent data)
        latest_analytics = analytics_records.last()
        
        if not latest_analytics:
            # Generate analytics if none exist
            latest_analytics = AnalyticsService.generate_daily_analytics(school, today)
        
        # Student metrics
        total_students = StudentProfile.objects.filter(
            school=school,
            user__role='S'
        ).count()
        
        active_students = StudentProfile.objects.filter(
            school=school,
            user__role='S',
            status='A'
        ).count()
        
        completed_students = StudentProfile.objects.filter(
            school=school,
            user__role='S',
            status='C'
        ).count()
        
        # Instructor metrics
        total_instructors = StudentProfile.objects.filter(
            school=school,
            user__role='I',
            status='A'
        ).count()
        
        # Lesson metrics
        lessons_this_period = Lesson.objects.filter(
            school=school,
            date__range=[timezone.make_aware(timezone.datetime.combine(start_date, timezone.datetime.min.time())),
                        timezone.make_aware(timezone.datetime.combine(end_date, timezone.datetime.max.time()))]
        )
        
        total_lessons = lessons_this_period.count()
        completed_lessons = lessons_this_period.filter(status='C').count()
        scheduled_lessons = lessons_this_period.filter(status='S').count()
        
        # Average rating
        avg_rating = Feedback.objects.filter(
            lesson__school=school,
            created_at__date__range=[start_date, end_date]
        ).aggregate(avg=Avg('rating'))['avg'] or 0
        
        # Revenue trend (last 7 days)
        revenue_trend = []
        for i in range(7):
            day = today - timedelta(days=6-i)
            day_analytics = analytics_records.filter(date=day).first()
            revenue_trend.append({
                'date': day,
                'revenue': float(day_analytics.revenue) if day_analytics else 0
            })
        
        # Student growth trend (last 7 days)
        student_trend = []
        for i in range(7):
            day = today - timedelta(days=6-i)
            day_analytics = analytics_records.filter(date=day).first()
            student_trend.append({
                'date': day,
                'active_students': day_analytics.active_students if day_analytics else 0,
                'new_students': day_analytics.new_students if day_analytics else 0
            })
        
        # Top performing students (by completion percentage)
        top_students = StudentProfile.objects.filter(
            school=school,
            user__role='S',
            status='A'
        ).annotate(
            completion=((F('progress_theory') + F('progress_driving')) / 2)
        ).order_by('-completion')[:5]
        
        top_students_data = [{
            'id': student.id,
            'name': student.user.get_full_name() or student.user.username,
            'completion_percentage': round((student.progress_theory + student.progress_driving) / 2, 2),
            'total_hours': student.total_hours_theory + student.total_hours_driving
        } for student in top_students]
        
        # Recent feedback
        recent_feedback = Feedback.objects.filter(
            lesson__school=school
        ).select_related('student__user', 'lesson__instructor').order_by('-created_at')[:5]
        
        recent_feedback_data = [{
            'id': feedback.id,
            'student': feedback.student.user.get_full_name() or feedback.student.user.username,
            'lesson': feedback.lesson.title,
            'rating': feedback.rating,
            'comment': feedback.comment[:100] if feedback.comment else '',
            'created_at': feedback.created_at
        } for feedback in recent_feedback]
        
        # Instructor performance
        instructor_stats = []
        instructors = User.objects.filter(
            role='I',
            student_profiles__school=school,
            student_profiles__status='A'
        ).distinct()
        
        for instructor in instructors:
            lessons_taught = Lesson.objects.filter(
                instructor=instructor,
                school=school,
                date__range=[timezone.make_aware(timezone.datetime.combine(start_date, timezone.datetime.min.time())),
                            timezone.make_aware(timezone.datetime.combine(end_date, timezone.datetime.max.time()))]
            ).count()
            
            avg_instructor_rating = Feedback.objects.filter(
                lesson__instructor=instructor,
                lesson__school=school
            ).aggregate(avg=Avg('rating'))['avg'] or 0
            
            instructor_stats.append({
                'id': instructor.id,
                'name': instructor.get_full_name() or instructor.username,
                'lessons_taught': lessons_taught,
                'average_rating': round(avg_instructor_rating, 2)
            })
        
        # Compile dashboard data
        dashboard_data = {
            'school': {
                'id': school.id,
                'name': school.name,
                'email': school.email
            },
            'period': {
                'range': date_range,
                'start_date': start_date,
                'end_date': end_date
            },
            'current_metrics': {
                'total_students': total_students,
                'active_students': active_students,
                'completed_students': completed_students,
                'total_instructors': total_instructors,
                'completion_rate': round(latest_analytics.completion_rate, 2) if latest_analytics else 0,
                'average_rating': round(avg_rating, 2),
                'instructor_utilization': round(latest_analytics.instructor_utilization, 2) if latest_analytics else 0
            },
            'lessons': {
                'total': total_lessons,
                'completed': completed_lessons,
                'scheduled': scheduled_lessons,
                'completion_rate': round((completed_lessons / total_lessons * 100), 2) if total_lessons > 0 else 0
            },
            'revenue': {
                'total': float(latest_analytics.revenue) if latest_analytics else 0,
                'trend': revenue_trend
            },
            'students': {
                'trend': student_trend,
                'top_performers': top_students_data
            },
            'instructors': instructor_stats,
            'recent_feedback': recent_feedback_data
        }
        
        return Response(dashboard_data)
    
    @action(detail=False, methods=['post'], permission_classes=[IsAuthenticated, IsPlatformAdminOrSchoolOwner])
    @transaction.atomic
    def generate_daily(self, request):
        """
        Generate daily analytics for a school.
        
        POST /api/school-analytics/generate_daily/
        Body: {
            "school_id": 123,
            "date": "2024-12-31" (optional, defaults to today)
        }
        """
        user = request.user
        school_id = request.data.get('school_id')
        date_str = request.data.get('date')
        
        # Validate school_id
        if not school_id:
            return Response(
                {'error': 'school_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get school
        try:
            school = DrivingSchool.objects.get(id=school_id)
        except DrivingSchool.DoesNotExist:
            return Response(
                {'error': 'School not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Check permissions
        if user.role == 'A' and not user.is_staff:
            if school.owner != user:
                raise PermissionDenied("You can only generate analytics for your own schools")
        
        # Parse date
        if date_str:
            try:
                target_date = timezone.datetime.strptime(date_str, '%Y-%m-%d').date()
            except ValueError:
                return Response(
                    {'error': 'Invalid date format. Use YYYY-MM-DD'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        else:
            target_date = timezone.now().date()
        
        # Generate analytics
        analytics = AnalyticsService.generate_daily_analytics(school, target_date, force_refresh=True)
        
        serializer = self.get_serializer(analytics)
        
        return Response({
            'message': 'Analytics generated successfully',
            'analytics': serializer.data
        }, status=status.HTTP_201_CREATED)
    
    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated, IsPlatformAdminOrSchoolOwner])
    @transaction.atomic
    def refresh(self, request, pk=None):
        """
        Refresh existing analytics record.
        
        POST /api/school-analytics/{id}/refresh/
        """
        analytics = self.get_object()
        user = request.user
        
        # Check permissions
        if user.role == 'A' and not user.is_staff:
            if analytics.school.owner != user:
                raise PermissionDenied("You can only refresh analytics for your own schools")
        
        # Refresh analytics
        refreshed_analytics = AnalyticsService.generate_daily_analytics(
            analytics.school, 
            analytics.date, 
            force_refresh=True
        )
        
        serializer = self.get_serializer(refreshed_analytics)
        
        return Response({
            'message': 'Analytics refreshed successfully',
            'analytics': serializer.data
        })
    
    @action(detail=False, methods=['post'], permission_classes=[IsAuthenticated, IsPlatformAdminOrSchoolOwner])
    @transaction.atomic
    def bulk_generate(self, request):
        """
        Generate analytics for multiple schools or date range.
        
        POST /api/school-analytics/bulk_generate/
        Body: {
            "school_ids": [1, 2, 3], (optional, all schools if not provided)
            "start_date": "2024-01-01",
            "end_date": "2024-12-31"
        }
        """
        user = request.user
        school_ids = request.data.get('school_ids', [])
        start_date_str = request.data.get('start_date')
        end_date_str = request.data.get('end_date')
        
        # Validate dates
        if not start_date_str or not end_date_str:
            return Response(
                {'error': 'start_date and end_date are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            start_date = timezone.datetime.strptime(start_date_str, '%Y-%m-%d').date()
            end_date = timezone.datetime.strptime(end_date_str, '%Y-%m-%d').date()
        except ValueError:
            return Response(
                {'error': 'Invalid date format. Use YYYY-MM-DD'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if end_date < start_date:
            return Response(
                {'error': 'end_date must be after start_date'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Limit date range to prevent performance issues
        days_diff = (end_date - start_date).days
        if days_diff > 90:
            return Response(
                {'error': 'Date range cannot exceed 90 days'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get schools
        if school_ids:
            schools = DrivingSchool.objects.filter(id__in=school_ids)
            
            # Check permissions
            if user.role == 'A' and not user.is_staff:
                schools = schools.filter(owner=user)
                if schools.count() != len(school_ids):
                    return Response(
                        {'error': 'Some schools do not belong to you'},
                        status=status.HTTP_403_FORBIDDEN
                    )
        else:
            # Generate for all accessible schools
            if user.role == 'A' and user.is_staff:
                schools = DrivingSchool.objects.all()
            else:
                schools = DrivingSchool.objects.filter(owner=user)
        
        if not schools.exists():
            return Response(
                {'error': 'No schools found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Generate analytics
        generated_count = 0
        skipped_count = 0
        
        for school in schools:
            current_date = start_date
            while current_date <= end_date:
                # Check if analytics already exists
                exists = SchoolAnalytics.objects.filter(
                    school=school,
                    date=current_date
                ).exists()
                
                if not exists:
                    AnalyticsService.generate_daily_analytics(school, current_date)
                    generated_count += 1
                else:
                    skipped_count += 1
                
                current_date += timedelta(days=1)
        
        return Response({
            'message': f'Bulk analytics generation completed',
            'summary': {
                'schools_processed': schools.count(),
                'date_range_days': days_diff + 1,
                'records_generated': generated_count,
                'records_skipped': skipped_count,
                'total_records': generated_count + skipped_count
            }
        }, status=status.HTTP_201_CREATED)
    
    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated, IsPlatformAdminOrSchoolOwnerOrInstructor])
    def trends(self, request):
        """
        Get trend analysis for a school.
        
        GET /api/school-analytics/trends/
        Query params:
        - school_id: Required
        - metric: 'students', 'revenue', 'completion_rate', 'rating' (default: 'students')
        - days: Number of days (default: 30, max: 365)
        """
        school_id = request.query_params.get('school_id')
        metric = request.query_params.get('metric', 'students')
        days = min(int(request.query_params.get('days', 30)), 365)
        
        # Validate school_id
        if not school_id:
            return Response(
                {'error': 'school_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get school
        try:
            school = DrivingSchool.objects.get(id=school_id)
        except DrivingSchool.DoesNotExist:
            return Response(
                {'error': 'School not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Check permissions
        user = request.user
        if user.role == 'A' and not user.is_staff:
            if school.owner != user:
                raise PermissionDenied("You can only view trends for your own schools")
        
        if user.role == 'I':
            instructor_profile = user.student_profiles.filter(status='A').first()
            if not instructor_profile or instructor_profile.school != school:
                raise PermissionDenied("You can only view trends for your school")
        
        # Get analytics data
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=days-1)
        
        analytics_records = SchoolAnalytics.objects.filter(
            school=school,
            date__range=[start_date, end_date]
        ).order_by('date')
        
        # Build trend data based on metric
        trend_data = []
        
        for record in analytics_records:
            data_point = {'date': record.date}
            
            if metric == 'students':
                data_point['total_students'] = record.total_students
                data_point['active_students'] = record.active_students
                data_point['new_students'] = record.new_students
            
            elif metric == 'revenue':
                data_point['revenue'] = float(record.revenue)
            
            elif metric == 'completion_rate':
                data_point['completion_rate'] = float(record.completion_rate)
            
            elif metric == 'rating':
                data_point['average_rating'] = float(record.average_rating)
            
            else:
                return Response(
                    {'error': f'Invalid metric: {metric}. Use students, revenue, completion_rate, or rating'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            trend_data.append(data_point)
        
        # Calculate summary statistics
        if trend_data:
            if metric == 'students':
                summary = {
                    'current_total': trend_data[-1]['total_students'],
                    'current_active': trend_data[-1]['active_students'],
                    'total_new_students': sum(d['new_students'] for d in trend_data),
                    'average_active': sum(d['active_students'] for d in trend_data) / len(trend_data)
                }
            
            elif metric == 'revenue':
                summary = {
                    'total_revenue': sum(d['revenue'] for d in trend_data),
                    'average_daily_revenue': sum(d['revenue'] for d in trend_data) / len(trend_data),
                    'highest_revenue': max(d['revenue'] for d in trend_data),
                    'lowest_revenue': min(d['revenue'] for d in trend_data)
                }
            
            elif metric == 'completion_rate':
                summary = {
                    'current_rate': trend_data[-1]['completion_rate'],
                    'average_rate': sum(d['completion_rate'] for d in trend_data) / len(trend_data),
                    'highest_rate': max(d['completion_rate'] for d in trend_data),
                    'lowest_rate': min(d['completion_rate'] for d in trend_data)
                }
            
            else:  # rating
                summary = {
                    'current_rating': trend_data[-1]['average_rating'],
                    'average_rating': sum(d['average_rating'] for d in trend_data) / len(trend_data),
                    'highest_rating': max(d['average_rating'] for d in trend_data),
                    'lowest_rating': min(d['average_rating'] for d in trend_data)
                }
        else:
            summary = {'message': 'No data available for this period'}
        
        return Response({
            'school': {
                'id': school.id,
                'name': school.name
            },
            'period': {
                'start_date': start_date,
                'end_date': end_date,
                'days': days
            },
            'metric': metric,
            'summary': summary,
            'trend_data': trend_data,
            'data_points': len(trend_data)
        })
    
    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated, IsPlatformAdminOrSchoolOwnerOrInstructor])
    def comparison(self, request):
        """
        Compare multiple schools or time periods.
        
        GET /api/school-analytics/comparison/
        Query params:
        - school_ids: Comma-separated school IDs (e.g., "1,2,3")
        - start_date: YYYY-MM-DD
        - end_date: YYYY-MM-DD
        """
        user = request.user

        school_ids_str = request.query_params.get('school_ids')
        start_date_str = request.query_params.get('start_date')
        end_date_str = request.query_params.get('end_date')
        
        # Validate inputs
        if not school_ids_str:
            return Response(
                {'error': 'school_ids is required (comma-separated)'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            school_ids = [int(id.strip()) for id in school_ids_str.split(',')]
        except ValueError:
            return Response(
                {'error': 'Invalid school_ids format'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if len(school_ids) > 5:
            return Response(
                {'error': 'Cannot compare more than 5 schools at once'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Parse dates
        # Check if only one date is provided (missing the other)
        if (start_date_str and not end_date_str) or (end_date_str and not start_date_str):
            # One date is missing
            if start_date_str and not end_date_str:
                return Response(
                    {'error': 'Missing end_date. Both start_date and end_date are required together.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            elif end_date_str and not start_date_str:
                return Response(
                    {'error': 'Missing start_date. Both start_date and end_date are required together.'},
                    status=status.HTTP_400_BAD_REQUEST
                )

        # Both dates provided
        if start_date_str and end_date_str:
            try:
                start_date = timezone.datetime.strptime(start_date_str, '%Y-%m-%d').date()
                end_date = timezone.datetime.strptime(end_date_str, '%Y-%m-%d').date()
            except ValueError:
                return Response(
                    {'error': 'Invalid date format. Use YYYY-MM-DD'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Validate date range
            if start_date > end_date:
                return Response(
                    {
                        'error': f'Invalid date range',
                        'detail': f'Start date ({start_date}) cannot be after end date ({end_date})',
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Check minimum date range (if needed)
            if (end_date - start_date).days < 1:
                return Response(
                    {'error': 'Date range must be at least 1 day'},
                    status=status.HTTP_400_BAD_REQUEST
                )

        # No dates provided, use defaults
        else:
            return Response(
                {'error': 'Both start_date and end_date are required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Get schools
        schools = DrivingSchool.objects.filter(id__in=school_ids)
        
        if not schools.exists():
            return Response(
                {'error': 'No schools found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Check permissions
        user = request.user
        if user.role == 'A' and not user.is_staff:
            # School owner can only compare their own schools
            schools = schools.filter(owner=user)
            if schools.count() != len(school_ids):
                return Response(
                    {'error': 'Some schools do not belong to you'},
                    status=status.HTTP_403_FORBIDDEN
                )
        
        if user.role == 'I':
            # Instructor cannot view their school
            return Response(
                {'error': 'Instructors can only view their own school, not compare'},
                status=status.HTTP_403_FORBIDDEN
            )

        # Continuing from where the comparison action left off...
    
        # Get analytics for comparison
        comparison_data = []
        
        for school in schools:
            # Get analytics for the period
            analytics_records = SchoolAnalytics.objects.filter(
                school=school,
                date__range=[start_date, end_date]
            ).order_by('date')
            
            # Calculate averages
            avg_total_students = analytics_records.aggregate(avg=Avg('total_students'))['avg'] or 0
            avg_active_students = analytics_records.aggregate(avg=Avg('active_students'))['avg'] or 0
            avg_completion_rate = analytics_records.aggregate(avg=Avg('completion_rate'))['avg'] or 0
            avg_rating = analytics_records.aggregate(avg=Avg('average_rating'))['avg'] or 0
            avg_revenue = analytics_records.aggregate(avg=Avg('revenue'))['avg'] or 0
            total_revenue = analytics_records.aggregate(total=Sum('revenue'))['total'] or 0
            total_lessons = analytics_records.aggregate(total=Sum('lessons_completed'))['total'] or 0
            
            # Get latest record for current metrics
            latest_record = analytics_records.last()
            
            # Get student enrollment trend
            new_students_total = analytics_records.aggregate(total=Sum('new_students'))['total'] or 0
            
            # Add to comparison data
            school_data = {
                'school': {
                    'id': school.id,
                    'name': school.name,
                    'owner': school.owner.get_full_name() or school.owner.username
                },
                'period_summary': {
                    'average_total_students': round(avg_total_students, 2),
                    'average_active_students': round(avg_active_students, 2),
                    'average_completion_rate': round(avg_completion_rate, 2),
                    'average_rating': round(avg_rating, 2),
                    'average_daily_revenue': round(avg_revenue, 2),
                    'total_revenue': round(total_revenue, 2),
                    'total_lessons_completed': total_lessons,
                    'new_students': new_students_total
                },
                'current_metrics': {
                    'total_students': latest_record.total_students if latest_record else 0,
                    'active_students': latest_record.active_students if latest_record else 0,
                    'completion_rate': latest_record.completion_rate if latest_record else 0,
                    'average_rating': latest_record.average_rating if latest_record else 0,
                    'instructor_utilization': latest_record.instructor_utilization if latest_record else 0
                } if latest_record else {},
                'data_points': analytics_records.count()
            }
            
            comparison_data.append(school_data)
        
        # Calculate growth rates
        for data in comparison_data:
            if data['data_points'] >= 2:
                # Get first and last analytics for growth calculation
                school = schools.get(id=data['school']['id'])
                first_record = SchoolAnalytics.objects.filter(
                    school=school,
                    date__range=[start_date, end_date]
                ).order_by('date').first()
                
                last_record = SchoolAnalytics.objects.filter(
                    school=school,
                    date__range=[start_date, end_date]
                ).order_by('date').last()
                
                if first_record and last_record and first_record != last_record:
                    # Calculate growth rates
                    student_growth = ((last_record.total_students - first_record.total_students) / 
                                    first_record.total_students * 100) if first_record.total_students > 0 else 0
                    
                    revenue_growth = ((last_record.revenue - first_record.revenue) / 
                                    first_record.revenue * 100) if first_record.revenue > 0 else 0
                    
                    completion_growth = last_record.completion_rate - first_record.completion_rate
                    
                    data['growth_rates'] = {
                        'student_growth': round(student_growth, 2),
                        'revenue_growth': round(revenue_growth, 2),
                        'completion_growth': round(completion_growth, 2),
                        'period': f"{first_record.date} to {last_record.date}"
                    }
        
        # Sort by performance (completion rate, then revenue)
        comparison_data.sort(
            key=lambda x: (
                x['period_summary']['average_completion_rate'],
                x['period_summary']['total_revenue']
            ),
            reverse=True
        )
        
        # Add rankings
        for idx, data in enumerate(comparison_data, 1):
            data['rank'] = idx
        
        # Overall statistics
        overall_stats = {
            'total_schools_compared': len(comparison_data),
            'highest_completion_rate': max(
                [d['period_summary']['average_completion_rate'] for d in comparison_data]
            ) if comparison_data else 0,
            'highest_average_rating': max(
                [d['period_summary']['average_rating'] for d in comparison_data]
            ) if comparison_data else 0,
            'highest_total_revenue': max(
                [d['period_summary']['total_revenue'] for d in comparison_data]
            ) if comparison_data else 0,
            'average_across_schools': {
                'completion_rate': round(
                    sum([d['period_summary']['average_completion_rate'] for d in comparison_data]) / 
                    len(comparison_data), 2
                ) if comparison_data else 0,
                'rating': round(
                    sum([d['period_summary']['average_rating'] for d in comparison_data]) / 
                    len(comparison_data), 2
                ) if comparison_data else 0
            }
        }
        
        return Response({
            'period': {
                'start_date': start_date,
                'end_date': end_date,
                'days': (end_date - start_date).days + 1
            },
            'overall_statistics': overall_stats,
            'school_comparison': comparison_data,
            'performance_ranking': comparison_data[:3] if len(comparison_data) >= 3 else comparison_data
        })
    
    @action(detail=False, methods=['get'])
    def export(self, request):
        """
        Export analytics data in CSV or JSON format.
        
        Query params:
        - school_id: Required
        - start_date: YYYY-MM-DD (optional, defaults to last 30 days)
        - end_date: YYYY-MM-DD (optional, defaults to today)
        - format: 'csv' or 'json' (default: 'csv')
        """


        
        school_id = request.query_params.get('school_id')
        start_date_str = request.query_params.get('start_date')
        end_date_str = request.query_params.get('end_date')
        export_format = request.query_params.get('format', 'csv').lower()
        
        # Validate format
        if export_format not in ['csv', 'json']:
            return Response(
                {'error': "Format must be 'csv' or 'json'"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if not school_id:
            return Response(
                {'error': 'school_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        

        try:
            school = DrivingSchool.objects.get(id=school_id)
        except DrivingSchool.DoesNotExist:
            return Response(
                {'error': 'School not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Check permissions
        user = request.user
        if user.role == 'A' and not user.is_staff:
            if school.owner != user:
                raise PermissionDenied("You can only export analytics for your own schools")
        
        if user.role == 'I':
            instructor_profile = user.student_profiles.filter(status='A').first()
            if not instructor_profile or instructor_profile.school != school:
                raise PermissionDenied("You can only export analytics for your school")
        
        # Parse dates or use defaults
        try:
            if start_date_str and end_date_str:
                start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
                end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
            else:
                # Default to last 30 days
                end_date = timezone.now().date()
                start_date = end_date - timedelta(days=30)
        except (ValueError, TypeError):
            return Response(
                {'error': 'Invalid date format. Use YYYY-MM-DD'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validate date range
        if start_date > end_date:
            return Response(
                {'error': 'Start date cannot be after end date'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Limit export range
        days_diff = (end_date - start_date).days
        if days_diff > 365:
            return Response(
                {'error': 'Export range cannot exceed 365 days'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get analytics data
        analytics_records = SchoolAnalytics.objects.filter(
            school=school,
            date__range=[start_date, end_date]
        ).order_by('date')
        
        # Prepare data
        export_data = []
        for record in analytics_records:
            export_data.append({
                'date': record.date.isoformat(),
                'total_students': record.total_students,
                'active_students': record.active_students,
                'new_students': record.new_students,
                'completion_rate': float(record.completion_rate),
                'revenue': float(record.revenue),
                'average_rating': float(record.average_rating) if record.average_rating else 0,
                'lessons_completed': record.lessons_completed,
                'instructor_utilization': float(record.instructor_utilization)
            })
        
        # Calculate summary
        summary = {
            'school': {
                'id': school.id,
                'name': school.name,
                'owner': school.owner.get_full_name() or school.owner.username
            },

            'period': {
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat(),
                'days': days_diff + 1
            },
            'total_records': len(export_data),
            'metrics_summary': {
                'average_total_students': round(
                    sum(d['total_students'] for d in export_data) / len(export_data), 2
                ) if export_data else 0,
                'average_active_students': round(
                    sum(d['active_students'] for d in export_data) / len(export_data), 2
                ) if export_data else 0,

                'average_completion_rate': round(
                    sum(d['completion_rate'] for d in export_data) / len(export_data), 2
                ) if export_data else 0,
                'total_revenue': round(
                    sum(d['revenue'] for d in export_data), 2
                ) if export_data else 0,
                'average_rating': round(
                    sum(d['average_rating'] for d in export_data) / len(export_data), 2
                ) if export_data else 0,
                'total_lessons_completed': sum(d['lessons_completed'] for d in export_data) if export_data else 0,

                'total_new_students': sum(d['new_students'] for d in export_data) if export_data else 0
            }
        }
        
        # Export based on format
        if export_format == 'csv':

            response = HttpResponse(content_type='text/csv')
            response['Content-Disposition'] = f'attachment; filename="{school.name}_analytics_{start_date}_{end_date}.csv"'
            
            writer = csv.DictWriter(response, fieldnames=[
                'date', 'total_students', 'active_students', 'new_students',
                'completion_rate', 'revenue', 'average_rating',
                'lessons_completed', 'instructor_utilization'
            ])
            
            writer.writeheader()
            writer.writerows(export_data)
            
            return response
        
        else:  # JSON format

            return Response({
                'metadata': summary,
                'data': export_data,
                'export_format': 'json',
                'exported_at': timezone.now().isoformat()
            })

    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated, IsPlatformAdminOrSchoolOwner])
    def alerts(self, request):
        """
        Get performance alerts for a school.
        Identifies areas needing attention.
        
        GET /api/school-analytics/alerts/
        Query params:
        - school_id: Required
        - days: Lookback period (default: 7, max: 30)
        """
        school_id = request.query_params.get('school_id')
        days = min(int(request.query_params.get('days', 7)), 30)
        
        if not school_id:
            return Response(
                {'error': 'school_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get school
        try:
            school = DrivingSchool.objects.get(id=school_id)
        except DrivingSchool.DoesNotExist:
            return Response(
                {'error': 'School not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Check permissions
        user = request.user
        if user.role == 'A' and not user.is_staff:
            if school.owner != user:
                raise PermissionDenied("You can only view alerts for your own schools")
        
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=days)
        
        # Get analytics for the period
        analytics_records = SchoolAnalytics.objects.filter(
            school=school,
            date__range=[start_date, end_date]
        ).order_by('date')
        
        if not analytics_records.exists():
            return Response({
                'school': school.name,
                'period': f'{start_date} to {end_date}',
                'message': 'No analytics data available for this period',
                'alerts': []
            })
        
        latest_record = analytics_records.last()
        first_record = analytics_records.first()
        
        alerts = []
        
        # Check for low completion rate
        if latest_record.completion_rate < 50:
            alerts.append({
                'type': 'warning',
                'code': 'LOW_COMPLETION_RATE',
                'title': 'Low Completion Rate',
                'message': f'Completion rate is {latest_record.completion_rate}%, below 50% threshold',
                'severity': 'high',
                'suggestion': 'Review student progress and provide additional support to struggling students.'
            })
        
        # Check for declining enrollment
        if latest_record.total_students < first_record.total_students:
            decline_percentage = ((first_record.total_students - latest_record.total_students) / 
                                first_record.total_students * 100) if first_record.total_students > 0 else 0
            
            if decline_percentage > 10:
                alerts.append({
                    'type': 'warning',
                    'code': 'DECLINING_ENROLLMENT',
                    'title': 'Declining Student Enrollment',
                    'message': f'Student enrollment declined by {decline_percentage:.1f}% over {days} days',
                    'severity': 'medium',
                    'suggestion': 'Review marketing strategies and student retention programs.'
                })
        
        # Check for low instructor utilization
        if latest_record.instructor_utilization < 60:
            alerts.append({
                'type': 'info',
                'code': 'LOW_INSTRUCTOR_UTILIZATION',
                    'title': 'Low Instructor Utilization',
                    'message': f'Instructor utilization is {latest_record.instructor_utilization}%, below optimal levels',
                    'severity': 'medium',
                    'suggestion': 'Consider optimizing instructor schedules or offering more lessons.'
                })
        
        # Check for no new students
        new_students_total = sum(record.new_students for record in analytics_records)
        if new_students_total == 0:
            alerts.append({
                'type': 'warning',
                'code': 'NO_NEW_STUDENTS',
                'title': 'No New Student Enrollment',
                'message': f'No new students enrolled in the last {days} days',
                'severity': 'high',
                'suggestion': 'Review marketing and enrollment strategies.'
            })
        
        # Check for low average rating
        if latest_record.average_rating < 3.0:
            alerts.append({
                'type': 'warning',
                'code': 'LOW_STUDENT_SATISFACTION',
                'title': 'Low Student Satisfaction',
                'message': f'Average student rating is {latest_record.average_rating}/5',
                'severity': 'high',
                'suggestion': 'Collect detailed feedback and address common concerns.'
            })
        
        # Check for low lesson completion rate
        total_lessons = Lesson.objects.filter(
            school=school,
            date__range=[timezone.make_aware(timezone.datetime.combine(start_date, timezone.datetime.min.time())),
                        timezone.make_aware(timezone.datetime.combine(end_date, timezone.datetime.max.time()))]
        ).count()
        
        completed_lessons = Lesson.objects.filter(
            school=school,
            status='C',
            date__range=[timezone.make_aware(timezone.datetime.combine(start_date, timezone.datetime.min.time())),
                        timezone.make_aware(timezone.datetime.combine(end_date, timezone.datetime.max.time()))]
        ).count()
        
        if total_lessons > 0:
            lesson_completion_rate = (completed_lessons / total_lessons) * 100
            if lesson_completion_rate < 70:
                alerts.append({
                    'type': 'warning',
                    'code': 'LOW_LESSON_COMPLETION',
                    'title': 'Low Lesson Completion Rate',
                    'message': f'Only {lesson_completion_rate:.1f}% of lessons were completed',
                    'severity': 'medium',
                    'suggestion': 'Review lesson scheduling and attendance policies.'
                })
        
        # Get at-risk students
        at_risk_students = StudentProfile.objects.filter(
            school=school,
            status='A',
            progress_theory__lt=20,
            progress_driving__lt=20
        ).count()
        
        if at_risk_students > 0:
            alerts.append({
                'type': 'warning',
                'code': 'AT_RISK_STUDENTS',
                'title': 'Students at Risk',
                'message': f'{at_risk_students} students have less than 20% progress in both theory and driving',
                'severity': 'high',
                'suggestion': 'Identify and provide additional support to at-risk students.'
            })
        
        # Categorize alerts by severity
        high_severity = [a for a in alerts if a['severity'] == 'high']
        medium_severity = [a for a in alerts if a['severity'] == 'medium']
        low_severity = [a for a in alerts if a['severity'] == 'low']
        
        # Calculate overall health score
        health_score = 100
        if high_severity:
            health_score -= len(high_severity) * 20
        if medium_severity:
            health_score -= len(medium_severity) * 10
        
        health_status = 'healthy' if health_score >= 80 else 'needs_attention' if health_score >= 60 else 'critical'
        
        return Response({
            'school': {
                'id': school.id,
                'name': school.name
            },
            'period': {
                'start_date': start_date,
                'end_date': end_date,
                'days': days
            },
            'overall_health': {
                'score': max(0, health_score),
                'status': health_status,
                'alerts_count': len(alerts)
            },
            'alerts_by_severity': {
                'high': high_severity,
                'medium': medium_severity,
                'low': low_severity
            },
            'all_alerts': alerts,
            'summary': {
                'total_alerts': len(alerts),
                'needs_immediate_attention': len(high_severity),
                'should_be_addressed': len(medium_severity),
                'for_information': len(low_severity)
            },
            'timestamp': timezone.now().isoformat()
        })
    
    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated, IsPlatformAdminOrSchoolOwner])
    def predictions(self, request):
        """
        Get predictive insights and forecasts.
        
        GET /api/school-analytics/predictions/
        Query params:
        - school_id: Required
        - horizon: 'week', 'month', 'quarter' (default: 'month')
        """
        school_id = request.query_params.get('school_id')
        horizon = request.query_params.get('horizon', 'month')
        
        if not school_id:
            return Response(
                {'error': 'school_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get school
        try:
            school = DrivingSchool.objects.get(id=school_id)
        except DrivingSchool.DoesNotExist:
            return Response(
                {'error': 'School not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Check permissions
        user = request.user
        if user.role == 'A' and not user.is_staff:
            if school.owner != user:
                raise PermissionDenied("You can only view predictions for your own schools")
        
        # Get historical data (last 90 days)
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=90)
        
        analytics_records = SchoolAnalytics.objects.filter(
            school=school,
            date__range=[start_date, end_date]
        ).order_by('date')
        
        if analytics_records.count() < 7:
            return Response({
                'school': school.name,
                'message': 'Insufficient data for predictions. Need at least 7 days of data.',
                'data_points': analytics_records.count()
            })
        
        # Calculate trends
        dates = [record.date for record in analytics_records]
        total_students = [record.total_students for record in analytics_records]
        active_students = [record.active_students for record in analytics_records]
        revenues = [float(record.revenue) for record in analytics_records]
        completion_rates = [float(record.completion_rate) for record in analytics_records]
        
        # Simple linear regression for prediction
        def predict_trend(values):
            if len(values) < 2:
                return 0
            
            # Calculate slope
            n = len(values)
            x_mean = n / 2
            y_mean = sum(values) / n
            
            numerator = sum((i - x_mean) * (values[i] - y_mean) for i in range(n))
            denominator = sum((i - x_mean) ** 2 for i in range(n))
            
            if denominator == 0:
                return 0
            
            return numerator / denominator
        
        # Calculate trends
        student_trend = predict_trend(total_students)
        active_trend = predict_trend(active_students)
        revenue_trend = predict_trend(revenues)
        completion_trend = predict_trend(completion_rates)
        
        # Make predictions based on horizon
        if horizon == 'week':
            days_ahead = 7
        elif horizon == 'quarter':
            days_ahead = 90
        else:  # month
            days_ahead = 30
        
        # Predictions
        latest = analytics_records.last()
        predictions = {
            'total_students': max(0, round(latest.total_students + student_trend * days_ahead)),
            'active_students': max(0, round(latest.active_students + active_trend * days_ahead)),
            'revenue': max(0, round(latest.revenue + revenue_trend * days_ahead, 2)),
            'completion_rate': max(0, min(100, round(latest.completion_rate + completion_trend * days_ahead, 2)))
        }
        
        # Calculate confidence based on data quality
        data_quality = min(1.0, analytics_records.count() / 30)  # Max confidence with 30 days of data
        confidence = round(data_quality * 100, 1)
        
        # Generate recommendations
        recommendations = []
        
        if student_trend < 0:
            recommendations.append({
                'type': 'enrollment',
                'priority': 'high',
                'title': 'Address Declining Enrollment',
                'action': 'Review marketing strategies and student acquisition channels.',
                'impact': 'High'
            })
        
        if revenue_trend < 0:
            recommendations.append({
                'type': 'revenue',
                'priority': 'high',
                'title': 'Improve Revenue Streams',
                'action': 'Consider introducing new services or adjusting pricing.',
                'impact': 'High'
            })
        
        if completion_trend < 0:
            recommendations.append({
                'type': 'retention',
                'priority': 'medium',
                'title': 'Improve Student Retention',
                'action': 'Provide additional support to at-risk students.',
                'impact': 'Medium'
            })
        
        if student_trend > 0 and revenue_trend <= 0:
            recommendations.append({
                'type': 'pricing',
                'priority': 'medium',
                'title': 'Review Pricing Strategy',
                'action': 'Growing student base but stagnant revenue may indicate pricing issues.',
                'impact': 'Medium'
            })
        
        return Response({
            'school': {
                'id': school.id,
                'name': school.name
            },
            'prediction_horizon': {
                'period': horizon,
                'days_ahead': days_ahead,
                'prediction_date': end_date + timedelta(days=days_ahead)
            },
            'historical_data': {
                'days_analyzed': len(analytics_records),
                'date_range': f'{start_date} to {end_date}',
                'data_quality_score': data_quality
            },
            'current_metrics': {
                'total_students': latest.total_students,
                'active_students': latest.active_students,
                'revenue': float(latest.revenue),
                'completion_rate': latest.completion_rate
            },
            'predicted_metrics': {
                'values': predictions,
                'confidence': f'{confidence}%',
                'trend_directions': {
                    'student_trend': 'up' if student_trend > 0 else 'down' if student_trend < 0 else 'stable',
                    'revenue_trend': 'up' if revenue_trend > 0 else 'down' if revenue_trend < 0 else 'stable',
                    'completion_trend': 'up' if completion_trend > 0 else 'down' if completion_trend < 0 else 'stable'
                }
            },
            'recommendations': recommendations,
            'trend_analysis': {
                'student_growth_per_day': round(student_trend, 3),
                'revenue_growth_per_day': round(revenue_trend, 3),
                'completion_change_per_day': round(completion_trend, 3)
            },
            'notes': [
                'Predictions are based on linear trend analysis of historical data.',
                f'Confidence level is {confidence}% based on data quality.',
                'Actual results may vary based on external factors.'
            ]
        })
    
    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def summary(self, request):
        """
        Get a summary of all accessible schools' analytics.
        Role-specific summary.
        
        GET /api/school-analytics/summary/
        """
        user = request.user
        
        if user.role == 'A' and user.is_staff:
            # Platform admin - summary of all schools
            schools = DrivingSchool.objects.all()
            school_summaries = []
            
            for school in schools[:10]:  # Limit to 10 schools for performance
                latest_analytics = SchoolAnalytics.objects.filter(
                    school=school
                ).order_by('-date').first()
                
                if latest_analytics:
                    school_summaries.append({
                        'school_id': school.id,
                        'school_name': school.name,
                        'owner': school.owner.get_full_name() or school.owner.username,
                        'total_students': latest_analytics.total_students,
                        'active_students': latest_analytics.active_students,
                        'completion_rate': latest_analytics.completion_rate,
                        'revenue': float(latest_analytics.revenue),
                        'last_updated': latest_analytics.date
                    })
            
            # Overall platform statistics
            total_schools = schools.count()
            total_students = sum(s['total_students'] for s in school_summaries)
            total_active_students = sum(s['active_students'] for s in school_summaries)
            avg_completion_rate = sum(s['completion_rate'] for s in school_summaries) / len(school_summaries) if school_summaries else 0
            total_revenue = sum(s['revenue'] for s in school_summaries)
            
            return Response({
                'user_role': 'platform_admin',
                'overall_platform_stats': {
                    'total_schools': total_schools,
                    'total_students': total_students,
                    'total_active_students': total_active_students,
                    'average_completion_rate': round(avg_completion_rate, 2),
                    'total_revenue': round(total_revenue, 2)
                },
                'school_summaries': school_summaries,
                'top_performing_schools': sorted(
                    school_summaries,
                    key=lambda x: x['completion_rate'],
                    reverse=True
                )[:3],
                'highest_revenue_schools': sorted(
                    school_summaries,
                    key=lambda x: x['revenue'],
                    reverse=True
                )[:3]
            })
        
        elif user.role == 'A' and not user.is_staff:
            # School owner - summary of their schools
            schools = DrivingSchool.objects.filter(owner=user)
            school_summaries = []
            
            for school in schools:
                latest_analytics = SchoolAnalytics.objects.filter(
                    school=school
                ).order_by('-date').first()
                
                if latest_analytics:
                    school_summaries.append({
                        'school_id': school.id,
                        'school_name': school.name,
                        'total_students': latest_analytics.total_students,
                        'active_students': latest_analytics.active_students,
                        'completion_rate': latest_analytics.completion_rate,
                        'revenue': float(latest_analytics.revenue),
                        'new_students': latest_analytics.new_students,
                        'last_updated': latest_analytics.date
                    })
            
            # Overall owner statistics
            if school_summaries:
                total_students = sum(s['total_students'] for s in school_summaries)
                total_active_students = sum(s['active_students'] for s in school_summaries)
                avg_completion_rate = sum(s['completion_rate'] for s in school_summaries) / len(school_summaries)
                total_revenue = sum(s['revenue'] for s in school_summaries)
                total_new_students = sum(s['new_students'] for s in school_summaries)
            else:
                total_students = total_active_students = avg_completion_rate = total_revenue = total_new_students = 0
            
            return Response({
                'user_role': 'school_owner',
                'overall_stats': {
                    'total_schools': schools.count(),
                    'total_students': total_students,
                    'total_active_students': total_active_students,
                    'average_completion_rate': round(avg_completion_rate, 2),
                    'total_revenue': round(total_revenue, 2),
                    'total_new_students': total_new_students
                },
                'school_summaries': school_summaries,
                'best_performing_school': max(
                    school_summaries,
                    key=lambda x: x['completion_rate']
                ) if school_summaries else None,
                'highest_revenue_school': max(
                    school_summaries,
                    key=lambda x: x['revenue']
                ) if school_summaries else None
            })
        
        elif user.role == 'I':
            # Instructor - summary of their school
            instructor_profile = user.student_profiles.filter(status='A').first()
            
            if not instructor_profile:
                return Response(
                    {'error': 'You are not associated with any active school'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            school = instructor_profile.school
            latest_analytics = SchoolAnalytics.objects.filter(
                school=school
            ).order_by('-date').first()
            
            if not latest_analytics:
                return Response({
                    'user_role': 'instructor',
                    'school': {
                        'id': school.id,
                        'name': school.name
                    },
                    'message': 'No analytics data available for this school'
                })
            
            # Instructor-specific metrics
            lessons_taught = Lesson.objects.filter(
                instructor=user,
                date__gte=timezone.now() - timedelta(days=30)
            ).count()
            
            avg_rating = Feedback.objects.filter(
                lesson__instructor=user
            ).aggregate(avg=Avg('rating'))['avg'] or 0
            
            students_taught = Attendance.objects.filter(
                lesson__instructor=user,
                presence=True
            ).values('student').distinct().count()
            
            return Response({
                'user_role': 'instructor',
                'school_summary': {
                    'school_id': school.id,
                    'school_name': school.name,
                    'total_students': latest_analytics.total_students,
                    'active_students': latest_analytics.active_students,
                    'completion_rate': latest_analytics.completion_rate,
                    'average_rating': latest_analytics.average_rating,
                    'last_updated': latest_analytics.date
                },
                'instructor_performance': {
                    'lessons_taught_30days': lessons_taught,
                    'average_rating': round(avg_rating, 2),
                    'unique_students_taught': students_taught
                },
                'comparison': {
                    'completion_rate_vs_school_average': round(
                        latest_analytics.completion_rate - latest_analytics.completion_rate, 2
                    ),  # Same for now, could compare with other instructors
                    'rating_vs_school_average': round(
                        float(avg_rating) - float(latest_analytics.average_rating), 2
                    )
                }
            })
        
        else:
            return Response(
                {'error': 'Students cannot access analytics summaries'},
                status=status.HTTP_403_FORBIDDEN
            )
    
    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated, IsPlatformAdmin])
    def system_health(self, request):
        """
        System health check for analytics module.
        Platform admin only.
        
        GET /api/school-analytics/system_health/
        """

        
        health_checks = {}
        
        user = self.request.user

        if user.role == 'A' and not user.is_staff:
            raise PermissionDenied("you don't have permission")

        # 1. Database connection check
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
            health_checks['database'] = {
                'status': 'healthy',
                'message': 'Database connection successful'
            }
        except Exception as e:
            health_checks['database'] = {
                'status': 'unhealthy',
                'message': f'Database connection failed: {str(e)}'
            }
        
        # 2. Cache check
        try:
            test_key = 'analytics_health_check'
            cache.set(test_key, 'test', 10)
            cached_value = cache.get(test_key)
            
            if cached_value == 'test':
                health_checks['cache'] = {
                    'status': 'healthy',
                    'message': 'Cache system working'
                }
            else:
                health_checks['cache'] = {
                    'status': 'unhealthy',
                    'message': 'Cache read/write failed'
                }
        except Exception as e:
            health_checks['cache'] = {
                'status': 'unhealthy',
                'message': f'Cache system error: {str(e)}'
            }
        
        # 3. Analytics data completeness check
        total_schools = DrivingSchool.objects.count()
        schools_with_analytics = SchoolAnalytics.objects.values('school').distinct().count()
        
        if total_schools > 0:
            coverage_percentage = (schools_with_analytics / total_schools) * 100
            if coverage_percentage >= 80:
                status = 'healthy'
            elif coverage_percentage >= 50:
                status = 'warning'
            else:
                status = 'unhealthy'
            
            health_checks['data_coverage'] = {
                'status': status,
                'message': f'Analytics coverage: {coverage_percentage:.1f}%',
                'details': {
                    'total_schools': total_schools,
                    'schools_with_analytics': schools_with_analytics,
                    'coverage_percentage': coverage_percentage
                }
            }
        
        # 4. Recent data freshness
        recent_analytics = SchoolAnalytics.objects.order_by('-date').first()
        if recent_analytics:
            days_since_last_update = (timezone.now().date() - recent_analytics.date).days
            
            if days_since_last_update == 0:
                status = 'healthy'
            elif days_since_last_update <= 2:
                status = 'warning'
            else:
                status = 'unhealthy'
            
            health_checks['data_freshness'] = {
                'status': status,
                'message': f'Most recent analytics: {recent_analytics.date} ({days_since_last_update} days ago)',
                'details': {
                    'last_update_date': recent_analytics.date,
                    'days_since_update': days_since_last_update,
                    'school': recent_analytics.school.name
                }
            }
        
        # 5. Performance metrics
        try:
            # Count queries in last hour
            hour_ago = timezone.now() - timedelta(hours=1)
            queries_last_hour = SchoolAnalytics.objects.filter(
                created_at__gte=hour_ago
            ).count()
            
            health_checks['performance'] = {
                'status': 'healthy',
                'message': f'Analytics queries in last hour: {queries_last_hour}',
                'details': {
                    'queries_last_hour': queries_last_hour,
                    'average_daily_queries': SchoolAnalytics.objects.filter(
                        created_at__date=timezone.now().date()
                    ).count()
                }
            }
        except Exception as e:
            health_checks['performance'] = {
                'status': 'warning',
                'message': f'Performance check failed: {str(e)}'
            }
        
        # Overall system status
        unhealthy_checks = [h for h in health_checks.values() if h['status'] == 'unhealthy']
        warning_checks = [h for h in health_checks.values() if h['status'] == 'warning']
        
        if unhealthy_checks:
            overall_status = 'unhealthy'
        elif warning_checks:
            overall_status = 'warning'
        else:
            overall_status = 'healthy'
        
        return Response({
            'system_health': {
                'status': overall_status,
                'timestamp': timezone.now().isoformat(),
                'checks_performed': len(health_checks),
                'unhealthy_checks': len(unhealthy_checks),
                'warning_checks': len(warning_checks)
            },
            'detailed_checks': health_checks,
            'recommendations': self._get_health_recommendations(health_checks),
            'next_scheduled_maintenance': 'Daily at 02:00 AM UTC'
        })
    
    def _get_health_recommendations(self, health_checks):
        """Generate recommendations based on health check results"""
        recommendations = []
        
        if 'data_coverage' in health_checks:
            coverage_data = health_checks['data_coverage']
            if coverage_data['status'] == 'warning':
                recommendations.append({
                    'priority': 'medium',
                    'action': 'Run bulk analytics generation for schools missing data.',
                    'reason': f"Only {coverage_data['details']['coverage_percentage']:.1f}% of schools have analytics data."
                })
            elif coverage_data['status'] == 'unhealthy':
                recommendations.append({
                    'priority': 'high',
                    'action': 'Urgently generate analytics for all schools.',
                    'reason': 'Analytics data coverage is critically low.'
                })
        
        if 'data_freshness' in health_checks:
            freshness_data = health_checks['data_freshness']
            if freshness_data['status'] == 'warning':
                recommendations.append({
                    'priority': 'low',
                    'action': 'Check analytics generation schedule.',
                    'reason': f"Last update was {freshness_data['details']['days_since_update']} days ago."
                })
            elif freshness_data['status'] == 'unhealthy':
                recommendations.append({
                    'priority': 'high',
                    'action': 'Immediately run analytics generation.',
                    'reason': 'Analytics data is severely outdated.'
                })
        
        return recommendations




class CSVRenderer:
    """Custom renderer for CSV responses"""
    media_type = 'text/csv'
    format = 'csv'
    
    def render(self, data, accepted_media_type=None, renderer_context=None):
        """
        Render report data as CSV
        """
        if isinstance(data, bytes):
            return data
        
        if isinstance(data, str):
            return data.encode('utf-8')
        
        # If data is a dict with 'error' key, it's an error response
        if isinstance(data, dict) and 'error' in data:
            return str(data).encode('utf-8')
        
        return data

# DSS-14-create-ReportViewSet
class ReportViewSet(viewsets.ViewSet):
    """
    ViewSet for generating and managing reports.
    
    Provides various report types and export formats for analytics data.
    
    Access Control:
    - Platform Admins: Full access to all reports
    - School Owners: Generate reports for their schools
    - Instructors: View reports for their school (read-only)
    - Students: Cannot access reports
    """
    
    permission_classes = [IsAuthenticated]
    
    def get_permissions(self):
        """Define permissions per action"""
        if self.action in ['weekly_report', 'monthly_report', 'custom_report', 'export_report']:
            return [IsAuthenticated(), IsPlatformAdminOrSchoolOwner()]
        
        elif self.action in ['instructor_performance', 'student_progress', 'financial_summary']:
            return [IsAuthenticated(), IsPlatformAdminOrSchoolOwnerOrInstructor()]
        
        elif self.action in ['send_weekly_report', 'schedule_report']:
            return [IsAuthenticated(), IsPlatformAdminOrSchoolOwner()]
        
        return [IsAuthenticated()]
    
    @action(detail=False, methods=['get'], url_path='report-weekly', url_name='report-weekly')
    def weekly_report(self, request):
        """
        Generate weekly report for a school.
        
        GET /api/reports/weekly_report/
        Query params:
        - school_id: Required
        - date: Optional (defaults to last 7 days from today)
        """
        user = request.user
        school_id = request.query_params.get('school_id')
        date_str = request.query_params.get('date')
        
        # Validate school_id
        if not school_id:
            return Response(
                {'error': 'school_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get school
        try:
            school = DrivingSchool.objects.get(id=school_id)
        except DrivingSchool.DoesNotExist:
            return Response(
                {'error': 'School not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Check permissions
        if user.role == 'A' and not user.is_staff:
            if school.owner != user:
                raise PermissionDenied("You can only generate reports for your own schools")
        
        # Parse date or use default
        if date_str:
            try:
                end_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            except ValueError:
                return Response(
                    {'error': 'Invalid date format. Use YYYY-MM-DD'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        else:
            end_date = timezone.now().date()
        
        start_date = end_date - timedelta(days=6)  # 7 days total
        
        # Get analytics data
        analytics_records = SchoolAnalytics.objects.filter(
            school=school,
            date__range=[start_date, end_date]
        ).order_by('date')
        
        if not analytics_records.exists():
            return Response({
                'school': school.name,
                'period': f'{start_date} to {end_date}',
                'message': 'No analytics data available for this week'
            })
        
        # Calculate summary metrics
        total_students = analytics_records.last().total_students if analytics_records.exists() else 0
        avg_active_students = analytics_records.aggregate(avg=Avg('active_students'))['avg'] or 0
        total_new_students = analytics_records.aggregate(total=Sum('new_students'))['total'] or 0
        avg_completion_rate = analytics_records.aggregate(avg=Avg('completion_rate'))['avg'] or 0
        total_revenue = analytics_records.aggregate(total=Sum('revenue'))['total'] or 0
        avg_rating = analytics_records.aggregate(avg=Avg('average_rating'))['avg'] or 0
        total_lessons = analytics_records.aggregate(total=Sum('lessons_completed'))['total'] or 0
        avg_instructor_utilization = analytics_records.aggregate(avg=Avg('instructor_utilization'))['avg'] or 0
        
        # Daily breakdown
        daily_data = []
        for record in analytics_records:
            daily_data.append({
                'date': record.date,
                'total_students': record.total_students,
                'active_students': record.active_students,
                'new_students': record.new_students,
                'completion_rate': float(record.completion_rate),
                'revenue': float(record.revenue),
                'average_rating': float(record.average_rating),
                'lessons_completed': record.lessons_completed
            })
        
        # Get lessons data
        lessons = Lesson.objects.filter(
            school=school,
            date__range=[
                timezone.make_aware(datetime.combine(start_date, datetime.min.time())),
                timezone.make_aware(datetime.combine(end_date, datetime.max.time()))
            ]
        )
        
        total_lessons_scheduled = lessons.count()
        completed_lessons = lessons.filter(status='C').count()
        cancelled_lessons = lessons.filter(status='X').count()
        
        # Get feedback data
        feedback_records = Feedback.objects.filter(
            lesson__school=school,
            created_at__date__range=[start_date, end_date]
        )
        
        total_feedback = feedback_records.count()
        feedback_by_rating = dict(
            feedback_records.values('rating').annotate(count=Count('id')).values_list('rating', 'count')
        )
        
        # Top performing students
        top_students = StudentProfile.objects.filter(
            school=school,
            user__role='S',
            status='A'
        ).annotate(
            avg_progress=((F('progress_theory') + F('progress_driving')) / 2)
        ).order_by('-avg_progress')[:5]
        
        top_students_data = [{
            'id': student.id,
            'name': student.user.get_full_name() or student.user.username,
            'progress': round((student.progress_theory + student.progress_driving) / 2, 2),
            'total_hours': student.total_hours_theory + student.total_hours_driving
        } for student in top_students]
        
        # Instructor performance
        instructors = User.objects.filter(
            role='I',
            student_profiles__school=school,
            student_profiles__status='A'
        ).distinct()
        
        instructor_stats = []
        for instructor in instructors:
            instructor_lessons = lessons.filter(instructor=instructor)
            instructor_feedback = feedback_records.filter(lesson__instructor=instructor)
            
            instructor_stats.append({
                'id': instructor.id,
                'name': instructor.get_full_name() or instructor.username,
                'lessons_taught': instructor_lessons.count(),
                'completed_lessons': instructor_lessons.filter(status='C').count(),
                'average_rating': round(
                    instructor_feedback.aggregate(avg=Avg('rating'))['avg'] or 0, 2
                ),
                'total_feedback': instructor_feedback.count()
            })
        
        # Attendance statistics
        attendance_records = Attendance.objects.filter(
            lesson__school=school,
            lesson__date__range=[
                timezone.make_aware(datetime.combine(start_date, datetime.min.time())),
                timezone.make_aware(datetime.combine(end_date, datetime.max.time()))
            ]
        )
        
        total_attendance_records = attendance_records.count()
        present_count = attendance_records.filter(presence=True).count()
        attendance_rate = round((present_count / total_attendance_records * 100), 2) if total_attendance_records > 0 else 0
        
        # Compare with previous week
        prev_week_start = start_date - timedelta(days=7)
        prev_week_end = start_date - timedelta(days=1)
        
        prev_week_analytics = SchoolAnalytics.objects.filter(
            school=school,
            date__range=[prev_week_start, prev_week_end]
        )
        
        if prev_week_analytics.exists():
            prev_avg_completion = prev_week_analytics.aggregate(avg=Avg('completion_rate'))['avg'] or 0
            prev_total_revenue = prev_week_analytics.aggregate(total=Sum('revenue'))['total'] or 0
            prev_new_students = prev_week_analytics.aggregate(total=Sum('new_students'))['total'] or 0
            
            completion_change = avg_completion_rate - prev_avg_completion
            revenue_change = float(total_revenue) - float(prev_total_revenue)
            students_change = total_new_students - prev_new_students
            
            comparison = {
                'completion_rate_change': round(completion_change, 2),
                'revenue_change': round(revenue_change, 2),
                'new_students_change': students_change,
                'trends': {
                    'completion': 'up' if completion_change > 0 else 'down' if completion_change < 0 else 'stable',
                    'revenue': 'up' if revenue_change > 0 else 'down' if revenue_change < 0 else 'stable',
                    'enrollment': 'up' if students_change > 0 else 'down' if students_change < 0 else 'stable'
                }
            }
        else:
            comparison = {
                'message': 'No previous week data available for comparison'
            }
        
        # Compile report
        report = {
            'report_type': 'weekly',
            'school': {
                'id': school.id,
                'name': school.name,
                'owner': school.owner.get_full_name() or school.owner.username,
                'email': school.email
            },
            'period': {
                'start_date': start_date,
                'end_date': end_date,
                'days': 7
            },
            'summary_metrics': {
                'total_students': total_students,
                'avg_active_students': round(avg_active_students, 2),
                'total_new_students': total_new_students,
                'avg_completion_rate': round(avg_completion_rate, 2),
                'total_revenue': round(float(total_revenue), 2),
                'avg_rating': round(avg_rating, 2),
                'total_lessons': total_lessons,
                'avg_instructor_utilization': round(avg_instructor_utilization, 2)
            },
            'daily_breakdown': daily_data,
            'lessons': {
                'total_scheduled': total_lessons_scheduled,
                'completed': completed_lessons,
                'cancelled': cancelled_lessons,
                'completion_rate': round((completed_lessons / total_lessons_scheduled * 100), 2) if total_lessons_scheduled > 0 else 0
            },
            'attendance': {
                'total_records': total_attendance_records,
                'present': present_count,
                'absent': total_attendance_records - present_count,
                'attendance_rate': attendance_rate
            },
            'feedback': {
                'total_feedback': total_feedback,
                'by_rating': feedback_by_rating,
                'average_rating': round(avg_rating, 2)
            },
            'top_students': top_students_data,
            'instructor_performance': instructor_stats,
            'comparison_with_previous_week': comparison,
            'generated_at': timezone.now().isoformat()
        }
        
        return Response(report)
    
    @action(detail=False, methods=['get'], url_name='report-monthly', url_path='report-monthly')
    def monthly_report(self, request):
        """
        Generate monthly report for a school.
        
        GET /api/reports/monthly_report/
        Query params:
        - school_id: Required
        - month: Optional (YYYY-MM format, defaults to current month)
        """
        user = request.user
        school_id = request.query_params.get('school_id')
        month_str = request.query_params.get('month')
        
        # Validate school_id
        if not school_id:
            return Response(
                {'error': 'school_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get school
        try:
            school = DrivingSchool.objects.get(id=school_id)
        except DrivingSchool.DoesNotExist:
            return Response(
                {'error': 'School not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Check permissions
        if user.role == 'A' and not user.is_staff:
            if school.owner != user:
                raise PermissionDenied("You can only generate reports for your own schools")
        
        # Parse month or use default
        if month_str:
            try:
                year, month = map(int, month_str.split('-'))
                start_date = date(year, month, 1)
            except (ValueError, AttributeError):
                return Response(
                    {'error': 'Invalid month format. Use YYYY-MM'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        else:
            today = timezone.now().date()
            start_date = date(today.year, today.month, 1)
        
        # Calculate end date (last day of month)
        if start_date.month == 12:
            end_date = date(start_date.year + 1, 1, 1) - timedelta(days=1)
        else:
            end_date = date(start_date.year, start_date.month + 1, 1) - timedelta(days=1)
        
        # Don't allow future months
        if start_date > timezone.now().date():
            return Response(
                {'error': 'Cannot generate reports for future months'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get analytics data
        analytics_records = SchoolAnalytics.objects.filter(
            school=school,
            date__range=[start_date, end_date]
        ).order_by('date')
        
        if not analytics_records.exists():
            return Response({
                'school': school.name,
                'period': f'{start_date} to {end_date}',
                'message': 'No analytics data available for this month'
            })
        
        # Calculate monthly metrics
        final_record = analytics_records.last()
        initial_record = analytics_records.first()
        
        # Student metrics
        students_at_start = initial_record.total_students
        students_at_end = final_record.total_students
        student_growth = students_at_end - students_at_start
        total_new_students = analytics_records.aggregate(total=Sum('new_students'))['total'] or 0
        avg_active_students = analytics_records.aggregate(avg=Avg('active_students'))['avg'] or 0
        
        # Performance metrics
        avg_completion_rate = analytics_records.aggregate(avg=Avg('completion_rate'))['avg'] or 0
        avg_rating = analytics_records.aggregate(avg=Avg('average_rating'))['avg'] or 0
        avg_instructor_utilization = analytics_records.aggregate(avg=Avg('instructor_utilization'))['avg'] or 0
        
        # Financial metrics
        total_revenue = analytics_records.aggregate(total=Sum('revenue'))['total'] or 0
        avg_daily_revenue = analytics_records.aggregate(avg=Avg('revenue'))['avg'] or 0
        highest_revenue_day = analytics_records.order_by('-revenue').first()
        
        # Lesson metrics
        total_lessons = analytics_records.aggregate(total=Sum('lessons_completed'))['total'] or 0
        
        lessons = Lesson.objects.filter(
            school=school,
            date__range=[
                timezone.make_aware(datetime.combine(start_date, datetime.min.time())),
                timezone.make_aware(datetime.combine(end_date, datetime.max.time()))
            ]
        )
        
        total_scheduled = lessons.count()
        completed = lessons.filter(status='C').count()
        cancelled = lessons.filter(status='X').count()
        
        # Weekly breakdown
        weekly_breakdown = []
        current_week_start = start_date
        week_num = 1
        
        while current_week_start <= end_date:
            week_end = min(current_week_start + timedelta(days=6), end_date)
            
            week_analytics = analytics_records.filter(date__range=[current_week_start, week_end])
            
            if week_analytics.exists():
                weekly_breakdown.append({
                    'week': week_num,
                    'start_date': current_week_start,
                    'end_date': week_end,
                    'avg_active_students': round(week_analytics.aggregate(avg=Avg('active_students'))['avg'] or 0, 2),
                    'new_students': week_analytics.aggregate(total=Sum('new_students'))['total'] or 0,
                    'revenue': round(float(week_analytics.aggregate(total=Sum('revenue'))['total'] or 0), 2),
                    'avg_completion_rate': round(week_analytics.aggregate(avg=Avg('completion_rate'))['avg'] or 0, 2),
                    'lessons_completed': week_analytics.aggregate(total=Sum('lessons_completed'))['total'] or 0
                })
            
            current_week_start = week_end + timedelta(days=1)
            week_num += 1
        
        # Student status breakdown
        students_completed = StudentProfile.objects.filter(
            school=school,
            status='C',
            completion_date__range=[start_date, end_date]
        ).count()
        
        current_active = StudentProfile.objects.filter(
            school=school,
            user__role='S',
            status='A'
        ).count()
        
        current_paused = StudentProfile.objects.filter(
            school=school,
            user__role='S',
            status='P'
        ).count()
        
        # Instructor performance (monthly)
        instructors = User.objects.filter(
            role='I',
            student_profiles__school=school,
            student_profiles__status='A'
        ).distinct()
        
        instructor_monthly_stats = []
        for instructor in instructors:
            instructor_lessons = lessons.filter(instructor=instructor)
            instructor_feedback = Feedback.objects.filter(
                lesson__instructor=instructor,
                lesson__school=school,
                created_at__date__range=[start_date, end_date]
            )
            
            instructor_monthly_stats.append({
                'id': instructor.id,
                'name': instructor.get_full_name() or instructor.username,
                'total_lessons': instructor_lessons.count(),
                'completed_lessons': instructor_lessons.filter(status='C').count(),
                'cancelled_lessons': instructor_lessons.filter(status='X').count(),
                'average_rating': round(instructor_feedback.aggregate(avg=Avg('rating'))['avg'] or 0, 2),
                'total_feedback': instructor_feedback.count(),
                'completion_rate': round(
                    (instructor_lessons.filter(status='C').count() / instructor_lessons.count() * 100), 2
                ) if instructor_lessons.count() > 0 else 0
            })
        
        # Top achievements
        achievements_earned = Achievement.objects.filter(
            student__school=school,
            earned_at__date__range=[start_date, end_date]
        )
        
        total_achievements = achievements_earned.count()
        achievements_by_type = dict(
            achievements_earned.values('type').annotate(count=Count('id')).values_list('type', 'count')
        )
        
        # Attendance analysis
        attendance_records = Attendance.objects.filter(
            lesson__school=school,
            lesson__date__range=[
                timezone.make_aware(datetime.combine(start_date, datetime.min.time())),
                timezone.make_aware(datetime.combine(end_date, datetime.max.time()))
            ]
        )
        
        total_attendance = attendance_records.count()
        present = attendance_records.filter(presence=True).count()
        monthly_attendance_rate = round((present / total_attendance * 100), 2) if total_attendance > 0 else 0
        
        # Compare with previous month
        prev_month_start = (start_date.replace(day=1) - timedelta(days=1)).replace(day=1)
        prev_month_end = start_date - timedelta(days=1)
        
        prev_month_analytics = SchoolAnalytics.objects.filter(
            school=school,
            date__range=[prev_month_start, prev_month_end]
        )
        
        if prev_month_analytics.exists():
            prev_revenue = prev_month_analytics.aggregate(total=Sum('revenue'))['total'] or 0
            prev_completion = prev_month_analytics.aggregate(avg=Avg('completion_rate'))['avg'] or 0
            prev_new_students = prev_month_analytics.aggregate(total=Sum('new_students'))['total'] or 0
            
            revenue_change = float(total_revenue) - float(prev_revenue)
            completion_change = avg_completion_rate - prev_completion
            students_change = total_new_students - prev_new_students
            
            revenue_pct = round((revenue_change / float(prev_revenue) * 100), 2) if prev_revenue > 0 else 0
            
            month_comparison = {
                'revenue_change': round(revenue_change, 2),
                'revenue_change_percentage': revenue_pct,
                'completion_rate_change': round(completion_change, 2),
                'new_students_change': students_change,
                'trends': {
                    'revenue': 'up' if revenue_change > 0 else 'down' if revenue_change < 0 else 'stable',
                    'completion': 'up' if completion_change > 0 else 'down' if completion_change < 0 else 'stable',
                    'enrollment': 'up' if students_change > 0 else 'down' if students_change < 0 else 'stable'
                }
            }
        else:
            month_comparison = {
                'message': 'No previous month data available for comparison'
            }
        
        # Compile monthly report
        report = {
            'report_type': 'monthly',
            'school': {
                'id': school.id,
                'name': school.name,
                'owner': school.owner.get_full_name() or school.owner.username,
                'email': school.email
            },
            'period': {
                'month': start_date.strftime('%B %Y'),
                'start_date': start_date,
                'end_date': end_date,
                'days': (end_date - start_date).days + 1
            },
            'executive_summary': {
                'total_revenue': round(float(total_revenue), 2),
                'student_growth': student_growth,
                'new_students': total_new_students,
                'students_completed': students_completed,
                'avg_completion_rate': round(avg_completion_rate, 2),
                'avg_rating': round(avg_rating, 2),
                'total_lessons_completed': total_lessons,
                'monthly_attendance_rate': monthly_attendance_rate
            },
            'student_metrics': {
                'students_at_start': students_at_start,
                'students_at_end': students_at_end,
                'net_growth': student_growth,
                'growth_percentage': round((student_growth / students_at_start * 100), 2) if students_at_start > 0 else 0,
                'new_enrollments': total_new_students,
                'completions': students_completed,
                'current_active': current_active,
                'current_paused': current_paused,
                'avg_active_per_day': round(avg_active_students, 2)
            },
            'financial_metrics': {
                'total_revenue': round(float(total_revenue), 2),
                'avg_daily_revenue': round(float(avg_daily_revenue), 2),
                'highest_revenue_day': {
                    'date': highest_revenue_day.date,
                    'amount': round(float(highest_revenue_day.revenue), 2)
                } if highest_revenue_day else None
            },
            'performance_metrics': {
                'avg_completion_rate': round(avg_completion_rate, 2),
                'avg_rating': round(avg_rating, 2),
                'avg_instructor_utilization': round(avg_instructor_utilization, 2)
            },
            'lesson_metrics': {
                'total_scheduled': total_scheduled,
                'total_completed': completed,
                'total_cancelled': cancelled,
                'completion_rate': round((completed / total_scheduled * 100), 2) if total_scheduled > 0 else 0,
                'cancellation_rate': round((cancelled / total_scheduled * 100), 2) if total_scheduled > 0 else 0
            },
            'weekly_breakdown': weekly_breakdown,
            'instructor_performance': instructor_monthly_stats,
            'achievements': {
                'total_earned': total_achievements,
                'by_type': achievements_by_type
            },
            'attendance': {
                'total_records': total_attendance,
                'present': present,
                'absent': total_attendance - present,
                'attendance_rate': monthly_attendance_rate
            },
            'comparison_with_previous_month': month_comparison,
            'generated_at': timezone.now().isoformat()
        }
        
        return Response(report)
    
    @action(detail=False, methods=['post'], url_path='report-send-weekly', url_name='report-send-weekly')
    def send_weekly_report(self, request):
        """
        Generate and send weekly report via email.
        
        POST /api/reports/send_weekly_report/
        Body: {
            "school_id": 123,
            "date": "2024-12-31" (optional)
        }
        """
        user = request.user
        school_id = request.data.get('school_id')
        date_str = request.data.get('date')
        
        if not school_id:
            return Response(
                {'error': 'school_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get school
        try:
            school = DrivingSchool.objects.get(id=school_id)
        except DrivingSchool.DoesNotExist:
            return Response(
                {'error': 'School not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Check permissions
        if user.role == 'A' and not user.is_staff:
            if school.owner != user:
                raise PermissionDenied("You can only send reports for your own schools")
        
        # Generate report (reuse weekly_report logic)
        request.query_params._mutable = True
        request.query_params['school_id'] = school_id
        if date_str:
            request.query_params['date'] = date_str
        request.query_params._mutable = False
        
        report_response = self.weekly_report(request)
        
        if report_response.status_code != 200:
            return report_response
        
        summary = report_response.data
        
        # Send email using ReportService
        try:
            ReportService.send_weekly_report(school, summary)
            
            return Response({
                'message': 'Weekly report sent successfully',
                'recipient': school.owner.email,
                'school': school.name,
                'period': {
                    'start_date': summary['period']['start_date'],
                    'end_date': summary['period']['end_date']
                },
                'sent_at': timezone.now().isoformat()
            })
        
        except Exception as e:
            return Response({
                'error': f'Failed to send report: {str(e)}',
                'report_generated': True,
                'email_sent': False
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    @action(detail=False, methods=['get'], )
    def instructor_performance(self, request):
        """
        Generate instructor performance report.
        
        GET /api/reports/instructor_performance/
        Query params:
        - school_id: Required
        - instructor_id: Optional (specific instructor)
        - start_date: Optional (YYYY-MM-DD)
        - end_date: Optional (YYYY-MM-DD)
        """
        user = request.user
        school_id = request.query_params.get('school_id')
        instructor_id = request.query_params.get('instructor_id')
        start_date_str = request.query_params.get('start_date')
        end_date_str = request.query_params.get('end_date')
        
        if not school_id:
            return Response(
                {'error': 'school_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get school
        try:
            school = DrivingSchool.objects.get(id=school_id)
        except DrivingSchool.DoesNotExist:
            return Response(
                {'error': 'School not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Check permissions
        if user.role == 'A' and not user.is_staff:
            if school.owner != user:
                raise PermissionDenied("You can only view reports for your own schools")
        
        if user.role == 'I':
            instructor_profile = user.student_profiles.filter(status='A').first()
            if not instructor_profile or instructor_profile.school != school:
                raise PermissionDenied("You can only view reports for your school")
        
        # Parse dates or use defaults (last 30 days)
        if start_date_str and end_date_str:
            try:
                start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
                end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
            except ValueError:
                return Response(
                    {'error': 'Invalid date format. Use YYYY-MM-DD'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        else:
            end_date = timezone.now().date()
            start_date = end_date - timedelta(days=30)
        
        # Get instructors
        if instructor_id:
            try:
                instructors = [User.objects.get(id=instructor_id, role='I')]
                # Verify instructor belongs to this school
                if not instructors[0].student_profiles.filter(school=school, status='A').exists():
                    return Response(
                        {'error': 'Instructor not found in this school'},
                        status=status.HTTP_404_NOT_FOUND
                    )
            except User.DoesNotExist:
                return Response(
                    {'error': 'Instructor not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
        else:
            instructors = User.objects.filter(
                role='I',
                student_profiles__school=school,
                student_profiles__status='A'
            ).distinct()
        
        # Generate performance data for each instructor
        instructor_reports = []
        
        for instructor in instructors:
            # Get lessons
            lessons = Lesson.objects.filter(
                instructor=instructor,
                school=school,
                date__range=[
                    timezone.make_aware(datetime.combine(start_date, datetime.min.time())),
                    timezone.make_aware(datetime.combine(end_date, datetime.max.time()))
                ]
                )
        
        total_lessons = lessons.count()
        completed_lessons = lessons.filter(status='C').count()
        cancelled_lessons = lessons.filter(status='X').count()
        
        # Get feedback
        feedback = Feedback.objects.filter(
            lesson__instructor=instructor,
            lesson__school=school,
            created_at__date__range=[start_date, end_date]
        )
        
        avg_rating = feedback.aggregate(avg=Avg('rating'))['avg'] or 0
        total_feedback = feedback.count()
        
        # Feedback distribution
        rating_distribution = dict(
            feedback.values('rating').annotate(count=Count('id')).values_list('rating', 'count')
        )
        
        # Students taught
        students_taught = Attendance.objects.filter(
            lesson__instructor=instructor,
            lesson__school=school,
            lesson__date__range=[
                timezone.make_aware(datetime.combine(start_date, datetime.min.time())),
                timezone.make_aware(datetime.combine(end_date, datetime.max.time()))
            ],
            presence=True
        ).values('student').distinct().count()
        
        # Hours taught
        total_hours = sum(
            (lesson.duration / 60) for lesson in lessons if lesson.status == 'C'
        )
        
        # Attendance rate for instructor's lessons
        attendance_records = Attendance.objects.filter(
            lesson__instructor=instructor,
            lesson__school=school,
            lesson__date__range=[
                timezone.make_aware(datetime.combine(start_date, datetime.min.time())),
                timezone.make_aware(datetime.combine(end_date, datetime.max.time()))
            ]
        )
        
        total_attendance = attendance_records.count()
        present = attendance_records.filter(presence=True).count()
        instructor_attendance_rate = round((present / total_attendance * 100), 2) if total_attendance > 0 else 0
        
        instructor_reports.append({
            'instructor': {
                'id': instructor.id,
                'name': instructor.get_full_name() or instructor.username,
                'email': instructor.email
            },
            'lesson_metrics': {
                'total_lessons': total_lessons,
                'completed': completed_lessons,
                'cancelled': cancelled_lessons,
                'completion_rate': round((completed_lessons / total_lessons * 100), 2) if total_lessons > 0 else 0,
                'total_hours': round(total_hours, 2)
            },
            'student_metrics': {
                'unique_students_taught': students_taught,
                'attendance_rate': instructor_attendance_rate
            },
            'feedback_metrics': {
                'average_rating': round(avg_rating, 2),
                'total_feedback': total_feedback,
                'rating_distribution': rating_distribution,
                'feedback_rate': round((total_feedback / completed_lessons * 100), 2) if completed_lessons > 0 else 0
            },
            'performance_score': round(
                (avg_rating * 0.4) + 
                ((completed_lessons / total_lessons * 5) * 0.3 if total_lessons > 0 else 0) + 
                ((instructor_attendance_rate / 20) * 0.3), 2
            )
        })
    
        # Sort by performance score
        instructor_reports.sort(key=lambda x: x['performance_score'], reverse=True)
    
        # Add rankings
        for idx, report in enumerate(instructor_reports, 1):
            report['rank'] = idx
    
        # Overall statistics
        total_instructors = len(instructor_reports)
        avg_completion_rate = sum(r['lesson_metrics']['completion_rate'] for r in instructor_reports) / total_instructors if total_instructors > 0 else 0
        avg_rating_overall = sum(r['feedback_metrics']['average_rating'] for r in instructor_reports) / total_instructors if total_instructors > 0 else 0
        
        return Response({
            'report_type': 'instructor_performance',
            'school': {
                'id': school.id,
                'name': school.name
            },
            'period': {
                'start_date': start_date,
                'end_date': end_date,
                'days': (end_date - start_date).days + 1
            },
            'overall_statistics': {
                'total_instructors': total_instructors,
                'avg_completion_rate': round(avg_completion_rate, 2),
                'avg_rating': round(avg_rating_overall, 2)
            },
            'instructor_reports': instructor_reports,
            'top_performers': instructor_reports[:3] if len(instructor_reports) >= 3 else instructor_reports,
            'generated_at': timezone.now().isoformat()
        })

    @action(detail=False, methods=['get'])
    def student_progress(self, request):
        """
        Generate student progress report.
        
        GET /api/reports/student_progress/
        Query params:
        - school_id: Required
        - status: Optional ('A', 'C', 'P')
        - min_progress: Optional (0-100)
        """
        user = request.user
        school_id = request.query_params.get('school_id')
        status_filter = request.query_params.get('status')
        min_progress = request.query_params.get('min_progress')
        
        if not school_id:
            return Response(
                {'error': 'school_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get school
        try:
            school = DrivingSchool.objects.get(id=school_id)
        except DrivingSchool.DoesNotExist:
            return Response(
                {'error': 'School not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Check permissions
        if user.role == 'A' and not user.is_staff:
            if school.owner != user:
                raise PermissionDenied("You can only view reports for your own schools")
        
        if user.role == 'I':
            instructor_profile = user.student_profiles.filter(status='A').first()
            if not instructor_profile or instructor_profile.school != school:
                raise PermissionDenied("You can only view reports for your school")
        
        # Get students
        students = StudentProfile.objects.filter(
            school=school,
            user__role='S'
        ).select_related('user')
        
        # Apply filters
        if status_filter:
            students = students.filter(status=status_filter)
        
        # Generate student reports
        student_reports = []
        
        for student in students:
            avg_progress = (student.progress_theory + student.progress_driving) / 2
            
            # Apply min_progress filter
            if min_progress:
                try:
                    min_prog = float(min_progress)
                    if avg_progress < min_prog:
                        continue
                except ValueError:
                    pass
            
            # Get attendance
            attendance = Attendance.objects.filter(student=student)
            total_lessons = attendance.count()
            attended = attendance.filter(presence=True).count()
            
            # Get achievements
            achievements_count = Achievement.objects.filter(student=student).count()
            
            # Get feedback given
            feedback_given = Feedback.objects.filter(student=student).count()
            
            student_reports.append({
                'student': {
                    'id': student.id,
                    'name': student.user.get_full_name() or student.user.username,
                    'email': student.user.email
                },
                'status': student.get_status_display(),
                'progress': {
                    'theory': float(student.progress_theory),
                    'driving': float(student.progress_driving),
                    'average': round(avg_progress, 2)
                },
                'hours': {
                    'theory': float(student.total_hours_theory),
                    'driving': float(student.total_hours_driving),
                    'total': float(student.total_hours_theory + student.total_hours_driving)
                },
                'attendance': {
                    'total_lessons': total_lessons,
                    'attended': attended,
                    'missed': total_lessons - attended,
                    'attendance_rate': round((attended / total_lessons * 100), 2) if total_lessons > 0 else 0
                },
                'engagement': {
                    'achievements_earned': achievements_count,
                    'feedback_given': feedback_given
                },
                'dates': {
                    'joined': student.joined_at,
                    'theory_start': student.theory_start_date,
                    'driving_start': student.driving_start_date,
                    'completion': student.completion_date
                }
            })
        
        # Sort by average progress
        student_reports.sort(key=lambda x: x['progress']['average'], reverse=True)
        
        # Categorize students
        at_risk = [s for s in student_reports if s['progress']['average'] < 20]
        on_track = [s for s in student_reports if 20 <= s['progress']['average'] < 80]
        excelling = [s for s in student_reports if s['progress']['average'] >= 80]
        
        return Response({
            'report_type': 'student_progress',
            'school': {
                'id': school.id,
                'name': school.name
            },
            'summary': {
                'total_students': len(student_reports),
                'at_risk': len(at_risk),
                'on_track': len(on_track),
                'excelling': len(excelling),
                'avg_progress': round(
                    sum(s['progress']['average'] for s in student_reports) / len(student_reports), 2
                ) if student_reports else 0
            },
            'students': student_reports,
            'categorized': {
                'at_risk': at_risk,
                'on_track': on_track,
                'excelling': excelling
            },
            'generated_at': timezone.now().isoformat()
        })

    @action(detail=False, methods=['get'])
    def financial_summary(self, request):
        """
        Generate financial summary report.
        
        GET /api/reports/financial_summary/
        Query params:
        - school_id: Required
        - start_date: Optional (YYYY-MM-DD)
        - end_date: Optional (YYYY-MM-DD)
        """
        user = request.user
        school_id = request.query_params.get('school_id')
        start_date_str = request.query_params.get('start_date')
        end_date_str = request.query_params.get('end_date')
        
        if not school_id:
            return Response(
                {'error': 'school_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get school
        try:
            school = DrivingSchool.objects.get(id=school_id)
        except DrivingSchool.DoesNotExist:
            return Response(
                {'error': 'School not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Check permissions
        if user.role == 'A' and not user.is_staff:
            if school.owner != user:
                raise PermissionDenied("You can only view financial reports for your own schools")
        
        if user.role == 'I':
            instructor_profile = user.student_profiles.filter(status='A').first()
            if not instructor_profile or instructor_profile.school != school:
                raise PermissionDenied("You can only view reports for your school")
        
        # Parse dates or use defaults
        if start_date_str and end_date_str:
            try:
                start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
                end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
            except ValueError:
                return Response(
                    {'error': 'Invalid date format. Use YYYY-MM-DD'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        else:
            end_date = timezone.now().date()
            start_date = end_date - timedelta(days=30)
        
        # Get analytics data
        analytics = SchoolAnalytics.objects.filter(
            school=school,
            date__range=[start_date, end_date]
        ).order_by('date')
        
        if not analytics.exists():
            return Response({
                'school': school.name,
                'period': f'{start_date} to {end_date}',
                'message': 'No financial data available for this period'
            })
        
        # Calculate financial metrics
        total_revenue = analytics.aggregate(total=Sum('revenue'))['total'] or 0
        avg_daily_revenue = analytics.aggregate(avg=Avg('revenue'))['avg'] or 0
        
        highest_day = analytics.order_by('-revenue').first()
        lowest_day = analytics.order_by('revenue').first()
        
        # Daily revenue data
        daily_revenue = [{
            'date': record.date,
            'revenue': float(record.revenue)
        } for record in analytics]
        
        # Monthly breakdown if period > 30 days
        monthly_breakdown = []
        if (end_date - start_date).days > 30:
            current_month = start_date.replace(day=1)
            while current_month <= end_date:
                if current_month.month == 12:
                    next_month = current_month.replace(year=current_month.year + 1, month=1)
                else:
                    next_month = current_month.replace(month=current_month.month + 1)
                
                month_end = min(next_month - timedelta(days=1), end_date)
                
                month_analytics = analytics.filter(date__range=[current_month, month_end])
                
                if month_analytics.exists():
                    monthly_breakdown.append({
                        'month': current_month.strftime('%B %Y'),
                        'total_revenue': round(float(month_analytics.aggregate(total=Sum('revenue'))['total'] or 0), 2),
                        'avg_daily_revenue': round(float(month_analytics.aggregate(avg=Avg('revenue'))['avg'] or 0), 2),
                        'days': month_analytics.count()
                    })
                
                current_month = next_month
        
        return Response({
            'report_type': 'financial_summary',
            'school': {
                'id': school.id,
                'name': school.name
            },
            'period': {
                'start_date': start_date,
                'end_date': end_date,
                'days': (end_date - start_date).days + 1
            },
            'financial_summary': {
                'total_revenue': round(float(total_revenue), 2),
                'avg_daily_revenue': round(float(avg_daily_revenue), 2),
                'highest_revenue_day': {
                    'date': highest_day.date,
                    'amount': round(float(highest_day.revenue), 2)
                } if highest_day else None,
                'lowest_revenue_day': {
                    'date': lowest_day.date,
                    'amount': round(float(lowest_day.revenue), 2)
                } if lowest_day else None
            },
            'daily_revenue': daily_revenue,
            'monthly_breakdown': monthly_breakdown if monthly_breakdown else None,
            'generated_at': timezone.now().isoformat()
        })

    @action(detail=False, methods=['get'], url_path='export')
    def export_report(self, request):
        """
        Export report in CSV or JSON format.
        
        GET /api/reports/export/
        Query params:
        - school_id: Required
        - report_type: 'weekly' or 'monthly' (default: 'weekly')
        - format: 'csv' or 'json' (default: 'csv')
        """
        try:
            school_id = request.query_params.get('school_id')
            report_type = request.query_params.get('report_type', 'weekly').lower()
            export_format = request.query_params.get('export_format', 'csv').lower()  # ← Changed
            
            if not school_id:
                return Response(
                    {'error': 'school_id is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            if export_format not in ['csv', 'json']:
                return Response(
                    {'error': "format must be 'csv' or 'json'"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Generate report data based on type
            if report_type == 'weekly':
                report_data = ReportService.generate_weekly_report(
                    school_id=int(school_id),
                    end_date=None,
                    user=request.user
                )
            elif report_type == 'monthly':
                report_data = ReportService.generate_monthly_report(
                    school_id=int(school_id),
                    year=None,
                    month=None,
                    user=request.user
                )
            else:
                return Response(
                    {'error': f'Unknown report type: {report_type}'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            

            if export_format not in ['csv', 'json']:
                return Response(
                    {'error': "export_format must be 'csv' or 'json'"},  # ← Updated error message
                    status=status.HTTP_400_BAD_REQUEST
                )
            # Export based on format
            if export_format == 'csv':
                # Generate CSV content
                csv_content = self._generate_csv_content(report_data, report_type)
                
                # Create response with CSV content
                response = Response(
                    csv_content,
                    status=status.HTTP_200_OK,
                    content_type='text/csv'
                )
                
                # Set filename
                school_name = report_data.get('school', {}).get('name', 'report').replace(' ', '_')
                filename = f"{report_type}_report_{school_name}_{datetime.now().strftime('%Y%m%d')}.csv"
                response['Content-Disposition'] = f'attachment; filename="{filename}"'
                
                return response
            else:  # json
                return Response(report_data)
        
        except PermissionError as e:
            return Response({'error': str(e)}, status=status.HTTP_403_FORBIDDEN)
        except ValueError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            import traceback
            print(f"Export error: {str(e)}")
            print(traceback.format_exc())
            return Response(
                {'error': f'Failed to export report: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def _generate_csv_content(self, report_data, report_type):
        """
        Generate CSV content as a string from report data.
        Returns the CSV content as a string.
        """
        # Use StringIO to write CSV to memory
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write metadata
        writer.writerow(['Report Type', report_type.upper()])
        if 'school' in report_data:
            writer.writerow(['School', report_data['school'].get('name', '')])
        if 'period' in report_data:
            start = report_data['period'].get('start_date', '')
            end = report_data['period'].get('end_date', '')
            writer.writerow(['Period', f"{start} to {end}"])
        writer.writerow(['Generated At', report_data.get('generated_at', datetime.now().isoformat())])
        writer.writerow([])  # Empty row
        
        # Write summary metrics
        summary = report_data.get('summary_metrics', {})
        if summary:
            writer.writerow(['Summary Metrics'])
            writer.writerow(['Metric', 'Value'])
            for key, value in summary.items():
                writer.writerow([key.replace('_', ' ').title(), value])
            writer.writerow([])  # Empty row
        
        # Write daily breakdown if exists
        if 'daily_breakdown' in report_data:
            writer.writerow(['Daily Breakdown'])
            writer.writerow(['Date', 'Total Students', 'Active Students', 'New Students', 'Revenue', 'Lessons Completed'])
            for day in report_data['daily_breakdown']:
                writer.writerow([
                    day.get('date', ''),
                    day.get('total_students', ''),
                    day.get('active_students', ''),
                    day.get('new_students', ''),
                    day.get('revenue', ''),
                    day.get('lessons_completed', '')
                ])
            writer.writerow([])  # Empty row
        
        # Write weekly breakdown if exists
        if 'weekly_breakdown' in report_data:
            writer.writerow(['Weekly Breakdown'])
            writer.writerow(['Week', 'Start Date', 'End Date', 'Avg Active Students', 'New Students', 'Revenue', 'Lessons'])
            for week in report_data['weekly_breakdown']:
                writer.writerow([
                    week.get('week', ''),
                    week.get('start_date', ''),
                    week.get('end_date', ''),
                    week.get('avg_active_students', ''),
                    week.get('new_students', ''),
                    week.get('revenue', ''),
                    week.get('lessons_completed', '')
                ])
            writer.writerow([])  # Empty row
        
        # Write lesson statistics if exists
        if 'lessons' in report_data:
            lessons = report_data['lessons']
            writer.writerow(['Lesson Statistics'])
            writer.writerow(['Metric', 'Value'])
            writer.writerow(['Total Scheduled', lessons.get('total_scheduled', '')])
            writer.writerow(['Completed', lessons.get('completed', '')])
            writer.writerow(['Cancelled', lessons.get('cancelled', '')])
            writer.writerow(['Completion Rate', f"{lessons.get('completion_rate', '')}%"])
            writer.writerow([])  # Empty row
        
        # Write attendance statistics if exists
        if 'attendance' in report_data:
            attendance = report_data['attendance']
            writer.writerow(['Attendance Statistics'])
            writer.writerow(['Metric', 'Value'])
            writer.writerow(['Total Records', attendance.get('total_records', '')])
            writer.writerow(['Present', attendance.get('present', '')])
            writer.writerow(['Absent', attendance.get('absent', '')])
            writer.writerow(['Attendance Rate', f"{attendance.get('attendance_rate', '')}%"])
        
        # Get the CSV content as a string
        csv_content = output.getvalue()
        output.close()
        
        return csv_content
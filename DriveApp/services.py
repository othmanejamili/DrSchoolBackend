# services.py
from datetime import timedelta
from django.utils import timezone
from datetime import datetime
from django.db.models import Avg, Count, Sum, Q
from .models import (SchoolAnalytics, StudentProfile, Lesson, 
                     Feedback, Attendance, Schedule, Vehicle, StudentDocument,
                     SubscriptionPlan, SchoolSubscription, AutomatedMessage, CommunicationTemplate)
from django.db import transaction
from django.db.models import Count, Avg, Sum, Max,Q, F, ExpressionWrapper, FloatField
from django.core.cache import cache
from datetime import timedelta
import logging
from .models import StudentPerformancePrediction
from typing import Dict, List, Optional, Tuple
from rest_framework import serializers
from decimal import Decimal
import os
from PIL import Image
from io import BytesIO
import cloudinary.uploader
import cloudinary.api

logger = logging.getLogger(__name__)



class StudentProfileService:
    """Handle all StudentProfile business logic and operations"""
    
    # Configuration
    THEORY_TARGET_HOURS = 50
    DRIVING_TARGET_HOURS = 40
    
    @staticmethod
    def calculate_completion_percentage(student_profile) -> float:
        """Calculate overall completion percentage"""
        if student_profile.status == 'C':  # Completed
            return 100.0
        return round((Decimal(student_profile.progress_theory) + Decimal(student_profile.progress_driving)) / 2, 2)
    
    @staticmethod
    def validate_student_creation(user, school, request_user=None) -> None:
        """Validate student profile creation business rules"""
        if not request_user or not request_user.is_authenticated:
            raise serializers.ValidationError({'user': 'Authentication required'})
        
        # Check user role
        if user.role != 'S':
            raise serializers.ValidationError({'user': 'Selected user must have student role'})
        
        # Check for existing enrollment
        if StudentProfile.objects.filter(user=user, school=school).exists():
            raise serializers.ValidationError({'user': 'This student is already enrolled in this school'})
        
        # PLATFORM ADMIN CHECK FIRST - they can manage any school
        if request_user.role == 'A' and request_user.is_staff:
            return  # Platform admin - allow any school
        
        # SCHOOL OWNER CHECK - can only manage their own schools
        if request_user.role == 'A' and not request_user.is_staff:
            if school.owner == request_user:
                return  # School owner managing their own school - OK
            else:
                raise serializers.ValidationError(
                    {'school': 'You can only manage students in your own schools'}
                )
        
        # INSTRUCTORS and STUDENTS cannot create profiles
        raise serializers.ValidationError(
            {'user': 'You do not have permission to create student profiles'}
        )
    
    @staticmethod
    def validate_student_data(attrs, instance=None) -> None:
        """Validate student profile data business rules"""
        # Progress validation
        progress_theory = attrs.get('progress_theory')
        progress_driving = attrs.get('progress_driving')
        
        if progress_theory is not None and (progress_theory < 0 or progress_theory > 100):
            raise serializers.ValidationError({'progress_theory': 'Progress theory should be between 0 and 100'})
        
        if progress_driving is not None and (progress_driving < 0 or progress_driving > 100):
            raise serializers.ValidationError({'progress_driving': 'Progress driving should be between 0 and 100'})
        
        # Date validation
        theory_start = attrs.get('theory_start_date', instance.theory_start_date if instance else None)
        driving_start = attrs.get('driving_start_date', instance.driving_start_date if instance else None)
        completion = attrs.get('completion_date')
        
        if completion:
            if theory_start and completion < theory_start:
                raise serializers.ValidationError("Completion date cannot be before theory start date")
            if driving_start and completion < driving_start:
                raise serializers.ValidationError("Completion date cannot be before driving start date")
        
        # Auto-set completion date if status changed to completed
        if attrs.get('status') == 'C' and not completion:
            attrs['completion_date'] = timezone.now().date()
    
    @staticmethod
    def validate_school_change(new_school, instance, request_user=None) -> None:
        """Validate school change business rules"""
        if instance and new_school != instance.school:
            raise serializers.ValidationError(
                {'school': 'Cannot change the school of an existing profile'}
            )
        
        # Check permissions for new school
        if request_user:
            # Platform admins can manage any school
            if request_user.role == 'A' and request_user.is_staff:
                return
            
            # School owners can only manage their own schools
            if request_user.role == 'A' and not request_user.is_staff:
                if new_school.owner != request_user:
                    raise serializers.ValidationError(
                        {'school': 'You can only manage students in your own schools'}
                    )
    
    @staticmethod
    def can_manage_school(request_user, school) -> bool:
        """Check if user can manage a school"""
        if not request_user or not request_user.is_authenticated:
            return False
        
        # Platform admins can manage any school
        if request_user.role == 'A' and request_user.is_staff:
            return True
        
        # School owners can only manage their own schools
        if request_user.role == 'A' and not request_user.is_staff:
            return school.owner == request_user
        
        # Instructors and students cannot manage schools
        return False

    @staticmethod
    @transaction.atomic
    def create_student_profile(validated_data, request_user) -> StudentProfile:
        """Create student profile with business logic"""
        if not request_user or not request_user.is_authenticated:
            raise serializers.ValidationError('Authentication required to create a student profile')
        
        return StudentProfile.objects.create(**validated_data)
    
    @staticmethod
    @transaction.atomic
    def update_student_profile(instance, validated_data) -> StudentProfile:
        """Update student profile with business logic"""
        # Prevent changing user and school (business rule)
        validated_data.pop('user', None)
        validated_data.pop('school', None)
        
        # Update instance
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        
        return instance
    
    @staticmethod
    def get_profile_picture_url(student_profile, request=None) -> Optional[str]:
        """Get full URL for profile picture"""
        if not student_profile.picture_profile:
            return None
        
        try:
            if request:
                return request.build_absolute_uri(student_profile.picture_profile.url)
            return student_profile.picture_profile.url
        except Exception:
            return None
    
    @staticmethod
    def update_progress_from_attendance(student_profile, lesson_type, hours_completed) -> None:
        """Update student progress based on attendance"""
        if lesson_type == 'T':  # Theory
            student_profile.total_hours_theory += hours_completed
            student_profile.progress_theory = min(
                100, 
                (student_profile.total_hours_theory / StudentProfileService.THEORY_TARGET_HOURS) * 100
            )
        elif lesson_type == 'D':  # Driving
            student_profile.total_hours_driving += hours_completed
            student_profile.progress_driving = min(
                100,
                (student_profile.total_hours_driving / StudentProfileService.DRIVING_TARGET_HOURS) * 100
            )
        
        student_profile.save()
    
    @staticmethod
    def check_completion_requirements(student_profile) -> bool:
        """Check if student meets completion requirements"""
        return (student_profile.progress_theory >= 100 and 
                student_profile.progress_driving >= 100 and
                student_profile.total_hours_theory >= StudentProfileService.THEORY_TARGET_HOURS and
                student_profile.total_hours_driving >= StudentProfileService.DRIVING_TARGET_HOURS)
    
    @staticmethod
    def auto_complete_student(student_profile) -> None:
        """Automatically mark student as completed if requirements met"""
        if (student_profile.status != 'C' and 
            StudentProfileService.check_completion_requirements(student_profile)):
            student_profile.status = 'C'
            student_profile.completion_date = timezone.now().date()
            student_profile.save()


class LessonService:
    """Handle all Lesson business logic and operations"""
    
    # Configuration
    MIN_DURATION = 1  # minutes
    MAX_DURATION = 480  # minutes (8 hours)
    COMPLETION_THRESHOLD = 0.8  # 80% attendance threshold
    
    @staticmethod
    def calculate_completion_percentage(lesson) -> float:
        """
        Calculate lesson completion percentage based on status and attendance.
        
        Returns:
            float: Completion percentage (0-100)
        """
        if lesson.status == 'C':  # Completed
            return 100.0
        elif lesson.status == 'S':  # Scheduled
            if lesson.date < timezone.now():
                return 0.0  # Missed/past lesson
            return 10.0  # Upcoming lesson
        else:  # 'P' - Paused
            # Calculate based on actual attendance
            total_enrolled = lesson.lesson_attendance.count()
            if total_enrolled == 0:
                return 0.0
            
            completed = lesson.lesson_attendance.filter(
                presence=True,
                hours_completed__gte=lesson.duration * LessonService.COMPLETION_THRESHOLD
            ).count()
            
            return round((completed / total_enrolled) * 100, 2)

    @staticmethod
    def validate_lesson_creation(instructor, school, lesson_date, duration, request_user=None) -> None:
        """Validate lesson creation business rules"""
        # Check instructor role
        if instructor.role != 'I':
            raise serializers.ValidationError({
                'instructor': 'Selected user must be an instructor'
            })
        
        # Check if instructor is enrolled in this school via StudentProfile
        if not StudentProfile.objects.filter(
            user=instructor, 
            school=school,
            status='A'  # Active status
        ).exists():
            raise serializers.ValidationError({
                'instructor': 'Instructor is not assigned to this school'
            })
        
        # Validate date for new lessons
        if lesson_date < timezone.now():
            raise serializers.ValidationError({
                'date': 'Cannot create lessons in the past'
            })
        
        # Validate duration
        if duration < LessonService.MIN_DURATION or duration > LessonService.MAX_DURATION:
            raise serializers.ValidationError({
                'duration': f'Duration must be between {LessonService.MIN_DURATION} and {LessonService.MAX_DURATION} minutes'
            })
        
        # Check school ownership - compare IDs instead of objects
        if request_user:
            if request_user.role == 'A' and request_user.is_staff:
                return
            if request_user.role == 'A' and not request_user.is_staff:
                if school.owner.id != request_user.id:
                    raise serializers.ValidationError({
                        'school': 'You can only manage lessons in your own schools'
                    })
 
        
        # Check for scheduling conflicts
        LessonService._check_scheduling_conflicts(instructor, lesson_date, duration)

    @staticmethod
    def validate_lesson_update(instance, validated_data, request_user=None) -> None:
        """Validate lesson update business rules"""
        if request_user and not hasattr(request_user, 'role'):
            raise serializers.ValidationError("Invalid user object provided")
        
        instructor = validated_data.get('instructor', instance.instructor)
        school = validated_data.get('school', instance.school)
        lesson_date = validated_data.get('date', instance.date)
        duration = validated_data.get('duration', instance.duration)
        
        # Check instructor role if changed
        if 'instructor' in validated_data and instructor.role != 'I':
            raise serializers.ValidationError({
                'instructor': 'Selected user must be an instructor'
            })
        
        # Check if instructor is enrolled in this school
        if ('instructor' in validated_data or 'school' in validated_data) and not StudentProfile.objects.filter(
            user=instructor, 
            school=school,
            status='A'
        ).exists():
            raise serializers.ValidationError({
                'instructor': 'Instructor is not assigned to this school'
            })
        
        # Check school ownership - compare IDs instead of objects
        if request_user and school.owner.id != request_user.id:
            raise serializers.ValidationError({
                'school': 'You can only manage lessons in your own schools'
            })
        
        # Validate duration
        if 'duration' in validated_data and (duration < LessonService.MIN_DURATION or duration > LessonService.MAX_DURATION):
            raise serializers.ValidationError({
                'duration': f'Duration must be between {LessonService.MIN_DURATION} and {LessonService.MAX_DURATION} minutes'
            })
        
        # Check for scheduling conflicts (only if time-related fields changed)
        if any(field in validated_data for field in ['instructor', 'date', 'duration']):
            LessonService._check_scheduling_conflicts(instructor, lesson_date, duration, instance)

    @staticmethod
    def _check_scheduling_conflicts(instructor, lesson_date, duration, instance=None) -> None:
        """Prevent double-booking instructors"""
        lesson_end = lesson_date + timezone.timedelta(minutes=duration)
        
        # Find conflicting lessons (overlapping time slots)
        conflicting_lessons = Lesson.objects.filter(
            instructor=instructor,
            date__lt=lesson_end,
            date__gte=lesson_date - timezone.timedelta(hours=1)  # 1 hour buffer
        )
        
        # Exclude current instance for updates
        if instance:
            conflicting_lessons = conflicting_lessons.exclude(pk=instance.pk)
        
        if conflicting_lessons.exists():
            raise serializers.ValidationError({
                'instructor': 'Instructor has a scheduling conflict at this time'
            })

    @staticmethod
    def validate_lesson_data(attrs, instance=None) -> None:
        """Validate lesson data business rules"""
        lesson_type = attrs.get('lesson_type')
        duration = attrs.get('duration')
        date = attrs.get('date')
        
        # Validate lesson type
        if lesson_type and lesson_type not in ['T', 'D']:
            raise serializers.ValidationError({
                'lesson_type': "Lesson type must be 'T' (Theory) or 'D' (Driving)"
            })
        
        # Validate duration range
        if duration and (duration < LessonService.MIN_DURATION or duration > LessonService.MAX_DURATION):
            raise serializers.ValidationError({
                'duration': f'Duration must be between {LessonService.MIN_DURATION} and {LessonService.MAX_DURATION} minutes'
            })
        
        # Auto-update status based on date
        if date and instance:
            LessonService._update_lesson_status_based_on_date(instance, date)

    @staticmethod
    def _update_lesson_status_based_on_date(instance, new_date) -> None:
        """Update lesson status based on date changes"""
        current_time = timezone.now()
        
        if new_date > current_time and instance.status != 'S':
            instance.status = 'S'  # Scheduled
        elif new_date <= current_time and instance.status == 'S':
            instance.status = 'P'  # Paused (past lesson)

    @staticmethod
    @transaction.atomic
    def create_lesson(validated_data, request_user=None) -> Lesson:
        """Create lesson with business logic"""
        if not request_user or not request_user.is_authenticated:
            raise serializers.ValidationError('Authentication required to create a lesson')
        
        # Extract fields for validation
        instructor = validated_data.get('instructor')
        school = validated_data.get('school')
        lesson_date = validated_data.get('date')
        duration = validated_data.get('duration')
        
        # Validate creation
        LessonService.validate_lesson_creation(instructor, school, lesson_date, duration, request_user)
        
        # Create the lesson
        return Lesson.objects.create(**validated_data)

    @staticmethod
    @transaction.atomic
    def update_lesson(instance, validated_data) -> Lesson:
        """Update lesson with business logic"""
        # Prevent changing school (business rule)
        if 'school' in validated_data and validated_data['school'] != instance.school:
            raise serializers.ValidationError("Cannot change the school of an existing lesson")
        
        # Update instance
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        instance.save()
        return instance

    @staticmethod
    def mark_lesson_completed(lesson) -> Lesson:
        """Mark lesson as completed and update related records"""
        if lesson.status == 'C':
            return lesson  # Already completed
        
        lesson.status = 'C'
        lesson.save()
        
        # Update student progress based on attendance
        LessonService._update_student_progress_from_completed_lesson(lesson)
        
        return lesson

    @staticmethod
    def _update_student_progress_from_completed_lesson(lesson) -> None:
        """Update student progress when lesson is completed"""
        attendances = lesson.lesson_attendance.filter(presence=True)
        
        for attendance in attendances:
            StudentProfileService.update_progress_from_attendance(
                attendance.student,
                lesson.lesson_type,
                attendance.hours_completed
            )
            
            # Check for auto-completion
            StudentProfileService.auto_complete_student(attendance.student)

    @staticmethod
    def get_lesson_statistics(lesson) -> dict:
        """Get comprehensive statistics for a lesson"""
        total_enrolled = lesson.lesson_attendance.count()
        present_students = lesson.lesson_attendance.filter(presence=True).count()
        average_hours_completed = lesson.lesson_attendance.filter(
            presence=True
        ).aggregate(
            avg_hours=Avg('hours_completed')
        )['avg_hours'] or 0
        
        return {
            'total_enrolled': total_enrolled,
            'present_students': present_students,
            'absent_students': total_enrolled - present_students,
            'attendance_rate': round((present_students / total_enrolled * 100), 2) if total_enrolled > 0 else 0,
            'average_hours_completed': round(average_hours_completed, 2),
            'completion_percentage': LessonService.calculate_completion_percentage(lesson)
        }

    @staticmethod
    def can_modify_lesson(user, lesson) -> bool:
        """Check if user has permission to modify this lesson"""
        # Compare IDs instead of objects to avoid identity issues
        if user.role == 'A':
            return True
        if user.role == 'I':
            return True
        return False



class ReportService:
    """Generate and send reports"""
    
    @staticmethod
    def send_weekly_report(school, summary):
        """Send weekly report email to school owner"""
        from django.core.mail import send_mail
        
        subject = f"📊 Weekly Report for {school.name}"
        
        message = f"""
        Hello {school.owner.get_full_name()},
        
        Here's your weekly performance report for {school.name}:
        
        📈 Performance Summary:
        - Average Completion Rate: {summary['summary_metrics']['avg_completion_rate']:.1f}%
        - Average Rating: {summary['summary_metrics']['avg_rating']:.1f}/5
        - New Students: {summary['summary_metrics']['total_new_students']}
        - Lessons Completed: {summary['summary_metrics']['total_lessons']}
        - Instructor Utilization: {summary['summary_metrics']['avg_instructor_utilization']:.1f}%
        
        View detailed analytics in your dashboard.
        
        Best regards,
        Driving School Management System
        """
        
        send_mail(
            subject=subject,
            message=message,
            from_email='noreply@drivingschool.com',
            recipient_list=[school.owner.email],
            fail_silently=False
        )


class AnalyticsService:
    """Generate comprehensive school analytics and insights with performance optimizations"""
    
    # Cache timeout in seconds (1 hour)
    CACHE_TIMEOUT = 3600
    
    
    @staticmethod
    def calculate_growth_rate(analytics_obj):
        """Calculate student growth rate compared to previous day"""
        try:
            previous_day = SchoolAnalytics.objects.filter(
                school=analytics_obj.school,
                date__lt=analytics_obj.date
            ).order_by('-date').first()
            
            if previous_day and previous_day.total_students > 0:
                growth = ((analytics_obj.total_students - previous_day.total_students) / 
                         previous_day.total_students * 100)
                return round(growth, 2)
            return 0.0
        except Exception:
            return 0.0

    @staticmethod
    def format_completion_percentage(completion_rate):
        """Format completion rate as readable percentage"""
        return f"{completion_rate}%"

    @staticmethod
    def format_revenue(revenue):
        """Format revenue with currency symbol"""
        return f"${revenue:,.2f}"

    @staticmethod
    def generate_performance_summary(analytics_obj):
        """Generate performance summary with None handling"""
        if not analytics_obj:
            return {
                'status': 'no_data',
                'highlights': ['No analytics data available'],
                'concerns': []
            }
        
        summary = {
            'status': 'good',
            'highlights': [],
            'concerns': []
        }
        
        # Evaluate metrics (with safe attribute access)
        if analytics_obj.completion_rate >= 80:
            summary['highlights'].append('High completion rate')
        elif analytics_obj.completion_rate < 50:
            summary['concerns'].append('Low completion rate')
        
        if analytics_obj.average_rating >= 4.5:
            summary['highlights'].append('Excellent student satisfaction')
        elif analytics_obj.average_rating < 3.0:
            summary['concerns'].append('Poor student ratings')
        
        if analytics_obj.instructor_utilization >= 80:
            summary['highlights'].append('Optimal instructor utilization')
        elif analytics_obj.instructor_utilization < 50:
            summary['concerns'].append('Low instructor utilization')
        
        # Determine overall status
        if len(summary['concerns']) > 2:
            summary['status'] = 'needs_attention'
        elif len(summary['highlights']) > 2:
            summary['status'] = 'excellent'
        
        return summary

    @staticmethod
    def validate_analytics_data(school, date, attrs):
        """Validate analytics data - extracted from serializer"""
        # Validate date is not in the future
        if date and date > timezone.now().date():
            raise serializers.ValidationError({
                'date': 'Analytics date cannot be in the future'
            })

        # Validate numeric consistency
        total_students = attrs.get('total_students', 0)
        active_students = attrs.get('active_students', 0)
        
        if active_students > total_students:
            raise serializers.ValidationError({
                'active_students': 'Active students cannot exceed total students'
            })

        # Validate percentages
        completion_rate = attrs.get('completion_rate')
        if completion_rate is not None and (completion_rate < 0 or completion_rate > 100):
            raise serializers.ValidationError({
                'completion_rate': 'Completion rate must be between 0 and 100'
            })

        instructor_utilization = attrs.get('instructor_utilization')
        if instructor_utilization is not None and (instructor_utilization < 0 or instructor_utilization > 100):
            raise serializers.ValidationError({
                'instructor_utilization': 'Instructor utilization must be between 0 and 100'
            })

        # Validate rating
        average_rating = attrs.get('average_rating')
        if average_rating is not None and (average_rating < 0 or average_rating > 5):
            raise serializers.ValidationError({
                'average_rating': 'Average rating must be between 0 and 5'
            })


    @staticmethod
    def generate_daily_analytics(school, date=None, force_refresh=False):
        """Generate analytics for a specific day with caching and performance optimizations"""
        if date is None:
            date = timezone.now().date()
        
        cache_key = f"analytics_{school.id}_{date}"
        
        # Return cached analytics if available and not forcing refresh
        if not force_refresh:
            cached_analytics = cache.get(cache_key)
            if cached_analytics:
                logger.info(f"Returning cached analytics for school {school.id} on {date}")
                return cached_analytics
        
        try:
            with transaction.atomic():
                # Get or create analytics record with select_for_update to prevent race conditions
                analytics, created = SchoolAnalytics.objects.select_for_update().get_or_create(
                    school=school,
                    date=date,
                    defaults=AnalyticsService._calculate_initial_metrics(school, date)
                )
                
                # Only recalculate if forced or record was just created
                if force_refresh or created:
                    metrics = AnalyticsService._calculate_all_metrics(school, date)
                    for key, value in metrics.items():
                        setattr(analytics, key, value)
                    analytics.save()
                
                # Cache the result
                cache.set(cache_key, analytics, AnalyticsService.CACHE_TIMEOUT)
                logger.info(f"Generated analytics for school {school.id} on {date}")
                
                return analytics
                
        except Exception as e:
            logger.error(f"Error generating analytics for school {school.id} on {date}: {str(e)}")
            raise
    
    @staticmethod
    def _calculate_initial_metrics(school, date):
        """Calculate initial metrics for new analytics record"""
        return {
            'total_students': 0,
            'active_students': 0,
            'new_students': 0,
            'completion_rate': 0,
            'average_rating': 0,
            'lessons_completed': 0,
            'instructor_utilization': 0,
            'revenue': 0
        }
    
    @staticmethod
    def _calculate_all_metrics(school, date):
        """Calculate all analytics metrics in optimized queries"""
        # Student metrics in single query
        student_metrics = StudentProfile.objects.filter(
            school=school
        ).aggregate(
            total_students=Count('id'),
            active_students=Count('id', filter=Q(status='A')),
            completed_students=Count('id', filter=Q(status='C')),
            new_students_today=Count('id', filter=Q(joined_at__date=date))
        )
        
        # Completion rate
        total = student_metrics['total_students']
        completed = student_metrics['completed_students']
        completion_rate = (completed / total * 100) if total > 0 else 0
        
        # Feedback metrics
        feedback_metrics = Feedback.objects.filter(
            lesson__school=school,
            created_at__date=date
        ).aggregate(
            avg_rating=Avg('rating'),
            feedback_count=Count('id')
        )
        
        # Lesson metrics
        lesson_metrics = Lesson.objects.filter(
            school=school,
            date__date=date
        ).aggregate(
            completed_lessons=Count('id', filter=Q(status='C')),
            scheduled_lessons=Count('id', filter=Q(status='S')),
            total_lessons=Count('id')
        )
        
        # Instructor metrics
        instructor_metrics = AnalyticsService._calculate_instructor_metrics(school, date)
        
        # Revenue metrics (if you have payment data)
        revenue_metrics = AnalyticsService._calculate_revenue_metrics(school, date)
        
        return {
            'total_students': student_metrics['total_students'],
            'active_students': student_metrics['active_students'],
            'new_students': student_metrics['new_students_today'],
            'completion_rate': completion_rate,
            'average_rating': feedback_metrics['avg_rating'] or 0,
            'lessons_completed': lesson_metrics['completed_lessons'],
            'instructor_utilization': instructor_metrics['utilization_rate'],
            'revenue': revenue_metrics['daily_revenue']
        }
    
    @staticmethod
    def _calculate_instructor_metrics(school, date):
        """Calculate instructor utilization and performance metrics"""
        # Get total active instructors
        total_instructors = StudentProfile.objects.filter(
            school=school,
            user__role='I',
            status='A'
        ).count()
        
        if total_instructors == 0:
            return {'utilization_rate': 0, 'active_instructors': 0}
        
        # Get instructors with lessons on the given date
        active_instructors = Lesson.objects.filter(
            school=school,
            date__date=date,
            status__in=['S', 'C']
        ).values('instructor').distinct().count()
        
        utilization_rate = (active_instructors / total_instructors * 100) if total_instructors > 0 else 0
        
        return {
            'utilization_rate': utilization_rate,
            'active_instructors': active_instructors,
            'total_instructors': total_instructors
        }
    
    @staticmethod
    def _calculate_revenue_metrics(school, date):
        """Calculate revenue metrics (placeholder - integrate with your payment system)"""
        # This is a placeholder - integrate with your actual payment model
        # Example: Payment.objects.filter(school=school, paid_date=date, status='completed')
        return {
            'daily_revenue': 0,
            'payments_count': 0,
            'average_payment': 0
        }
    
    @staticmethod
    def get_school_summary(school, days=30, use_cache=True):
        """Get comprehensive school performance summary for last N days"""
        cache_key = f"school_summary_{school.id}_{days}"
        
        if use_cache:
            cached_summary = cache.get(cache_key)
            if cached_summary:
                return cached_summary
        
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=days)
        
        try:
            # Use database aggregation for better performance
            analytics_data = SchoolAnalytics.objects.filter(
                school=school,
                date__gte=start_date,
                date__lte=end_date
            ).aggregate(
                avg_completion_rate=Avg('completion_rate'),
                avg_rating=Avg('average_rating'),
                total_new_students=Sum('new_students'),
                total_lessons=Sum('lessons_completed'),
                avg_instructor_utilization=Avg('instructor_utilization'),
                total_revenue=Sum('revenue'),
                data_points=Count('id')
            )
            
            # Calculate additional real-time metrics
            real_time_metrics = AnalyticsService._get_real_time_metrics(school, days)
            
            # Calculate trends
            trends = AnalyticsService._calculate_trends(school, start_date, end_date, days)
            
            summary = {
                'period': f'Last {days} days',
                'summary_metrics': {
                    'avg_completion_rate': round(analytics_data['avg_completion_rate'] or 0, 2),
                    'avg_rating': round(analytics_data['avg_rating'] or 0, 2),
                    'total_new_students': analytics_data['total_new_students'] or 0,
                    'total_lessons': analytics_data['total_lessons'] or 0,
                    'avg_instructor_utilization': round(analytics_data['avg_instructor_utilization'] or 0, 2),
                    'total_revenue': analytics_data['total_revenue'] or 0,
                    'data_coverage': f"{(analytics_data['data_points'] or 0)}/{days} days"
                },
                'real_time_metrics': real_time_metrics,
                'trends': trends,
                'performance_indicators': AnalyticsService._get_performance_indicators(
                    analytics_data, real_time_metrics
                )
            }
            
            if use_cache:
                cache.set(cache_key, summary, AnalyticsService.CACHE_TIMEOUT // 2)  # Shorter cache for summaries
                
            return summary
            
        except Exception as e:
            logger.error(f"Error generating school summary for {school.id}: {str(e)}")
            return AnalyticsService._get_fallback_summary(school, days)
    
    @staticmethod
    def _get_real_time_metrics(school, days):
        """Get real-time metrics not stored in daily analytics"""
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)
        
        # Current active students (enrolled within period and still active)
        current_active = StudentProfile.objects.filter(
            school=school,
            status='A',
            joined_at__gte=start_date
        ).count()
        
        # Lessons scheduled for today
        today_lessons = Lesson.objects.filter(
            school=school,
            date__date=timezone.now().date()
        ).count()
        
        # Pending feedback requests
        pending_feedback = Lesson.objects.filter(
            school=school,
            status='C',
            date__gte=start_date
        ).exclude(
            lesson_feedback__isnull=False
        ).count()
        
        return {
            'current_active_students': current_active,
            'today_lessons_scheduled': today_lessons,
            'pending_feedback_requests': pending_feedback,
            'student_satisfaction_score': AnalyticsService._calculate_satisfaction_score(school, days)
        }
    
    @staticmethod
    def _calculate_satisfaction_score(school, days):
        """Calculate comprehensive satisfaction score"""
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)
        
        feedback_stats = Feedback.objects.filter(
            lesson__school=school,
            created_at__gte=start_date
        ).aggregate(
            avg_rating=Avg('rating'),
            feedback_count=Count('id'),
            five_star=Count('id', filter=Q(rating=5))
        )
        
        if feedback_stats['feedback_count'] == 0:
            return 0
        
        # Calculate score based on average rating and 5-star percentage
        avg_rating = feedback_stats['avg_rating'] or 0
        five_star_percentage = (feedback_stats['five_star'] / feedback_stats['feedback_count']) * 100
        
        return round((avg_rating * 15) + (five_star_percentage * 0.4), 2)  # Weighted score
    
    @staticmethod
    def _calculate_trends(school, start_date, end_date, days):
        """Calculate performance trends compared to previous period"""
        previous_start = start_date - timedelta(days=days)
        previous_end = start_date - timedelta(days=1)
        
        current_period = SchoolAnalytics.objects.filter(
            school=school,
            date__gte=start_date,
            date__lte=end_date
        ).aggregate(
            avg_rating=Avg('average_rating'),
            total_students=Sum('new_students'),
            completion_rate=Avg('completion_rate')
        )
        
        previous_period = SchoolAnalytics.objects.filter(
            school=school,
            date__gte=previous_start,
            date__lte=previous_end
        ).aggregate(
            avg_rating=Avg('average_rating'),
            total_students=Sum('new_students'),
            completion_rate=Avg('completion_rate')
        )
        
        def calculate_trend(current, previous, field_name):
            if not previous or previous.get(field_name) is None or previous[field_name] == 0:
                return 'neutral'
            change = ((current.get(field_name) or 0) - previous[field_name]) / previous[field_name] * 100
            return 'up' if change > 5 else 'down' if change < -5 else 'stable'
        
        return {
            'rating_trend': calculate_trend(current_period, previous_period, 'avg_rating'),
            'enrollment_trend': calculate_trend(current_period, previous_period, 'total_students'),
            'completion_trend': calculate_trend(current_period, previous_period, 'completion_rate')
        }
    
    @staticmethod
    def _get_performance_indicators(analytics_data, real_time_metrics):
        """Generate performance indicators and alerts"""
        indicators = []
        
        # Completion rate indicator
        completion_rate = analytics_data['avg_completion_rate'] or 0
        if completion_rate < 30:
            indicators.append({'type': 'warning', 'message': 'Low completion rate needs attention'})
        elif completion_rate > 80:
            indicators.append({'type': 'success', 'message': 'Excellent completion rate'})
        
        # Student satisfaction indicator
        satisfaction = real_time_metrics['student_satisfaction_score']
        if satisfaction < 60:
            indicators.append({'type': 'warning', 'message': 'Low student satisfaction detected'})
        
        # Instructor utilization indicator
        utilization = analytics_data['avg_instructor_utilization'] or 0
        if utilization < 50:
            indicators.append({'type': 'info', 'message': 'Consider optimizing instructor schedules'})
        
        return indicators
    
    @staticmethod
    def _get_fallback_summary(school, days):
        """Provide fallback summary when analytics data is unavailable"""
        return {
            'period': f'Last {days} days',
            'summary_metrics': {
                'avg_completion_rate': 0,
                'avg_rating': 0,
                'total_new_students': 0,
                'total_lessons': 0,
                'avg_instructor_utilization': 0,
                'total_revenue': 0,
                'data_coverage': 'No data available'
            },
            'real_time_metrics': {
                'current_active_students': 0,
                'today_lessons_scheduled': 0,
                'pending_feedback_requests': 0,
                'student_satisfaction_score': 0
            },
            'trends': {
                'rating_trend': 'neutral',
                'enrollment_trend': 'neutral',
                'completion_trend': 'neutral'
            },
            'performance_indicators': [
                {'type': 'info', 'message': 'Analytics data still being collected'}
            ]
        }
    
    @staticmethod
    def bulk_generate_analytics(schools, start_date, end_date):
        """Generate analytics for multiple schools in bulk"""
        from django.utils.dateparse import parse_date
        
        current_date = start_date
        results = {'processed': 0, 'errors': []}
        
        while current_date <= end_date:
            for school in schools:
                try:
                    AnalyticsService.generate_daily_analytics(school, current_date, force_refresh=True)
                    results['processed'] += 1
                except Exception as e:
                    results['errors'].append({
                        'school': school.id,
                        'date': current_date,
                        'error': str(e)
                    })
            current_date += timedelta(days=1)
        
        return results
    
    @staticmethod
    def get_analytics_time_series(school, metric, days=30):
        """Get time series data for specific metric"""
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=days)
        
        data = SchoolAnalytics.objects.filter(
            school=school,
            date__gte=start_date,
            date__lte=end_date
        ).values('date').annotate(
            value=Avg(metric)
        ).order_by('date')
        
        return {
            'metric': metric,
            'period': f'Last {days} days',
            'data_points': list(data),
            'summary': {
                'min': min([d['value'] for d in data if d['value'] is not None]) if data else 0,
                'max': max([d['value'] for d in data if d['value'] is not None]) if data else 0,
                'avg': sum([d['value'] for d in data if d['value'] is not None]) / len(data) if data else 0
            }
        }
    

class StudentProgressService:
    """Handle comprehensive student progress tracking, predictions, and interventions"""
    
    # Configuration constants
    THEORY_TARGET_HOURS = 50
    DRIVING_TARGET_HOURS = 40
    MIN_WEEKS_FOR_ACCURATE_PREDICTION = 4
    CACHE_TIMEOUT = 1800  # 30 minutes
    
    # Risk factor thresholds
    RISK_THRESHOLDS = {
        'attendance_rate': 0.7,
        'theory_hours_alert': 10,
        'driving_hours_alert': 5,
        'progress_imbalance': 30,
        'weekly_hours_min': 2
    }



        

    @staticmethod
    def calculate_days_until_completion(prediction_obj):
        """Calculate days until predicted completion with None handling"""
        if prediction_obj is None or prediction_obj.predicted_completion_date is None:
            return None
        
        delta = prediction_obj.predicted_completion_date - timezone.now().date()
        return delta.days

    @staticmethod
    def calculate_risk_level(success_probability):
        """Calculate risk level based on success probability"""
        if success_probability >= 80:
            return 'low'
        elif success_probability >= 60:
            return 'medium'
        elif success_probability >= 40:
            return 'high'
        return 'critical'

    @staticmethod
    def format_confidence_percentage(confidence_level):
        """Convert confidence level to percentage"""
        return f"{confidence_level * 100:.0f}%"

    @staticmethod
    def validate_prediction_data(attrs):
        """Validate prediction data - extracted from serializer"""
        confidence_level = attrs.get('confidence_level')
        success_probability = attrs.get('success_probability')
        predicted_date = attrs.get('predicted_completion_date')

        # Validate confidence level (0.00 to 1.00)
        if confidence_level is not None and (confidence_level < 0 or confidence_level > 1):
            raise serializers.ValidationError({
                'confidence_level': 'Confidence level must be between 0 and 1'
            })

        # Validate success probability (0.00 to 100.00)
        if success_probability is not None and (success_probability < 0 or success_probability > 100):
            raise serializers.ValidationError({
                'success_probability': 'Success probability must be between 0 and 100'
            })

        # Validate predicted date is in the future
        if predicted_date and predicted_date < timezone.now().date():
            raise serializers.ValidationError({
                'predicted_completion_date': 'Predicted completion date must be in the future'
            })

        # Validate predicted date is reasonable (not more than 2 years)
        if predicted_date:
            max_date = timezone.now().date() + timedelta(days=730)
            if predicted_date > max_date:
                raise serializers.ValidationError({
                    'predicted_completion_date': 'Predicted date cannot be more than 2 years in the future'
                })

    @staticmethod
    def validate_risk_factors_structure(value):
        """Validate risk_factors JSON structure"""
        if not isinstance(value, dict):
            raise serializers.ValidationError("Risk factors must be a dictionary")
        return value

    @staticmethod
    def validate_recommendations_structure(value):
        """Validate recommendations JSON structure"""
        if not isinstance(value, list):
            raise serializers.ValidationError("Recommendations must be a list")
        
        # Ensure all recommendations are strings
        if not all(isinstance(item, str) for item in value):
            raise serializers.ValidationError("All recommendations must be strings")
        
        return value
    
    @staticmethod
    @transaction.atomic
    def update_hours_from_attendance(attendance) -> bool:
        """Update student hours when attendance is marked with comprehensive progress tracking"""
        try:
            student = attendance.student
            lesson = attendance.lesson
            hours = float(attendance.hours_completed)
            
            if not attendance.presence or hours == 0:
                return False
            
            # Get current values before update
            old_theory_hours = student.total_hours_theory
            old_driving_hours = student.total_hours_driving
            
            if lesson.lesson_type == 'T':
                student.total_hours_theory += hours
                student.progress_theory = min(
                    100, 
                    (student.total_hours_theory / StudentProgressService.THEORY_TARGET_HOURS) * 100
                )
            elif lesson.lesson_type == 'D':
                student.total_hours_driving += hours
                student.progress_driving = min(
                    100,
                    (student.total_hours_driving / StudentProgressService.DRIVING_TARGET_HOURS) * 100
                )
            
            student.save()
            
            # Clear progress cache
            cache_key = f"student_progress_{student.id}"
            cache.delete(cache_key)
            
            # Check for milestone achievements
            StudentProgressService._check_milestones(student, lesson.lesson_type, hours)
            
            # Trigger achievement check
            AchievementService.check_and_award(student)
            
            # Update performance prediction if significant progress made
            if (abs(student.total_hours_theory - old_theory_hours) > 2 or 
                abs(student.total_hours_driving - old_driving_hours) > 2):
                StudentProgressService.calculate_completion_estimate(student)
            
            logger.info(f"Updated progress for student {student.id}: {hours} hours in {lesson.lesson_type}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating hours from attendance {attendance.id}: {str(e)}")
            raise
    
    @staticmethod
    def _check_milestones(student, lesson_type: str, hours_completed: float):
        """Check and log significant progress milestones"""
        milestones = []
        
        if lesson_type == 'T':
            if student.total_hours_theory >= 25 and student.total_hours_theory - hours_completed < 25:
                milestones.append("Halfway through theory requirements")
            if student.total_hours_theory >= StudentProgressService.THEORY_TARGET_HOURS:
                milestones.append("Theory requirements completed!")
                
        elif lesson_type == 'D':
            if student.total_hours_driving >= 20 and student.total_hours_driving - hours_completed < 20:
                milestones.append("Halfway through driving requirements")
            if student.total_hours_driving >= StudentProgressService.DRIVING_TARGET_HOURS:
                milestones.append("Driving requirements completed!")
        
        # Log milestones for reporting
        for milestone in milestones:
            logger.info(f"Milestone achieved for student {student.id}: {milestone}")
    
    @staticmethod
    def _to_float(value):
        """Convert Decimal or any numeric type to float safely."""
        if value is None:
            return 0.0
        if isinstance(value, Decimal):
            return float(value)
        return float(value)
    @staticmethod
    def calculate_completion_estimate(student, force_refresh: bool = False) -> Optional['StudentPerformancePrediction']:
        """Predict student completion date with enhanced accuracy algorithm"""
        
        
        cache_key = f"completion_estimate_{student.id}"
        
        if not force_refresh:
            cached_prediction = cache.get(cache_key)
            if cached_prediction:
                return cached_prediction
        
        try:
            # Enhanced progress calculation
            progress_metrics = StudentProgressService._calculate_comprehensive_metrics(student)
            
            if not progress_metrics['has_sufficient_data']:
                return None
            
            # Calculate predicted completion date using multiple methods
            predicted_date = StudentProgressService._predict_completion_date(student, progress_metrics)
            
            # Calculate comprehensive success probability
            success_probability = StudentProgressService._calculate_success_probability(student, progress_metrics)
            
            # Determine confidence level based on data quality
            confidence_level = StudentProgressService._calculate_confidence_level(progress_metrics)
            
            # Identify risks and recommendations
            risk_factors = StudentProgressService._identify_comprehensive_risk_factors(student, progress_metrics)
            recommendations = StudentProgressService._generate_personalized_recommendations(student, progress_metrics, risk_factors)
            
            # Create or update prediction
            prediction, created = StudentPerformancePrediction.objects.update_or_create(
                student=student,
                defaults={
                    'predicted_completion_date': predicted_date,
                    'success_probability': success_probability,
                    'confidence_level': confidence_level,
                    'risk_factors': risk_factors,
                    'recommendations': recommendations,
                    'last_updated': timezone.now()
                }
            )
            
            # Cache the prediction
            cache.set(cache_key, prediction, StudentProgressService.CACHE_TIMEOUT)
            
            logger.info(f"Generated completion estimate for student {student.id}: {success_probability:.1f}% success probability")
            return prediction
            
        except Exception as e:
            logger.error(f"Error calculating completion estimate for student {student.id}: {str(e)}")
            return None
        
        
    
    @staticmethod
    def _calculate_comprehensive_metrics(student) -> Dict:
        """Calculate comprehensive progress metrics for prediction"""
        from .models import Attendance, Lesson
        
        # FIX: Convert everything to float for consistent calculations
        current_date = timezone.now().date()
        student_joined_date = student.joined_at.date()
        
        enrollment_days = (current_date - student_joined_date).days
        weeks_enrolled = float(enrollment_days) / 7.0  # FIX: Use float division
        
        # Attendance metrics
        attendance_stats = Attendance.objects.filter(student=student).aggregate(
            total_lessons=Count('id'),
            attended_lessons=Count('id', filter=Q(presence=True)),
            total_hours=Sum('hours_completed', filter=Q(presence=True))
        )
        
        # Recent activity (last 30 days)
        recent_cutoff = timezone.now() - timedelta(days=30)
        recent_activity = Attendance.objects.filter(
            student=student,
            lesson__date__gte=recent_cutoff
        ).aggregate(
            recent_lessons=Count('id'),
            recent_hours=Sum('hours_completed', filter=Q(presence=True))
        )
        
        # Convert all values to float to avoid Decimal/float issues
        total_lessons = float(attendance_stats['total_lessons'] or 0)
        attended_lessons = float(attendance_stats['attended_lessons'] or 0)
        total_hours = float(attendance_stats['total_hours'] or 0)
        recent_lessons = float(recent_activity['recent_lessons'] or 0)
        recent_hours = float(recent_activity['recent_hours'] or 0)
        
        # Calculate rates with float values
        attendance_rate = (attended_lessons / total_lessons) if total_lessons > 0 else 0.0
        recent_activity_ratio = (recent_lessons / max(1.0, total_lessons))
        
        # Calculate weekly averages with float values
        weekly_hours = 0.0
        if weeks_enrolled > 0:
            weekly_hours = (float(student.total_hours_theory) + float(student.total_hours_driving)) / weeks_enrolled
        
        recent_weekly_hours = 0.0
        if enrollment_days >= 30:
            recent_weekly_hours = recent_hours / 4.0  # 4 weeks
        
        # Lesson type distribution
        lesson_distribution = Attendance.objects.filter(
            student=student,
            presence=True
        ).values('lesson__lesson_type').annotate(
            count=Count('id'),
            total_hours=Sum('hours_completed')
        )
        
        return {
            'enrollment_days': enrollment_days,
            'weeks_enrolled': weeks_enrolled,
            'total_lessons': total_lessons,
            'attendance_rate': attendance_rate,
            'total_hours_completed': total_hours,
            'recent_activity_ratio': recent_activity_ratio,
            'weekly_hours': weekly_hours,
            'recent_weekly_hours': recent_weekly_hours,
            'lesson_distribution': {item['lesson__lesson_type']: item for item in lesson_distribution},
            'progress_balance': float(student.progress_theory) - float(student.progress_driving),
            'has_sufficient_data': enrollment_days >= 7 and total_lessons > 0
        }
    

    
    @staticmethod
    def _calculate_success_probability(student, metrics: Dict) -> float:
        """Calculate comprehensive success probability using multiple factors"""
        factors = []
        weights = []
        
        # Convert Decimal fields to float at the start
        progress_theory = float(student.progress_theory)
        progress_driving = float(student.progress_driving)
        
        # Attendance factor (25%)
        attendance_score = metrics['attendance_rate'] * 100
        factors.append(attendance_score)
        weights.append(0.25)
        
        # Progress factor (30%)
        progress_score = (progress_theory + progress_driving) / 2
        factors.append(progress_score)
        weights.append(0.30)
        
        # Consistency factor (20%)
        consistency_score = min(100, metrics['recent_activity_ratio'] * 100 * 1.5)
        factors.append(consistency_score)
        weights.append(0.20)
        
        # Pace factor (15%)
        required_weekly_hours = 4  # Target hours per week
        pace_score = min(100, (metrics['weekly_hours'] / required_weekly_hours) * 100)
        factors.append(pace_score)
        weights.append(0.15)
        
        # Balance factor (10%)
        balance_penalty = abs(metrics['progress_balance']) / 2  # Penalize large imbalances
        balance_score = max(0, 100 - balance_penalty)
        factors.append(balance_score)
        weights.append(0.10)
        
        # Calculate weighted probability
        success_probability = sum(f * w for f, w in zip(factors, weights))
        
        return min(100, max(0, success_probability))

    @staticmethod
    def _predict_completion_date(student, metrics: Dict):
        """Predict completion date using multiple calculation methods"""
        # Convert Decimal fields to float
        total_theory = float(student.total_hours_theory)
        total_driving = float(student.total_hours_driving)
        
        # Method 1: Linear projection based on current pace
        remaining_theory = max(0, StudentProgressService.THEORY_TARGET_HOURS - total_theory)
        remaining_driving = max(0, StudentProgressService.DRIVING_TARGET_HOURS - total_driving)
        remaining_total = remaining_theory + remaining_driving
        
        # Use recent weekly hours if available, otherwise overall average
        effective_weekly_hours = metrics['recent_weekly_hours'] if metrics['recent_weekly_hours'] > 0 else metrics['weekly_hours']
        
        if effective_weekly_hours > 0:
            weeks_remaining = remaining_total / effective_weekly_hours
        else:
            # Default to conservative estimate if no hours data
            weeks_remaining = 20  # 5 months
        
        # Adjust for attendance rate and recent activity
        attendance_factor = min(1.0, metrics['attendance_rate'] * 1.2)  # Bonus for good attendance
        activity_factor = min(1.0, metrics['recent_activity_ratio'] * 1.5)  # Bonus for recent activity
        
        adjusted_weeks = weeks_remaining / (attendance_factor * activity_factor)
        
        # Cap unrealistic predictions (too short or too long)
        adjusted_weeks = max(2, min(52, adjusted_weeks))  # Between 2 weeks and 1 year
        
        predicted_date = timezone.now().date() + timedelta(weeks=int(adjusted_weeks))
        
        return predicted_date

    @staticmethod
    def _calculate_confidence_level(metrics: Dict) -> float:
        """Calculate prediction confidence level based on data quality"""
        confidence_factors = []
        
        # Data quantity factor
        if metrics['weeks_enrolled'] >= 8:
            confidence_factors.append(1.0)
        elif metrics['weeks_enrolled'] >= 4:
            confidence_factors.append(0.75)
        elif metrics['weeks_enrolled'] >= 2:
            confidence_factors.append(0.5)
        else:
            confidence_factors.append(0.25)
        
        # Data consistency factor
        if metrics['total_lessons'] >= 10:
            confidence_factors.append(1.0)
        elif metrics['total_lessons'] >= 5:
            confidence_factors.append(0.8)
        elif metrics['total_lessons'] >= 2:
            confidence_factors.append(0.6)
        else:
            confidence_factors.append(0.3)
        
        # Recent activity factor
        confidence_factors.append(metrics['recent_activity_ratio'])
        
        return sum(confidence_factors) / len(confidence_factors)
    
    @staticmethod
    def _identify_comprehensive_risk_factors(student, metrics: Dict) -> Dict:
        """Identify comprehensive risk factors affecting student success"""
        risks = {}
        
        # Attendance risks
        if metrics['attendance_rate'] < StudentProgressService.RISK_THRESHOLDS['attendance_rate']:
            risks['poor_attendance'] = {
                'severity': 'high' if metrics['attendance_rate'] < 0.5 else 'medium',
                'message': f'Attendance rate is {metrics["attendance_rate"]:.0%}',
                'suggestion': 'Improve class attendance consistency'
            }
        
        # Progress risks
        if student.total_hours_theory < StudentProgressService.RISK_THRESHOLDS['theory_hours_alert']:
            risks['low_theory_progress'] = {
                'severity': 'medium',
                'message': f'Only {student.total_hours_theory} theory hours completed',
                'suggestion': 'Focus on theory lessons'
            }
        
        if student.total_hours_driving < StudentProgressService.RISK_THRESHOLDS['driving_hours_alert']:
            risks['low_driving_progress'] = {
                'severity': 'medium',
                'message': f'Only {student.total_hours_driving} driving hours completed',
                'suggestion': 'Schedule more driving practice'
            }
        
        # Pace risks
        if metrics['weekly_hours'] < StudentProgressService.RISK_THRESHOLDS['weekly_hours_min']:
            risks['slow_pace'] = {
                'severity': 'medium',
                'message': f'Average {metrics["weekly_hours"]:.1f} hours per week',
                'suggestion': 'Increase lesson frequency'
            }
        
        # Balance risks
        if abs(metrics['progress_balance']) > StudentProgressService.RISK_THRESHOLDS['progress_imbalance']:
            risks['progress_imbalance'] = {
                'severity': 'low',
                'message': 'Significant difference between theory and driving progress',
                'suggestion': 'Balance theory and practical lessons'
            }
        
        # Consistency risks
        if metrics['recent_activity_ratio'] < 0.3:
            risks['inconsistent_activity'] = {
                'severity': 'medium',
                'message': 'Low recent activity compared to overall',
                'suggestion': 'Maintain consistent lesson attendance'
            }
        
        return risks
    
    @staticmethod
    def _generate_personalized_recommendations(student, metrics: Dict, risk_factors: Dict) -> List[str]:
        """Generate personalized, actionable recommendations"""
        recommendations = []
        
        # Progress-based recommendations
        if student.progress_theory < 50:
            recommendations.append("Focus on completing theory modules to build foundational knowledge")
        
        if student.progress_driving < 50:
            recommendations.append("Increase driving practice to build confidence and skills")
        
        # Balance recommendations
        if metrics['progress_balance'] > 20:
            recommendations.append("Consider reducing theory focus and increasing driving practice")
        elif metrics['progress_balance'] < -20:
            recommendations.append("Balance driving practice with necessary theory lessons")
        
        # Pace recommendations
        if metrics['weekly_hours'] < 3:
            recommendations.append("Consider increasing lesson frequency to maintain momentum")
        elif metrics['weekly_hours'] > 10:
            recommendations.append("Current pace is excellent - maintain consistency")
        
        # Risk-based recommendations
        for risk in risk_factors.values():
            recommendations.append(risk['suggestion'])
        
        # Ensure we have at least basic recommendations
        if not recommendations:
            if metrics['weeks_enrolled'] < 2:
                recommendations.append("Continue with current learning plan - early stages look good")
            else:
                recommendations.append("Maintain current progress - you're on track for success")
        
        return recommendations[:5]  # Return top 5 recommendations
    
    @staticmethod
    def get_student_progress_report(student) -> Dict:
        """Generate comprehensive progress report for a student"""
        cache_key = f"progress_report_{student.id}"
        cached_report = cache.get(cache_key)
        
        if cached_report:
            return cached_report
        
        metrics = StudentProgressService._calculate_comprehensive_metrics(student)
        prediction = StudentProgressService.calculate_completion_estimate(student)
        
        report = {
            'student_info': {
                'name': student.user.get_full_name(),
                'joined_date': student.joined_at,
                'days_enrolled': metrics['enrollment_days'],
                'current_status': student.get_status_display()
            },
            'progress_summary': {
                'theory': {
                    'hours': student.total_hours_theory,
                    'progress': student.progress_theory,
                    'remaining': max(0, StudentProgressService.THEORY_TARGET_HOURS - student.total_hours_theory)
                },
                'driving': {
                    'hours': student.total_hours_driving,
                    'progress': student.progress_driving,
                    'remaining': max(0, StudentProgressService.DRIVING_TARGET_HOURS - student.total_hours_driving)
                },
                'overall_progress': (student.progress_theory + student.progress_driving) / 2
            },
            'attendance_metrics': {
                'total_lessons': metrics['total_lessons'],
                'attendance_rate': metrics['attendance_rate'],
                'total_hours_completed': metrics['total_hours_completed']
            },
            'performance_prediction': {
                'predicted_completion': prediction.predicted_completion_date if prediction else None,
                'success_probability': prediction.success_probability if prediction else 0,
                'confidence_level': prediction.confidence_level if prediction else 0,
                'risk_factors': prediction.risk_factors if prediction else {},
                'recommendations': prediction.recommendations if prediction else []
            } if prediction else None,
            'weekly_analysis': {
                'average_hours_per_week': metrics['weekly_hours'],
                'recent_weekly_hours': metrics['recent_weekly_hours'],
                'consistency_score': metrics['recent_activity_ratio'] * 100
            }
        }
        
        cache.set(cache_key, report, StudentProgressService.CACHE_TIMEOUT)
        return report
    
    @staticmethod
    def identify_at_risk_students(school, min_risk_score: float = 0.6) -> List[Dict]:
        """Identify students at risk of not completing successfully"""
        from .models import StudentProfile
        
        at_risk_students = []
        
        active_students = StudentProfile.objects.filter(
            school=school,
            status='A'
        ).select_related('user')
        
        for student in active_students:
            prediction = StudentProgressService.calculate_completion_estimate(student)
            
            if prediction and prediction.success_probability < (min_risk_score * 100):
                risk_factors = prediction.risk_factors or {}
                high_risk_factors = [rf for rf in risk_factors.values() if rf.get('severity') == 'high']
                
                at_risk_students.append({
                    'student': student,
                    'success_probability': prediction.success_probability,
                    'high_risk_factors': high_risk_factors,
                    'predicted_completion': prediction.predicted_completion_date,
                    'recommendations': prediction.recommendations or []
                })
        
        # Sort by risk level (lowest success probability first)
        at_risk_students.sort(key=lambda x: x['success_probability'])
        
        return at_risk_students


class AchievementService:
    """Award achievements based on milestones"""
    
    ACHIEVEMENT_RULES = {
        'first_lesson': {
            'title': 'First Steps',
            'description': 'Completed your first lesson',
            'points': 10,
            'icon': '🎯'
        },
        'theory_master': {
            'title': 'Theory Master',
            'description': 'Completed 50 hours of theory',
            'points': 100,
            'icon': '📚'
        },
        'driving_ace': {
            'title': 'Driving Ace',
            'description': 'Completed 40 hours of driving',
            'points': 150,
            'icon': '🚗'
        },
        'perfect_attendance': {
            'title': 'Perfect Attendance',
            'description': '100% attendance for 10 lessons',
            'points': 75,
            'icon': '✨'
        }
    }
    
    @staticmethod
    def check_and_award(student):
        """Check and award all eligible achievements"""
        from .models import Achievement, Attendance
        
        # Check first lesson
        if not Achievement.objects.filter(student=student, type='first_lesson').exists():
            if Attendance.objects.filter(student=student, presence=True).exists():
                AchievementService._award_achievement(student, 'first_lesson')
        
        # Check theory master
        if not Achievement.objects.filter(student=student, type='theory_master').exists():
            if student.total_hours_theory >= 50:
                AchievementService._award_achievement(student, 'theory_master')
        
        # Check driving ace
        if not Achievement.objects.filter(student=student, type='driving_ace').exists():
            if student.total_hours_driving >= 40:
                AchievementService._award_achievement(student, 'driving_ace')
        
        # Check perfect attendance
        if not Achievement.objects.filter(student=student, type='perfect_attendance').exists():
            total_lessons = Attendance.objects.filter(student=student).count()
            if total_lessons >= 10:
                present = Attendance.objects.filter(
                    student=student, 
                    presence=True
                ).count()
                if present == total_lessons:
                    AchievementService._award_achievement(student, 'perfect_attendance')
    
    @staticmethod
    def _award_achievement(student, achievement_type):
        """Award a specific achievement"""
        from .models import Achievement
        
        rule = AchievementService.ACHIEVEMENT_RULES.get(achievement_type)
        if not rule:
            return
        
        Achievement.objects.create(
            student=student,
            type=achievement_type,
            title=rule['title'],
            description=rule['description'],
            icon=rule['icon'],
            points=rule['points']
        )


class AttendanceService:
    """Handle all Attendance business logic and operations"""
    
    # Configuration
    THEORY_TARGET_HOURS = 50
    DRIVING_TARGET_HOURS = 40
    
    @staticmethod
    def validate_attendance_creation(student, lesson, presence, hours_completed, request_user=None) -> None:
        """Validate attendance creation business rules"""
        # Check for duplicate attendance
        if Attendance.objects.filter(student=student, lesson=lesson).exists():
            raise serializers.ValidationError({
                'student': 'Attendance already recorded for this student in this lesson'
            })
        
        # Validate lesson date
        if lesson.date > timezone.now():
            raise serializers.ValidationError({
                'lesson': 'Cannot mark attendance for future lessons'
            })
        
        # Validate school enrollment
        if student.school != lesson.school:
            raise serializers.ValidationError({
                'student': 'Student is not enrolled in this school'
            })
        
        # Validate presence and hours logic
        AttendanceService._validate_presence_hours_logic(presence, hours_completed, lesson)
        
        # Validate user permissions
        AttendanceService._validate_user_permissions(request_user, student)

    @staticmethod
    def validate_attendance_update(instance, validated_data, request_user=None) -> None:
        """Validate attendance update business rules"""
        student = validated_data.get('student', instance.student)
        lesson = validated_data.get('lesson', instance.lesson)
        presence = validated_data.get('presence', instance.presence)
        hours_completed = validated_data.get('hours_completed', instance.hours_completed)
        
        # Check if changing student or lesson (should not be allowed)
        if 'student' in validated_data and validated_data['student'] != instance.student:
            raise serializers.ValidationError({
                'student': 'Cannot change student for existing attendance'
            })
        
        if 'lesson' in validated_data and validated_data['lesson'] != instance.lesson:
            raise serializers.ValidationError({
                'lesson': 'Cannot change lesson for existing attendance'
            })
        
        # Validate school enrollment
        if student.school != lesson.school:
            raise serializers.ValidationError({
                'student': 'Student is not enrolled in this school'
            })
        
        # Validate presence and hours logic
        AttendanceService._validate_presence_hours_logic(presence, hours_completed, lesson)
        
        # Validate user permissions
        AttendanceService._validate_user_permissions(request_user, student)

    @staticmethod
    def _validate_presence_hours_logic(presence, hours_completed, lesson) -> None:
        """Validate the relationship between presence and hours completed"""
        # Cannot have hours when absent
        if presence is False and hours_completed and hours_completed > 0:
            raise serializers.ValidationError({
                'hours_completed': 'Cannot have hours completed when marked absent'
            })
        
        # Must have hours when present
        if presence is True and (hours_completed is None or hours_completed == 0):
            raise serializers.ValidationError({
                'hours_completed': 'Must record hours completed when present'
            })
        
        # Hours cannot exceed lesson duration
        if hours_completed and lesson and hours_completed > lesson.duration:
            raise serializers.ValidationError({
                'hours_completed': f'Hours completed cannot exceed lesson duration ({lesson.duration} minutes)'
            })

    @staticmethod
    def _validate_user_permissions(request_user, student) -> None:
        """Validate user has permission to modify attendance"""
        if not request_user or not request_user.is_authenticated:
            raise serializers.ValidationError('Authentication required')
        
        # Students can only mark their own attendance
        if request_user.role == 'S' and request_user != student.user:
            raise serializers.ValidationError({
                'student': 'You can only mark your own attendance'
            })
        
        # Instructors and admins need school permissions
        if request_user.role in ['I', 'A']:
            if not AttendanceService._has_school_permission(request_user, student.school):
                raise serializers.ValidationError({
                    'student': 'You do not have permission to manage attendance for this school'
                })

    @staticmethod
    def _has_school_permission(user, school) -> bool:
        """Check if user has permission to manage school attendance"""
        if user.role == 'A' and user.is_staff:
            return True

        if user.role == 'A' and school.owner == user:
            return True
        
        if user.role == 'I':
            # Check if instructor is assigned to this school
            return StudentProfile.objects.filter(
                user=user, 
                school=school, 
                status='A'
            ).exists()
        
        return False

    @staticmethod
    @transaction.atomic
    def create_attendance(validated_data, request_user=None) -> Attendance:
        """Create attendance record with business logic"""
        if not request_user or not request_user.is_authenticated:
            raise serializers.ValidationError('Authentication required to create attendance')
        
        # Extract fields for validation
        student = validated_data.get('student')
        lesson = validated_data.get('lesson')
        presence = validated_data.get('presence')
        hours_completed = validated_data.get('hours_completed')
        
        # Validate creation
        AttendanceService.validate_attendance_creation(
            student, lesson, presence, hours_completed, request_user
        )
        
        # Create attendance
        attendance = Attendance.objects.create(**validated_data)
        
        # Update student progress if present
        if attendance.presence and attendance.hours_completed > 0:
            AttendanceService._update_student_progress(
                attendance.student, 
                attendance.lesson.lesson_type,
                attendance.hours_completed,
                operation='add'
            )
        
        return attendance

    @staticmethod
    @transaction.atomic
    def update_attendance(instance, validated_data) -> Attendance:
        """Update attendance record with business logic"""
        # Store old values for progress calculation
        old_hours = instance.hours_completed
        old_presence = instance.presence
        old_lesson_type = instance.lesson.lesson_type
        
        # Prevent changing student and lesson
        validated_data.pop('student', None)
        validated_data.pop('lesson', None)
        
        # Update instance
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        instance.save()
        
        # Handle progress updates if hours or presence changed
        if any(field in validated_data for field in ['hours_completed', 'presence']):
            AttendanceService._handle_progress_update(
                instance, old_hours, old_presence, old_lesson_type
            )
        
        return instance

    @staticmethod
    def _handle_progress_update(attendance, old_hours, old_presence, old_lesson_type) -> None:
        """Handle student progress updates when attendance changes"""
        student = attendance.student
        
        # Remove old progress if previously present with hours
        if old_presence and old_hours > 0:
            AttendanceService._update_student_progress(
                student, old_lesson_type, old_hours, operation='subtract'
            )
        
        # Add new progress if currently present with hours
        if attendance.presence and attendance.hours_completed > 0:
            AttendanceService._update_student_progress(
                student, 
                attendance.lesson.lesson_type, 
                attendance.hours_completed, 
                operation='add'
            )

    @staticmethod
    def _update_student_progress(student, lesson_type, hours, operation) -> None:
        """Update student progress based on attendance"""
        hours_float = float(hours)
        
        if lesson_type == 'T':  # Theory
            if operation == 'add':
                student.total_hours_theory += hours_float
                student.progress_theory = min(100, (student.total_hours_theory / AttendanceService.THEORY_TARGET_HOURS) * 100)
            else:  # subtract
                student.total_hours_theory = max(0, student.total_hours_theory - hours_float)
                student.progress_theory = min(100, (student.total_hours_theory / AttendanceService.THEORY_TARGET_HOURS) * 100)
                
        elif lesson_type == 'D':  # Driving
            if operation == 'add':
                student.total_hours_driving += hours_float
                student.progress_driving = min(100, (student.total_hours_driving / AttendanceService.DRIVING_TARGET_HOURS) * 100)
            else:  # subtract
                student.total_hours_driving = max(0, student.total_hours_driving - hours_float)
                student.progress_driving = min(100, (student.total_hours_driving / AttendanceService.DRIVING_TARGET_HOURS) * 100)
        
        student.save()
        
        # Check for auto-completion
        StudentProfileService.auto_complete_student(student)

    @staticmethod
    def get_attendance_rate(student) -> float:
        """Calculate student's overall attendance rate"""
        total_lessons = Attendance.objects.filter(student=student).count()
        if total_lessons == 0:
            return 0.0
        
        present_lessons = Attendance.objects.filter(
            student=student,
            presence=True
        ).count()
        
        return round((present_lessons / total_lessons) * 100, 2)

    @staticmethod
    def get_lesson_attendance_rate(lesson) -> float:
        """Calculate attendance rate for a specific lesson"""
        total_enrolled = lesson.lesson_attendance.count()
        if total_enrolled == 0:
            return 0.0
        
        present_students = lesson.lesson_attendance.filter(presence=True).count()
        return round((present_students / total_enrolled) * 100, 2)

    @staticmethod
    def get_student_statistics(student) -> dict:
        """Get comprehensive attendance statistics for a student"""
        attendances = Attendance.objects.filter(student=student)
        total_lessons = attendances.count()
        attended = attendances.filter(presence=True).count()
        missed = total_lessons - attended
        
        total_hours = attendances.filter(presence=True).aggregate(
            total_hours=Sum('hours_completed')
        )['total_hours'] or 0
        
        # Calculate hours by lesson type
        theory_hours = attendances.filter(
            presence=True,
            lesson__lesson_type='T'
        ).aggregate(
            total=Sum('hours_completed')
        )['total'] or 0
        
        driving_hours = attendances.filter(
            presence=True,
            lesson__lesson_type='D'
        ).aggregate(
            total=Sum('hours_completed')
        )['total'] or 0
        
        return {
            'total_lessons': total_lessons,
            'attended': attended,
            'missed': missed,
            'attendance_rate': AttendanceService.get_attendance_rate(student),
            'total_hours': float(total_hours),
            'theory_hours': float(theory_hours),
            'driving_hours': float(driving_hours),
            'completion_percentage': StudentProfileService.calculate_completion_percentage(student)
        }

    @staticmethod
    def get_lesson_statistics(lesson) -> dict:
        """Get comprehensive statistics for a lesson"""
        attendances = lesson.lesson_attendance.all()
        total_enrolled = attendances.count()
        present_students = attendances.filter(presence=True).count()
        absent_students = total_enrolled - present_students
        
        average_hours = attendances.filter(presence=True).aggregate(
            avg_hours=Avg('hours_completed')
        )['avg_hours'] or 0
        
        total_hours = attendances.filter(presence=True).aggregate(
            total_hours=Sum('hours_completed')
        )['total_hours'] or 0
        
        return {
            'total_enrolled': total_enrolled,
            'present_students': present_students,
            'absent_students': absent_students,
            'attendance_rate': AttendanceService.get_lesson_attendance_rate(lesson),
            'average_hours_completed': round(float(average_hours), 2),
            'total_hours_completed': float(total_hours)
        }

    @staticmethod
    def can_modify_attendance(user, attendance) -> bool:
        """Check if user has permission to modify attendance"""
        if user.role == 'S':
            return user == attendance.student.user
        
        if user.role == 'A' and user.is_staff:
            return True

        if user.role == 'A':
            return attendance.student.school.owner == user
        
        if user.role == 'I':
            return (attendance.lesson.instructor == user and 
                    AttendanceService._has_school_permission(user, attendance.student.school))
        
        return False

class CommunicationService:
    """Handle all automated messaging business logic"""
    
    # Configuration
    MAX_PAST_SCHEDULING_DAYS = 30
    
    @staticmethod
    def validate_message_creation(student, template, scheduled_for, user=None) -> None:
        """Validate message creation business rules"""
        # Validate student and template belong to same school
        if student.school != template.school:
            raise serializers.ValidationError({
                'student': 'Student must belong to the same school as the template'
            })

        # Validate template is active
        if not template.is_active:
            raise serializers.ValidationError({
                'template': 'Cannot use an inactive template'
            })

        # Validate scheduled time is reasonable
        if scheduled_for < timezone.now() - timedelta(days=CommunicationService.MAX_PAST_SCHEDULING_DAYS):
            raise serializers.ValidationError({
                'scheduled_for': f'Cannot schedule messages more than {CommunicationService.MAX_PAST_SCHEDULING_DAYS} days in the past'
            })

        # Validate permissions if user provided
        if user and template.school.owner != user:
            raise serializers.ValidationError({
                'template': 'You can only create messages for your own school'
            })

    @staticmethod
    def validate_message_update(instance, validated_data) -> None:
        """Validate message update business rules"""
        student = validated_data.get('student', instance.student)
        template = validated_data.get('template', instance.template)
        status = validated_data.get('status', instance.status)
        
        # Prevent changing student/template
        if 'student' in validated_data and student != instance.student:
            raise serializers.ValidationError("Cannot change the student of existing message")
        
        if 'template' in validated_data and template != instance.template:
            raise serializers.ValidationError("Cannot change the template of existing message")
        
        # Validate status transitions
        if 'status' in validated_data:
            CommunicationService._validate_status_transition(instance.status, status)

    @staticmethod
    def _validate_status_transition(current_status, new_status) -> None:
        """Validate status transition logic"""
        valid_transitions = {
            'pending': ['sent', 'failed'],
            'sent': ['delivered', 'failed'],
            'delivered': ['read'],
            'failed': ['pending'],  # Can retry
            'read': []  # Final state
        }
        
        if new_status != current_status:
            if new_status not in valid_transitions.get(current_status, []):
                raise serializers.ValidationError(
                    f"Cannot transition from {current_status} to {new_status}"
                )

    @staticmethod
    def get_is_overdue(message) -> bool:
        """Check if message is overdue to be sent"""
        return message.status == 'pending' and message.scheduled_for < timezone.now()

    @staticmethod
    def get_time_until_send(message) -> str:
        """Get human-readable time until scheduled send"""
        if message.status != 'pending':
            return None
        
        now = timezone.now()
        if message.scheduled_for < now:
            delta = now - message.scheduled_for
            return f"Overdue by {delta.days} days" if delta.days > 0 else "Overdue"
        
        delta = message.scheduled_for - now
        hours = delta.total_seconds() / 3600
        
        if hours < 1:
            minutes = int(delta.total_seconds() / 60)
            return f"In {minutes} minutes"
        elif hours < 24:
            return f"In {int(hours)} hours"
        else:
            return f"In {delta.days} days"

    @staticmethod
    @transaction.atomic
    def create_message(validated_data, user=None) -> AutomatedMessage:
        """Create automated message with business logic"""
        student = validated_data.get('student')
        template = validated_data.get('template')
        scheduled_for = validated_data.get('scheduled_for')
        
        # Validate creation
        CommunicationService.validate_message_creation(student, template, scheduled_for, user)
        
        # Create the message
        return AutomatedMessage.objects.create(**validated_data)

    @staticmethod
    @transaction.atomic
    def update_message(instance, validated_data) -> AutomatedMessage:
        """Update message with business logic"""
        # Validate update
        CommunicationService.validate_message_update(instance, validated_data)
        
        # If status is changing to 'sent', set sent_at
        new_status = validated_data.get('status')
        if new_status == 'sent' and instance.status != 'sent':
            validated_data['sent_at'] = timezone.now()
        
        # Update instance (student/template already validated as unchanged)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        instance.save()
        return instance

    @staticmethod
    def send_scheduled_messages():
        """Send all pending messages (call from Celery task)"""
        pending_messages = AutomatedMessage.objects.filter(
            status='pending',
            scheduled_for__lte=timezone.now()
        )
        
        for message in pending_messages:
            try:
                CommunicationService._send_single_message(message)
                message.status = 'sent'
                message.sent_at = timezone.now()
                message.save()
            except Exception as e:
                message.status = 'failed'
                message.delivery_error = str(e)
                message.save()

    @staticmethod
    def _send_single_message(message):
        """Actually send a single message"""
        content = CommunicationService._render_template(message.template, message.student)
        
        from django.core.mail import send_mail
        send_mail(
            subject=content['subject'],
            message=content['body'],
            from_email='noreply@drivingschool.com',
            recipient_list=[message.student.user.email],
            fail_silently=False
        )

    @staticmethod
    def _render_template(template, student):
        """Render template with student variables"""
        context = {
            'student_name': student.user.get_full_name() or student.user.username,
            'progress_theory': student.progress_theory,
            'progress_driving': student.progress_driving,
            'school_name': student.school.name,
            'license_type': student.get_license_type_display(),
            'total_hours_theory': student.total_hours_theory,  
            'total_hours_driving': student.total_hours_driving,  
        }
        
        subject = template.subject
        body = template.body
        
        for key, value in context.items():
            placeholder = f'{{{key}}}'
            subject = subject.replace(placeholder, str(value))
            body = body.replace(placeholder, str(value))
        
        return {'subject': subject, 'body': body}

    @staticmethod
    def get_message_statistics(school=None):
        """Get messaging statistics"""
        queryset = AutomatedMessage.objects.all()
        if school:
            queryset = queryset.filter(template__school=school)
            
        total = queryset.count()
        by_status = queryset.values('status').annotate(count=Count('id'))
        
        return {
            'total_messages': total,
            'by_status': {item['status']: item['count'] for item in by_status},
            'delivery_rate': CommunicationService._calculate_delivery_rate(queryset)
        }

    @staticmethod
    def _calculate_delivery_rate(queryset):
        """Calculate successful delivery rate"""
        successful = queryset.filter(status__in=['sent', 'delivered', 'read']).count()
        total = queryset.count()
        return round((successful / total) * 100, 2) if total > 0 else 0
    
    
    @staticmethod
    def notify_at_risk_student(student, risk_factors, recommendations):
        """Notify school owner about at-risk student"""
        from django.core.mail import send_mail
        
        subject = f"⚠️ At-Risk Student Alert: {student.user.get_full_name()}"
        
        risk_summary = "\n".join([
            f"- {risk['message']}" 
            for risk in risk_factors.values()
        ])
        
        recommendations_text = "\n".join([
            f"• {rec}" 
            for rec in recommendations
        ])
        
        message = f"""
        Hello {student.school.owner.get_full_name()},
        
        Student {student.user.get_full_name()} may need additional support.
        
        Risk Factors:
        {risk_summary}
        
        Recommended Actions:
        {recommendations_text}
        
        Please review this student's progress and consider intervention.
        
        Best regards,
        Driving School Management System
        """
        
        send_mail(
            subject=subject,
            message=message,
            from_email='noreply@drivingschool.com',
            recipient_list=[student.school.owner.email],
            fail_silently=False
        )

    @staticmethod
    def send_maintenance_alert(vehicle, urgency, message):
        """Send vehicle maintenance alert to school owner"""
        from django.core.mail import send_mail
        
        urgency_emoji = '🚨' if urgency == 'high' else '⚠️'
        
        subject = f"{urgency_emoji} Vehicle Maintenance Alert - {vehicle.plate_number}"
        
        email_message = f"""
        Hello {vehicle.school.owner.get_full_name()},
        
        {message}
        
        Vehicle Details:
        - Make/Model: {vehicle.make} {vehicle.model}
        - Plate Number: {vehicle.plate_number}
        - Last Maintenance: {vehicle.last_maintenance or 'Never'}
        - Next Maintenance: {vehicle.next_maintenance}
        
        Please schedule maintenance as soon as possible.
        
        Best regards,
        Driving School Management System
        """
        
        send_mail(
            subject=subject,
            message=email_message,
            from_email='noreply@drivingschool.com',
            recipient_list=[vehicle.school.owner.email],
            fail_silently=False
        )

    
    @staticmethod
    def send_subscription_warning(owner, subscription, days_remaining):
        """Send subscription expiry warning to school owner"""
        from django.core.mail import send_mail
        
        subject = f"⏰ Subscription Expiring in {days_remaining} Days"
        
        message = f"""
        Hello {owner.get_full_name()},
        
        Your subscription for {subscription.school.name} will expire in {days_remaining} days.
        
        Subscription Details:
        - Plan: {subscription.plan.name}
        - Expiry Date: {subscription.current_period_end.strftime('%B %d, %Y')}
        - Current Status: {subscription.get_status_display()}
        
        Please renew your subscription to avoid service interruption.
        
        Renew now: [Your renewal link here]
        
        Best regards,
        Driving School Management System
        """
        
        send_mail(
            subject=subject,
            message=message,
            from_email='noreply@drivingschool.com',
            recipient_list=[owner.email],
            fail_silently=False
        )

# Add this to your services.py
class CommunicationTemplateService:
    """Handle template business logic"""
    
    @staticmethod
    def get_available_variables():
        """Get all available template variables"""
        return {
            'student_name': 'Full name of the student',
            'progress_theory': 'Theory progress percentage',
            'progress_driving': 'Driving progress percentage', 
            'school_name': 'Name of the driving school',
            'license_type': 'Type of license (Car/Moto)',
            'instructor_name': 'Name of the instructor',
            'lesson_date': 'Date of the next lesson',
            'completion_date': 'Expected completion date',
            'total_hours_theory': 'Total theory hours completed',
            'total_hours_driving': 'Total driving hours completed',
        }
    
    @staticmethod
    def validate_template_creation(school, name, template_type) -> None:
        """Validate template creation"""
        # Check for duplicate names per school
        if CommunicationTemplate.objects.filter(school=school, name=name).exists():
            raise serializers.ValidationError({
                'name': 'A template with this name already exists for your school'
            })
    
    @staticmethod
    def get_school_templates(school, template_type=None):
        """Get templates for a school, optionally filtered by type"""
        queryset = CommunicationTemplate.objects.filter(school=school, is_active=True)
        if template_type:
            queryset = queryset.filter(template_type=template_type)
        return queryset.order_by('name')
# services.py - Add this class
class FeedbackService:
    """Handle feedback analysis, insights, and automated actions"""
    
    @staticmethod
    def analyze_feedback_trends(school, days=30):
        """Analyze feedback trends for a school"""
        from .models import Feedback
        
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)
        
        feedback_data = Feedback.objects.filter(
            lesson__school=school,
            created_at__gte=start_date,
            created_at__lte=end_date
        )
        
        # Basic statistics
        stats = feedback_data.aggregate(
            avg_rating=Avg('rating'),
            total_feedback=Count('id'),
            five_star=Count('id', filter=Q(rating=5)),
            one_star=Count('id', filter=Q(rating=1))
        )
        
        # Rating distribution
        rating_distribution = {}
        for rating in range(1, 6):
            count = feedback_data.filter(rating=rating).count()
            rating_distribution[rating] = {
                'count': count,
                'percentage': (count / stats['total_feedback'] * 100) if stats['total_feedback'] > 0 else 0
            }
        
        # Instructor performance
        instructor_stats = feedback_data.values(
            'lesson__instructor__username',
            'lesson__instructor_id'
        ).annotate(
            avg_rating=Avg('rating'),
            feedback_count=Count('id'),
            last_feedback=Max('created_at')
        ).order_by('-avg_rating')
        
        # Lesson type analysis
        lesson_type_stats = feedback_data.values(
            'lesson__lesson_type'
        ).annotate(
            avg_rating=Avg('rating'),
            count=Count('id')
        )
        
        # Sentiment analysis on comments
        positive_keywords = ['great', 'excellent', 'awesome', 'good', 'helpful', 'patient', 'professional']
        negative_keywords = ['poor', 'bad', 'terrible', 'disappointing', 'rude', 'unprofessional']
        
        feedback_with_comments = feedback_data.exclude(comment='').exclude(comment__isnull=True)
        
        sentiment_analysis = {
            'positive_comments': feedback_with_comments.filter(
                Q(comment__icontains='great') | 
                Q(comment__icontains='excellent') |
                Q(comment__icontains='awesome') |
                Q(comment__icontains='good') |
                Q(comment__icontains='helpful') |
                Q(comment__icontains='patient') |
                Q(comment__icontains='professional')
            ).count(),
            'negative_comments': feedback_with_comments.filter(
                Q(comment__icontains='poor') | 
                Q(comment__icontains='bad') |
                Q(comment__icontains='terrible') |
                Q(comment__icontains='disappointing') |
                Q(comment__icontains='rude') |
                Q(comment__icontains='unprofessional')
            ).count(),
            'total_with_comments': feedback_with_comments.count()
        }
        
        return {
            'period': f'Last {days} days',
            'summary': {
                'average_rating': round(stats['avg_rating'] or 0, 2),
                'total_feedback': stats['total_feedback'],
                'five_star_percentage': (stats['five_star'] / stats['total_feedback'] * 100) if stats['total_feedback'] > 0 else 0,
                'one_star_percentage': (stats['one_star'] / stats['total_feedback'] * 100) if stats['total_feedback'] > 0 else 0,
                'response_rate': FeedbackService._calculate_response_rate(school, start_date, end_date)
            },
            'rating_distribution': rating_distribution,
            'instructor_performance': list(instructor_stats),
            'lesson_type_analysis': list(lesson_type_stats),
            'sentiment_analysis': sentiment_analysis,
            'trend_comparison': FeedbackService._compare_with_previous_period(school, days)
        }
    
    @staticmethod
    def _calculate_response_rate(school, start_date, end_date):
        """Calculate what percentage of completed lessons received feedback"""
        from .models import Lesson, Feedback
        
        completed_lessons = Lesson.objects.filter(
            school=school,
            status='C',
            date__gte=start_date,
            date__lte=end_date
        ).count()
        
        if completed_lessons == 0:
            return 0
        
        feedback_count = Feedback.objects.filter(
            lesson__school=school,
            lesson__status='C',
            created_at__gte=start_date,
            created_at__lte=end_date
        ).count()
        
        return (feedback_count / completed_lessons) * 100
    
    @staticmethod
    def _compare_with_previous_period(school, days):
        """Compare current period with previous period"""
        from .models import Feedback
        
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)
        previous_start = start_date - timedelta(days=days)
        
        current_stats = Feedback.objects.filter(
            lesson__school=school,
            created_at__gte=start_date,
            created_at__lte=end_date
        ).aggregate(
            avg_rating=Avg('rating'),
            count=Count('id')
        )
        
        previous_stats = Feedback.objects.filter(
            lesson__school=school,
            created_at__gte=previous_start,
            created_at__lt=start_date
        ).aggregate(
            avg_rating=Avg('rating'),
            count=Count('id')
        )
        
        current_avg = current_stats['avg_rating'] or 0
        previous_avg = previous_stats['avg_rating'] or 0
        
        return {
            'rating_trend': 'up' if current_avg > previous_avg else 'down' if current_avg < previous_avg else 'stable',
            'rating_change': round(current_avg - previous_avg, 2),
            'volume_trend': 'up' if current_stats['count'] > previous_stats['count'] else 'down' if current_stats['count'] < previous_stats['count'] else 'stable',
            'volume_change': current_stats['count'] - previous_stats['count']
        }
    
    @staticmethod
    def get_instructor_performance(instructor, days=90):
        """Get detailed performance analysis for an instructor"""
        from .models import Feedback
        
        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)
        
        feedbacks = Feedback.objects.filter(
            lesson__instructor=instructor,
            created_at__gte=start_date,
            created_at__lte=end_date
        )
        
        stats = feedbacks.aggregate(
            avg_rating=Avg('rating'),
            total_feedback=Count('id'),
            with_comments=Count('id', filter=~Q(comment=''))
        )
        
        # Recent feedback (last 7 days)
        recent_feedback = feedbacks.filter(
            created_at__gte=end_date - timedelta(days=7)
        ).order_by('-created_at')
        
        # Common themes in comments
        comments = feedbacks.exclude(comment='').values_list('comment', flat=True)
        common_themes = FeedbackService._analyze_comment_themes(comments)
        
        # Rating over time (monthly)
        monthly_trend = feedbacks.extra(
            {'month': "DATE_TRUNC('month', created_at)"}
        ).values('month').annotate(
            avg_rating=Avg('rating'),
            count=Count('id')
        ).order_by('month')
        
        return {
            'instructor': instructor.username,
            'period': f'Last {days} days',
            'performance_summary': {
                'average_rating': round(stats['avg_rating'] or 0, 2),
                'total_feedback': stats['total_feedback'],
                'feedback_with_comments': stats['with_comments'],
                'comment_rate': (stats['with_comments'] / stats['total_feedback'] * 100) if stats['total_feedback'] > 0 else 0
            },
            'rating_distribution': FeedbackService._get_rating_distribution(feedbacks),
            'common_themes': common_themes,
            'recent_feedback': [
                {
                    'rating': fb.rating,
                    'comment': fb.comment,
                    'date': fb.created_at,
                    'lesson': fb.lesson.title
                }
                for fb in recent_feedback[:5]  # Last 5 feedbacks
            ],
            'monthly_trend': list(monthly_trend),
            'improvement_recommendations': FeedbackService._generate_instructor_recommendations(feedbacks)
        }
    
    @staticmethod
    def _analyze_comment_themes(comments):
        """Analyze common themes in feedback comments"""
        themes = {
            'teaching_style': {'keywords': ['explain', 'teach', 'instruct', 'demonstrate'], 'count': 0},
            'patience': {'keywords': ['patient', 'calm', 'understanding', 'supportive'], 'count': 0},
            'communication': {'keywords': ['communicat', 'clear', 'explanation', 'describe'], 'count': 0},
            'professionalism': {'keywords': ['professional', 'punctual', 'organized', 'prepared'], 'count': 0},
            'vehicle': {'keywords': ['car', 'vehicle', 'clean', 'maintained'], 'count': 0}
        }
        
        for comment in comments:
            if not comment:
                continue
                
            comment_lower = comment.lower()
            for theme, data in themes.items():
                for keyword in data['keywords']:
                    if keyword in comment_lower:
                        data['count'] += 1
                        break
        
        # Filter out themes with no mentions and sort by count
        active_themes = {k: v for k, v in themes.items() if v['count'] > 0}
        return dict(sorted(active_themes.items(), key=lambda x: x[1]['count'], reverse=True))
    
    @staticmethod
    def _get_rating_distribution(feedbacks):
        """Get rating distribution for feedback queryset"""
        distribution = {}
        for rating in range(1, 6):
            count = feedbacks.filter(rating=rating).count()
            distribution[rating] = {
                'count': count,
                'percentage': (count / feedbacks.count() * 100) if feedbacks.count() > 0 else 0
            }
        return distribution
    
    @staticmethod
    def _generate_instructor_recommendations(feedbacks):
        """Generate personalized recommendations for instructors"""
        recommendations = []
        
        if feedbacks.count() == 0:
            return ["No feedback available for analysis"]
        
        avg_rating = feedbacks.aggregate(avg=Avg('rating'))['avg'] or 0
        
        if avg_rating < 3.0:
            recommendations.append("Focus on improving overall student satisfaction")
        
        # Analyze low ratings for specific issues
        low_ratings = feedbacks.filter(rating__lte=2)
        low_rating_comments = low_ratings.exclude(comment='')
        
        if low_rating_comments.filter(comment__icontains='rude').exists():
            recommendations.append("Work on communication style and patience")
        
        if low_rating_comments.filter(comment__icontains='unprepared').exists():
            recommendations.append("Improve lesson preparation and organization")
        
        if low_rating_comments.filter(comment__icontains='late').exists():
            recommendations.append("Focus on punctuality and time management")
        
        # Positive reinforcement
        high_ratings = feedbacks.filter(rating__gte=4)
        high_rating_comments = high_ratings.exclude(comment='')
        
        if high_rating_comments.filter(comment__icontains='patient').exists():
            recommendations.append("Continue demonstrating patience with students")
        
        if high_rating_comments.filter(comment__icontains='explain').exists():
            recommendations.append("Keep up the clear explanations")
        
        return recommendations if recommendations else ["Continue current teaching approach"]
    
    @staticmethod
    def trigger_feedback_reminders(days_after_lesson=2):
        """Trigger feedback reminders for recent lessons"""
        from .models import Lesson, Attendance, CommunicationTemplate, AutomatedMessage
        
        cutoff_date = timezone.now() - timedelta(days=days_after_lesson)
        
        # Find completed lessons without feedback
        lessons_without_feedback = Lesson.objects.filter(
            status='C',
            date__lte=cutoff_date
        ).exclude(
            lesson_feedback__isnull=False  # Lessons that have no feedback
        )
        
        for lesson in lessons_without_feedback:
            # Get students who attended but didn't provide feedback
            attended_students = Attendance.objects.filter(
                lesson=lesson,
                presence=True
            ).exclude(
                student__student_feedback__lesson=lesson  # Students who haven't given feedback for this lesson
            )
            
            for attendance in attended_students:
                # Find appropriate template
                template = CommunicationTemplate.objects.filter(
                    school=lesson.school,
                    template_type='feedback_reminder',
                    is_active=True
                ).first()
                
                if template:
                    AutomatedMessage.objects.get_or_create(
                        student=attendance.student,
                        template=template,
                        scheduled_for=timezone.now() + timedelta(hours=1),  # Send in 1 hour
                        defaults={'status': 'pending'}
                    )
    
    @staticmethod
    def get_student_avg_rating(student):
        """Get student's average rating across all feedback (used by other services)"""
        from .models import Feedback
        
        avg_rating = Feedback.objects.filter(
            student=student
        ).aggregate(Avg('rating'))['rating__avg']
        
        return avg_rating or 0
    
    @staticmethod
    def generate_feedback_report(school, start_date, end_date):
        """Generate comprehensive feedback report for school administration"""
        trends = FeedbackService.analyze_feedback_trends(school, days=(end_date - start_date).days)
        
        # Top performing instructors
        top_instructors = Feedback.objects.filter(
            lesson__school=school,
            created_at__gte=start_date,
            created_at__lte=end_date
        ).values(
            'lesson__instructor__username',
            'lesson__instructor_id'
        ).annotate(
            avg_rating=Avg('rating'),
            feedback_count=Count('id')
        ).filter(
            feedback_count__gte=3  # Only instructors with sufficient feedback
        ).order_by('-avg_rating')[:5]
        
        # Areas for improvement
        low_rated_feedback = Feedback.objects.filter(
            lesson__school=school,
            rating__lte=2,
            created_at__gte=start_date,
            created_at__lte=end_date
        )
        
        common_issues = FeedbackService._analyze_low_rating_issues(low_rated_feedback)
        
        return {
            'report_period': {
                'start': start_date,
                'end': end_date
            },
            'executive_summary': {
                'overall_rating': trends['summary']['average_rating'],
                'feedback_volume': trends['summary']['total_feedback'],
                'response_rate': trends['summary']['response_rate'],
                'key_trends': trends['trend_comparison']
            },
            'top_performers': list(top_instructors),
            'areas_for_improvement': common_issues,
            'detailed_analysis': trends,
            'recommendations': FeedbackService._generate_school_recommendations(trends)
        }
    
    @staticmethod
    def _analyze_low_rating_issues(low_rated_feedback):
        """Analyze common issues in low-rated feedback"""
        issues = {}
        
        for feedback in low_rated_feedback:
            comment = (feedback.comment or '').lower()
            
            if 'rude' in comment or 'unprofessional' in comment:
                issues['professionalism'] = issues.get('professionalism', 0) + 1
            elif 'late' in comment or 'punctual' in comment:
                issues['punctuality'] = issues.get('punctuality', 0) + 1
            elif 'explain' in comment or 'confusing' in comment:
                issues['communication'] = issues.get('communication', 0) + 1
            elif 'car' in comment or 'vehicle' in comment:
                issues['vehicle_condition'] = issues.get('vehicle_condition', 0) + 1
            elif 'nervous' in comment or 'scared' in comment:
                issues['student_comfort'] = issues.get('student_comfort', 0) + 1
            else:
                issues['other'] = issues.get('other', 0) + 1
        
        return issues
    
    @staticmethod
    def _generate_school_recommendations(trends):
        """Generate school-level recommendations based on feedback analysis"""
        recommendations = []
        summary = trends['summary']
        
        if summary['average_rating'] < 3.5:
            recommendations.append("Implement instructor training program focused on student satisfaction")
        
        if summary['response_rate'] < 30:
            recommendations.append("Increase feedback collection through reminders and incentives")
        
        if trends['sentiment_analysis']['negative_comments'] > trends['sentiment_analysis']['positive_comments']:
            recommendations.append("Address common concerns mentioned in negative feedback")
        
        if summary['one_star_percentage'] > 10:
            recommendations.append("Conduct one-on-one reviews with instructors receiving low ratings")
        
        return recommendations if recommendations else ["Maintain current quality standards and monitoring"]
    

class ScheduleService:
    """Handle all Schedule business logic and operations"""
    
    # Configuration
    MAX_LESSON_DURATION_HOURS = 4
    BUFFER_MINUTES = 15  # Buffer between lessons
    MIN_LESSON_DURATION_MINUTES = 30
    
    @staticmethod
    def validate_schedule_creation(lesson, vehicle, instructor, start_time, end_time, request_user=None) -> None:
        """Validate schedule creation business rules"""
        # Validate time range
        ScheduleService._validate_time_range(start_time, end_time)
        
        # Validate lesson assignment
        ScheduleService._validate_lesson_assignment(lesson, instructor)
        
        # Validate vehicle availability and status
        if vehicle:
            ScheduleService._validate_vehicle_availability(vehicle, start_time, end_time)
        
        # Check for scheduling conflicts
        ScheduleService._check_scheduling_conflicts(instructor, vehicle, start_time, end_time)
        
        # Validate user permissions
        ScheduleService._validate_user_permissions(request_user, lesson.school)

    @staticmethod
    def validate_schedule_update(instance, validated_data, request_user=None) -> None:
        """Validate schedule update business rules"""
        lesson = validated_data.get('lesson', instance.lesson)
        vehicle = validated_data.get('vehicle', instance.vehicle)
        instructor = validated_data.get('instructor', instance.instructor)
        start_time = validated_data.get('start_time', instance.start_time)
        end_time = validated_data.get('end_time', instance.end_time)
        
        # Prevent lesson change
        if 'lesson' in validated_data and validated_data['lesson'] != instance.lesson:
            raise serializers.ValidationError("Cannot change the lesson of an existing schedule")
        
        # Validate time range if changed
        if any(field in validated_data for field in ['start_time', 'end_time']):
            ScheduleService._validate_time_range(start_time, end_time)
        
        # Validate lesson assignment
        ScheduleService._validate_lesson_assignment(lesson, instructor)
        
        # Validate vehicle if changed
        if 'vehicle' in validated_data or any(field in validated_data for field in ['start_time', 'end_time']):
            if vehicle:
                ScheduleService._validate_vehicle_availability(vehicle, start_time, end_time, instance)
        
        # Check for scheduling conflicts if time-related fields changed
        if any(field in validated_data for field in ['instructor', 'vehicle', 'start_time', 'end_time']):
            ScheduleService._check_scheduling_conflicts(instructor, vehicle, start_time, end_time, instance)
        
        # Validate user permissions
        ScheduleService._validate_user_permissions(request_user, lesson.school)

    @staticmethod
    def _validate_time_range(start_time, end_time) -> None:
        """Validate start and end time business rules"""
        if end_time <= start_time:
            raise serializers.ValidationError({
                'end_time': 'End time must be after start time'
            })
        
        # Check minimum duration
        duration_minutes = (end_time - start_time).total_seconds() / 60
        if duration_minutes < ScheduleService.MIN_LESSON_DURATION_MINUTES:
            raise serializers.ValidationError({
                'end_time': f'Lesson duration must be at least {ScheduleService.MIN_LESSON_DURATION_MINUTES} minutes'
            })
        
        # Check maximum duration
        duration_hours = duration_minutes / 60
        if duration_hours > ScheduleService.MAX_LESSON_DURATION_HOURS:
            raise serializers.ValidationError({
                'end_time': f'Lesson duration cannot exceed {ScheduleService.MAX_LESSON_DURATION_HOURS} hours'
            })
        
        # Don't allow scheduling in the past
        if start_time < timezone.now():
            raise serializers.ValidationError({
                'start_time': 'Cannot schedule lessons in the past'
            })

    @staticmethod
    def _validate_lesson_assignment(lesson, instructor) -> None:
        """Validate instructor is properly assigned to the lesson"""
        if instructor.role != 'I':
            raise serializers.ValidationError({
                'instructor': 'Selected user must have instructor role'
            })
        
        # Check if instructor is assigned to this lesson
        if lesson.instructor and lesson.instructor != instructor:
            raise serializers.ValidationError({
                'instructor': 'Instructor must be assigned to this lesson'
            })

    @staticmethod
    def _validate_vehicle_availability(vehicle, start_time, end_time, instance=None) -> None:
        """Validate vehicle availability and status"""
        # Check vehicle status
        if vehicle.status != 'available':
            raise serializers.ValidationError({
                'vehicle': f'Vehicle is {vehicle.get_status_display().lower()} and cannot be scheduled'
            })
        
        # Check if vehicle belongs to the same school as the lesson
        if instance and vehicle.school != instance.lesson.school:
            raise serializers.ValidationError({
                'vehicle': 'Vehicle must belong to the same school as the lesson'
            })

    @staticmethod
    def _check_scheduling_conflicts(instructor, vehicle, start_time, end_time, instance=None) -> None:
        """Check for instructor and vehicle scheduling conflicts"""
        buffer_time = timedelta(minutes=ScheduleService.BUFFER_MINUTES)
        
        # Check instructor availability
        instructor_query = Schedule.objects.filter(
            instructor=instructor,
            start_time__lt=end_time + buffer_time,
            end_time__gt=start_time - buffer_time
        )
        
        if instance:
            instructor_query = instructor_query.exclude(pk=instance.pk)
            
        if instructor_query.exists():
            conflicting = instructor_query.first()
            raise serializers.ValidationError({
                'instructor': f'Instructor is already scheduled from {conflicting.start_time} to {conflicting.end_time}'
            })

        # Check vehicle availability (if vehicle is assigned)
        if vehicle:
            vehicle_query = Schedule.objects.filter(
                vehicle=vehicle,
                start_time__lt=end_time + buffer_time,
                end_time__gt=start_time - buffer_time
            )
            
            if instance:
                vehicle_query = vehicle_query.exclude(pk=instance.pk)
                
            if vehicle_query.exists():
                conflicting = vehicle_query.first()
                raise serializers.ValidationError({
                    'vehicle': f'Vehicle is already scheduled from {conflicting.start_time} to {conflicting.end_time}'
                })

    @staticmethod
    def _validate_user_permissions(request_user, school) -> None:
        """Validate user has permission to manage schedules"""
        if not request_user or not request_user.is_authenticated:
            raise serializers.ValidationError('Authentication required to manage schedules')
        
        # Admin must own the school
        if request_user.role == 'A' and school.owner != request_user:
            raise serializers.ValidationError('You can only manage schedules in your own schools')
        
        # Instructors must be assigned to the school
        if request_user.role == 'I':
            if not StudentProfile.objects.filter(
                user=request_user, 
                school=school, 
                status='A'
            ).exists():
                raise serializers.ValidationError('You are not assigned to this school')

    @staticmethod
    @transaction.atomic
    def create_schedule(validated_data, request_user=None) -> Schedule:
        """Create schedule with business logic"""
        if not request_user or not request_user.is_authenticated:
            raise serializers.ValidationError('Authentication required to create a schedule')
        
        # Extract fields for validation
        lesson = validated_data.get('lesson')
        vehicle = validated_data.get('vehicle')
        instructor = validated_data.get('instructor')
        start_time = validated_data.get('start_time')
        end_time = validated_data.get('end_time')
        
        # Validate creation
        ScheduleService.validate_schedule_creation(
            lesson, vehicle, instructor, start_time, end_time, request_user
        )
        
        # Check if lesson already has a schedule
        if hasattr(lesson, 'schedule'):
            raise serializers.ValidationError("This lesson already has a schedule")
        
        # Create the schedule
        return Schedule.objects.create(**validated_data)

    @staticmethod
    @transaction.atomic
    def update_schedule(instance, validated_data) -> Schedule:
        """Update schedule with business logic"""
        # Prevent changing lesson
        validated_data.pop('lesson', None)
        
        # Update instance
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        instance.save()
        return instance

    @staticmethod
    def get_schedule_duration(schedule) -> int:
        """Calculate schedule duration in minutes"""
        if schedule.end_time and schedule.start_time:
            delta = schedule.end_time - schedule.start_time
            return int(delta.total_seconds() / 60)
        return 0

    @staticmethod
    def get_instructor_schedule(instructor, start_date, end_date) -> list:
        """Get instructor's schedule for a date range"""
        return Schedule.objects.filter(
            instructor=instructor,
            start_time__date__range=[start_date, end_date]
        ).order_by('start_time')

    @staticmethod
    def get_vehicle_schedule(vehicle, start_date, end_date) -> list:
        """Get vehicle's schedule for a date range"""
        return Schedule.objects.filter(
            vehicle=vehicle,
            start_time__date__range=[start_date, end_date]
        ).order_by('start_time')

    @staticmethod
    def get_school_schedule(school, start_date, end_date) -> list:
        """Get school's schedule for a date range"""
        return Schedule.objects.filter(
            lesson__school=school,
            start_time__date__range=[start_date, end_date]
        ).order_by('start_time')

    @staticmethod
    def check_availability(instructor, vehicle, start_time, end_time, instance=None) -> dict:
        """Check availability of instructor and vehicle for a time slot"""
        buffer_time = timedelta(minutes=ScheduleService.BUFFER_MINUTES)
        
        instructor_available = not Schedule.objects.filter(
            instructor=instructor,
            start_time__lt=end_time + buffer_time,
            end_time__gt=start_time - buffer_time
        ).exclude(pk=instance.pk if instance else None).exists()
        
        vehicle_available = True
        if vehicle:
            vehicle_available = not Schedule.objects.filter(
                vehicle=vehicle,
                start_time__lt=end_time + buffer_time,
                end_time__gt=start_time - buffer_time
            ).exclude(pk=instance.pk if instance else None).exists()
        
        return {
            'instructor_available': instructor_available,
            'vehicle_available': vehicle_available,
            'time_slot_available': instructor_available and vehicle_available
        }

    @staticmethod
    def can_modify_schedule(user, schedule) -> bool:
        """Check if user has permission to modify this schedule"""
        if user.role == 'A':
            return schedule.lesson.school.owner == user
        
        if user.role == 'I':
            return schedule.instructor == user
        
        return False


class VehicleService:
    """Handle all Vehicle business logic and operations"""
    
    # Configuration
    MIN_VEHICLE_YEAR = 1990
    MAX_FUTURE_YEAR = 1  # Can register vehicles up to 1 year in future
    MAINTENANCE_INTERVAL_DAYS = 180  # 6 months
    INITIAL_MAINTENANCE_DAYS = 90    # 3 months for new vehicles
    
    # Image validation constants
    MAX_IMAGE_SIZE_MB = 10  # Cloudinary can handle larger files
    MAX_IMAGE_SIZE_BYTES = MAX_IMAGE_SIZE_MB * 1024 * 1024
    MIN_IMAGE_WIDTH = 800
    MIN_IMAGE_HEIGHT = 600
    MAX_IMAGE_WIDTH = 5000
    MAX_IMAGE_HEIGHT = 5000
    ALLOWED_IMAGE_FORMATS = ['JPEG', 'PNG', 'JPG', 'WEBP']
    ALLOWED_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.webp']
    MAX_IMAGES_PER_VEHICLE = 15  # Increased since Cloudinary handles it well
    
    @staticmethod
    def validate_image_file(image_file):
        """
        Validate image before uploading to Cloudinary
        Cloudinary will do additional optimization, but we validate first
        """
        if not image_file:
            return False, "Image file is required"
        
        # 1. Check file size
        if image_file.size > VehicleService.MAX_IMAGE_SIZE_BYTES:
            size_mb = image_file.size / (1024 * 1024)
            return False, f"Image size ({size_mb:.2f}MB) exceeds maximum ({VehicleService.MAX_IMAGE_SIZE_MB}MB)"
        
        # 2. Check file extension
        ext = os.path.splitext(image_file.name)[1].lower()
        if ext not in VehicleService.ALLOWED_EXTENSIONS:
            return False, f"File extension '{ext}' not allowed. Allowed: {', '.join(VehicleService.ALLOWED_EXTENSIONS)}"
        
        # 3. Validate actual image using PIL
        try:
            image_file.seek(0)
            img = Image.open(image_file)
            img.verify()
            
            # Re-open for dimension checks
            image_file.seek(0)
            img = Image.open(image_file)
            
            width, height = img.size
            
            # Check dimensions
            if width < VehicleService.MIN_IMAGE_WIDTH or height < VehicleService.MIN_IMAGE_HEIGHT:
                return False, f"Image too small ({width}x{height}). Minimum: {VehicleService.MIN_IMAGE_WIDTH}x{VehicleService.MIN_IMAGE_HEIGHT}"
            
            if width > VehicleService.MAX_IMAGE_WIDTH or height > VehicleService.MAX_IMAGE_HEIGHT:
                return False, f"Image too large ({width}x{height}). Maximum: {VehicleService.MAX_IMAGE_WIDTH}x{VehicleService.MAX_IMAGE_HEIGHT}"
            
            # Check format
            if img.format not in VehicleService.ALLOWED_IMAGE_FORMATS:
                return False, f"Format '{img.format}' not allowed. Allowed: {', '.join(VehicleService.ALLOWED_IMAGE_FORMATS)}"
            
            # Reset file pointer
            image_file.seek(0)
            return True, None
            
        except Exception as e:
            return False, f"Invalid image: {str(e)}"
    
    @staticmethod
    def validate_multiple_images(images_list, vehicle=None):
        """Validate multiple images"""
        if not images_list:
            return True, None
        
        current_count = 0
        if vehicle:
            current_count = vehicle.pictures.count()
        
        new_count = len(images_list)
        total_count = current_count + new_count
        
        if total_count > VehicleService.MAX_IMAGES_PER_VEHICLE:
            return False, f"Cannot upload {new_count} images. Vehicle has {current_count} images. Max: {VehicleService.MAX_IMAGES_PER_VEHICLE}"
        
        # Validate each image
        for idx, image in enumerate(images_list, 1):
            is_valid, error = VehicleService.validate_image_file(image)
            if not is_valid:
                return False, f"Image {idx}: {error}"
        
        return True, None
    
    @staticmethod
    def upload_to_cloudinary(image_file, folder='vehicles', vehicle_id=None):
        """
        Upload image to Cloudinary with optimizations
        Returns: (success, result_or_error)
        """
        try:
            # Validate first
            is_valid, error = VehicleService.validate_image_file(image_file)
            if not is_valid:
                return False, error
            
            # Prepare upload options
            upload_options = {
                'folder': folder,
                'resource_type': 'image',
                'quality': 'auto:good',
                'fetch_format': 'auto',
                'eager': [
                    {
                        'width': 300, 'height': 200,
                        'crop': 'fill', 'quality': 'auto:good'
                    },  # Thumbnail
                    {
                        'width': 1200, 'crop': 'limit',
                        'quality': 'auto:best'
                    }  # Optimized full size
                ],
                'eager_async': True,  # Generate transformations in background
            }
            
            # Add tags for organization
            if vehicle_id:
                upload_options['tags'] = [f'vehicle_{vehicle_id}']
            
            # Upload to Cloudinary
            result = cloudinary.uploader.upload(image_file, **upload_options)
            
            return True, result
            
        except Exception as e:
            return False, f"Upload failed: {str(e)}"
    
    @staticmethod
    def delete_from_cloudinary(public_id):
        """Delete image from Cloudinary"""
        try:
            result = cloudinary.uploader.destroy(public_id)
            return result.get('result') == 'ok'
        except Exception as e:
            return False
    
    @staticmethod
    def delete_picture(vehicle, picture_id, user):
        """Delete vehicle picture (including from Cloudinary)"""
        from .models import VehiclePicture
        
        try:
            picture = VehiclePicture.objects.get(id=picture_id, vehicle=vehicle)
            
            # Check permissions
            if not VehicleService.can_modify_vehicle(user, vehicle):
                return False, "No permission to delete this picture"
            
            # Delete from Cloudinary
            if picture.cloudinary_public_id:
                VehicleService.delete_from_cloudinary(picture.cloudinary_public_id)
            
            was_primary = picture.is_primary
            picture.delete()
            
            # Set another as primary if needed
            if was_primary:
                new_primary = VehiclePicture.objects.filter(vehicle=vehicle).first()
                if new_primary:
                    new_primary.is_primary = True
                    new_primary.save()
            
            return True, "Picture deleted successfully"
            
        except VehiclePicture.DoesNotExist:
            return False, "Picture not found"
        except Exception as e:
            return False, f"Error: {str(e)}"
    
    @staticmethod
    def get_vehicle_images_summary(vehicle):
        """Get vehicle images summary"""
        pictures = vehicle.pictures.all()
        primary = pictures.filter(is_primary=True).first()
        
        return {
            'total_images': pictures.count(),
            'has_primary': bool(primary),
            'primary_image_url': primary.image.url if primary and primary.image else None,
            'primary_thumbnail_url': primary.get_thumbnail_url() if primary else None,
            'can_add_more': pictures.count() < VehicleService.MAX_IMAGES_PER_VEHICLE,
            'remaining_slots': VehicleService.MAX_IMAGES_PER_VEHICLE - pictures.count()
        }
    
    @staticmethod
    @transaction.atomic
    def set_primary_picture(vehicle, picture_id):
        picture = vehicle.pictures.filter(id=picture_id).first()
        if not picture:
            return False,"The picture not found for this vehicle"

        vehicle.pictures.filter(is_primary=True).update(is_primary=False)

        picture.is_primary = True
        picture.save(update_fields=["is_primary"])

        return True,"Primary picture updated successfully"

    @staticmethod
    def validate_vehicle_creation(school, plate_number, year, last_maintenance, next_maintenance, request_user=None) -> None:
        """Validate vehicle creation business rules"""
        # Validate plate number
        VehicleService._validate_plate_number(plate_number)
        
        # Validate year
        VehicleService._validate_year(year)
        
        # Validate maintenance dates
        VehicleService._validate_maintenance_dates(last_maintenance, next_maintenance, is_creation=True)
        
        if request_user:
            # Platform admins (role='A' AND is_staff=True) can add to any school
            if request_user.role == 'A' and request_user.is_staff:
                pass  # Platform admin can add to any school
            elif request_user.role == 'A' and not request_user.is_staff:
                # School owner can only add to their own schools
                if school.owner != request_user:
                    raise serializers.ValidationError({
                        'school': 'You can only add vehicles to your own school'
                    })
            else:
                # Instructors and students cannot create vehicles
                raise serializers.ValidationError({
                    'school': 'You do not have permission to add vehicles'
                })
        
        # Check plate number uniqueness
        if Vehicle.objects.filter(plate_number=plate_number.upper()).exists():
            raise serializers.ValidationError({
                'plate_number': 'This plate number is already registered'
            })

    @staticmethod
    def validate_vehicle_update(instance, validated_data, request_user=None) -> None:
        """Validate vehicle update business rules"""
        plate_number = validated_data.get('plate_number', instance.plate_number)
        year = validated_data.get('year', instance.year)
        last_maintenance = validated_data.get('last_maintenance', instance.last_maintenance)
        next_maintenance = validated_data.get('next_maintenance', instance.next_maintenance)
        
        # Prevent school change
        if 'school' in validated_data and validated_data['school'] != instance.school:
            raise serializers.ValidationError("Cannot change the school of an existing vehicle")
        
        # Validate plate number if changed
        if 'plate_number' in validated_data:
            VehicleService._validate_plate_number(plate_number)
            
            # Check uniqueness excluding current instance
            if Vehicle.objects.filter(plate_number=plate_number.upper()).exclude(pk=instance.pk).exists():
                raise serializers.ValidationError({
                    'plate_number': 'This plate number is already registered'
                })
        
        # Validate year if changed
        if 'year' in validated_data:
            VehicleService._validate_year(year)
        
        # Validate maintenance dates
        VehicleService._validate_maintenance_dates(last_maintenance, next_maintenance, is_creation=False)


    @staticmethod
    def _validate_plate_number(plate_number) -> None:
        """Validate plate number format"""
        if not plate_number or len(plate_number) < 3:
            raise serializers.ValidationError({
                'plate_number': 'Plate number must be at least 3 characters'
            })
        
        # Optional: Add more specific plate number format validation
        # Example: Check for alphanumeric and specific patterns

    @staticmethod
    def _validate_year(year) -> None:
        """Validate vehicle year is reasonable"""
        current_year = timezone.now().year
        max_year = current_year + VehicleService.MAX_FUTURE_YEAR
        
        if year < VehicleService.MIN_VEHICLE_YEAR or year > max_year:
            raise serializers.ValidationError({
                'year': f'Vehicle year must be between {VehicleService.MIN_VEHICLE_YEAR} and {max_year}'
            })

    @staticmethod
    def _validate_maintenance_dates(last_maintenance, next_maintenance, is_creation=False) -> None:
        """Validate maintenance date logic"""
        current_date = timezone.now().date()
        
        # Validate last_maintenance is not in the future
        if last_maintenance and last_maintenance > current_date:
            raise serializers.ValidationError({
                'last_maintenance': 'Last maintenance date cannot be in the future'
            })
        
        # Validate next_maintenance is not in the past for new vehicles
        if is_creation and next_maintenance and next_maintenance < current_date:
            raise serializers.ValidationError({
                'next_maintenance': 'Next maintenance date cannot be in the past for new vehicles'
            })
        
        # Validate maintenance date order
        if last_maintenance and next_maintenance and next_maintenance <= last_maintenance:
            raise serializers.ValidationError({
                'next_maintenance': 'Next maintenance must be after last maintenance'
            })

    @staticmethod
    @transaction.atomic
    def create_vehicle(validated_data, request_user=None) -> Vehicle:
        """Create vehicle with business logic"""
        if not request_user or not request_user.is_authenticated:
            raise serializers.ValidationError('Authentication required to create a vehicle')
        
        # Extract fields for validation
        school = validated_data.get('school')
        plate_number = validated_data.get('plate_number')
        year = validated_data.get('year')
        last_maintenance = validated_data.get('last_maintenance')
        next_maintenance = validated_data.get('next_maintenance')
        
        # Validate creation
        VehicleService.validate_vehicle_creation(
            school, plate_number, year, last_maintenance, next_maintenance, request_user
        )
        
        # Auto-schedule maintenance if not provided
        if not next_maintenance:
            if last_maintenance:
                validated_data['next_maintenance'] = last_maintenance + timedelta(days=VehicleService.MAINTENANCE_INTERVAL_DAYS)
            else:
                validated_data['next_maintenance'] = timezone.now().date() + timedelta(days=VehicleService.INITIAL_MAINTENANCE_DAYS)
        
        # Create the vehicle
        return Vehicle.objects.create(**validated_data)

    @staticmethod
    @transaction.atomic
    def update_vehicle(instance, validated_data) -> Vehicle:
        """Update vehicle with business logic"""
        # Prevent changing school
        validated_data.pop('school', None)
        
        # Update instance
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        instance.save()
        return instance

    @staticmethod
    def is_available(vehicle) -> bool:
        """Check if vehicle is available for scheduling"""
        return vehicle.status == 'available'

    @staticmethod
    def get_maintenance_status(vehicle) -> str:
        """Get maintenance status description"""
        if not vehicle.next_maintenance:
            return 'No maintenance scheduled'
        
        next_maintenance = vehicle.next_maintenance
        if isinstance(next_maintenance, str):
            next_maintenance = datetime.strptime(next_maintenance, "%Y-%m-%d").date()
            
        date = timezone.now().date()

        days_until = (next_maintenance - date).days
        
        if days_until < 0:
            return f'Overdue by {abs(days_until)} days'
        elif days_until <= 7:
            return f'Due in {days_until} days'
        elif days_until <= 30:
            return f'Due in {days_until} days'
        return f'Scheduled for {vehicle.next_maintenance}'

    @staticmethod
    def get_vehicle_age(vehicle) -> int:
        """Calculate vehicle age in years"""
        current_year = timezone.now().year
        return current_year - vehicle.year

    @staticmethod
    def get_vehicle_utilization(vehicle, start_date, end_date) -> dict:
        """Calculate vehicle utilization statistics"""
        from .models import Schedule
        
        # Get scheduled hours for the vehicle
        schedules = Schedule.objects.filter(
            vehicle=vehicle,
            start_time__date__range=[start_date, end_date]
        )
        
        total_scheduled_hours = sum(
            (schedule.end_time - schedule.start_time).total_seconds() / 3600 
            for schedule in schedules
        )
        
        total_days = (end_date - start_date).days + 1
        max_possible_hours = total_days * 8  # Assuming 8 hours per day max
        
        utilization_rate = (total_scheduled_hours / max_possible_hours * 100) if max_possible_hours > 0 else 0
        
        return {
            'total_scheduled_hours': round(total_scheduled_hours, 2),
            'utilization_rate': round(utilization_rate, 2),
            'scheduled_lessons': schedules.count(),
            'period_days': total_days
        }

    @staticmethod
    def get_maintenance_overdue_vehicles(school=None):
        """Get vehicles with overdue maintenance"""
        today = timezone.now().date()
        queryset = Vehicle.objects.filter(next_maintenance__lt=today)
        
        if school:
            queryset = queryset.filter(school=school)
        
        return queryset.order_by('next_maintenance')

    @staticmethod
    def get_upcoming_maintenance_vehicles(school=None, days=30):
        """Get vehicles with maintenance due in the next X days"""
        today = timezone.now().date()
        due_date = today + timedelta(days=days)
        
        queryset = Vehicle.objects.filter(
            next_maintenance__range=[today, due_date]
        )
        
        if school:
            queryset = queryset.filter(school=school)
        
        return queryset.order_by('next_maintenance')

    @staticmethod
    def perform_maintenance(vehicle, maintenance_date=None, notes=None):
        """Perform maintenance on a vehicle and schedule next one"""
        if maintenance_date is None:
            maintenance_date = timezone.now().date()
        
        vehicle.last_maintenance = maintenance_date
        vehicle.next_maintenance = maintenance_date + timedelta(days=VehicleService.MAINTENANCE_INTERVAL_DAYS)
        vehicle.status = 'available'  # Ensure it's available after maintenance
        
        # In a real application, you might want to create a MaintenanceRecord here
        # MaintenanceRecord.objects.create(vehicle=vehicle, date=maintenance_date, notes=notes)
        
        vehicle.save()
        return vehicle

    @staticmethod
    def can_modify_vehicle(user, vehicle) -> bool:
        """Check if user has permission to modify this vehicle"""
        if not user or not user.is_authenticated:
            return False
        
        # Platform admins (staff) can modify any vehicle
        if user.role == 'A' and user.is_staff:
            return True
        
        # School owners (non-staff admins) can modify vehicles in their schools
        if user.role == 'A' and not user.is_staff:
            return vehicle.school.owner == user
        
        # Instructors can modify vehicles in their school
        if user.role == 'I':
            # Get instructor's school through their student profile
            try:
                instructor_profile = user.student_profiles.filter(status='A').first()
                if instructor_profile:
                    return instructor_profile.school == vehicle.school
            except AttributeError:
                pass
            return False
        
        # Students cannot modify vehicles
        return False

    @staticmethod
    def get_vehicle_statistics(school=None):
        """Get comprehensive vehicle statistics"""
        from django.db.models import Avg, Count, Q
        
        queryset = Vehicle.objects.all()
        if school:
            queryset = queryset.filter(school=school)
        
        total_vehicles = queryset.count()
        available_vehicles = queryset.filter(status='available').count()
        maintenance_vehicles = queryset.filter(status='maintenance').count()
        reserved_vehicles = queryset.filter(status='reserved').count()
        out_of_service_vehicles = queryset.filter(status='out_of_service').count()
        
        # Average vehicle age - FIXED: Use proper aggregation
        current_year = timezone.now().year
        average_age_result = queryset.aggregate(
            avg_age=Avg(current_year - F('year'))
        )
        average_age = average_age_result['avg_age'] or 0
        
        # Maintenance statistics
        today = timezone.now().date()
        overdue_maintenance = queryset.filter(next_maintenance__lt=today).count()
        upcoming_maintenance = queryset.filter(
            next_maintenance__range=[today, today + timedelta(days=30)]
        ).count()
        
        return {
            'total_vehicles': total_vehicles,
            'available_vehicles': available_vehicles,
            'maintenance_vehicles': maintenance_vehicles,
            'reserved_vehicles': reserved_vehicles,
            'out_of_service_vehicles': out_of_service_vehicles,
            'availability_rate': round((available_vehicles / total_vehicles * 100), 2) if total_vehicles > 0 else 0,
            'average_age': round(average_age, 1),
            'overdue_maintenance': overdue_maintenance,
            'upcoming_maintenance': upcoming_maintenance
        }

class StudentDocumentService:

    @staticmethod
    def get_file_url(student_document, request=None) -> Optional[str]:
        if not student_document.file:
            return None
        
        try:
            if request:
                return request.build_absolute_uri(student_document.file.url)
            return student_document.file.url
        except Exception :
            return None
        
    @staticmethod
    def validate_file_size(file) -> str:
        if file:
            try:
                size_bytes = file.size
                if size_bytes < 1024:
                    return f"{size_bytes} B"
                elif size_bytes < 1024 * 1024:
                    return f"{size_bytes / 1024:.2f} KB"
                else:
                    return f"{size_bytes / (1024 * 1024):.2f} MB"
            except Exception:
                return "Unknown"
        return None
    
    @staticmethod
    def validate_file_extension(file) -> None:
        if file:
            ext =  os.path.splitext(file.name)[1].lower()
            allowed_extensions = ['.pdf', '.jpg', '.jpeg', '.png', '.doc', '.docx']
            if ext not in allowed_extensions:
                raise serializers.ValidationError(
                    f"File type {ext} not allowed. Allowed types:{', '.join(allowed_extensions)}"
                )
        


    @staticmethod
    def validate_document_creation(student, file ,request_user=None) -> None:
        if student is None:
            raise serializers.ValidationError("Student is required")
        
        if request_user and request_user.role == 'S':
            if student.user != request_user:
                raise serializers.ValidationError("You can only upload your own documents")
        
        StudentDocumentService.validate_file_upload(file)

    @staticmethod
    def can_modify_document(user, document) -> bool:
        """Check if user can modify this document"""
        if user.role == 'A':
            return document.student.school.owner == user
        elif user.role == 'I':
            # Check if instructor is assigned to the same school
            return document.student.school == user.student_profiles.first().school
        elif user.role == 'S':
            return document.student.user == user
        return False

    @staticmethod
    def validate_file_upload(file) -> None:
        """Validate file upload - size and extension"""
        # Check file size
        max_size = 10 * 1024 * 1024
        if file.size > max_size:
            raise serializers.ValidationError(f"File too large: {file.size} bytes")
        
        # Check extension
        StudentDocumentService.validate_file_extension(file)

    @staticmethod
    @transaction.atomic
    def create_document(validated_data, request_user = None) -> StudentDocument:
        student = validated_data.get('student')
        file = validated_data.get('file')

        StudentDocumentService.validate_document_creation(student, file, request_user)

        return StudentDocument.objects.create(**validated_data)
    
    @staticmethod
    @transaction.atomic
    def update_document(instance ,validated_data) -> StudentDocument:
        validated_data.pop('student', None)

        if 'file' in validated_data:
            StudentDocumentService.validate_file_upload(validated_data['file'])
            
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        instance.save()

        return instance
    
class SubscriptionPlanService:
    """Handle all SubscriptionPlan business logic and operations"""
    
    # Configuration
    MIN_PRICE = 0
    MIN_STUDENTS = 1
    MIN_INSTRUCTORS = 1
    MIN_DURATION_DAYS = 1
    
    @staticmethod
    def validate_plan_creation(price, max_students, max_instructors, duration_days, features) -> None:
        """Validate subscription plan creation business rules"""
        # Validate price
        SubscriptionPlanService.validate_price(price)
        
        # Validate limits
        SubscriptionPlanService.validate_limits(max_students, max_instructors)
        
        # Validate duration
        SubscriptionPlanService.validate_duration(duration_days)
        
        # Validate features
        SubscriptionPlanService.validate_features(features)

    @staticmethod
    def validate_plan_update(instance, validated_data) -> None:
        """Validate subscription plan update business rules"""
        price = validated_data.get('price', instance.price)
        max_students = validated_data.get('max_students', instance.max_students)
        max_instructors = validated_data.get('max_instructors', instance.max_instructors)
        duration_days = validated_data.get('duration_days', instance.duration_days)
        features = validated_data.get('features', instance.features)
        
        # Validate price if changed
        if 'price' in validated_data:
            SubscriptionPlanService.validate_price(price)
        
        # Validate limits if changed
        if any(field in validated_data for field in ['max_students', 'max_instructors']):
            SubscriptionPlanService.validate_limits(max_students, max_instructors)
        
        # Validate duration if changed
        if 'duration_days' in validated_data:
            SubscriptionPlanService.validate_duration(duration_days)
        
        # Validate features if changed
        if 'features' in validated_data:
            SubscriptionPlanService.validate_features(features)

    @staticmethod
    def validate_price(price) -> None:
        """Validate price is reasonable"""
        if price < SubscriptionPlanService.MIN_PRICE:
            raise serializers.ValidationError({
                'price': 'Price cannot be negative'
            })

    @staticmethod
    def validate_limits(max_students, max_instructors) -> None:
        """Validate student and instructor limits"""
        if max_students < SubscriptionPlanService.MIN_STUDENTS:
            raise serializers.ValidationError({
                'max_students': 'Must allow at least 1 student'
            })

        if max_instructors < SubscriptionPlanService.MIN_INSTRUCTORS:
            raise serializers.ValidationError({
                'max_instructors': 'Must allow at least 1 instructor'
            })

    @staticmethod
    def validate_duration(duration_days) -> None:
        """Validate duration is reasonable"""
        if duration_days < SubscriptionPlanService.MIN_DURATION_DAYS:
            raise serializers.ValidationError({
                'duration_days': 'Duration must be at least 1 day'
            })

    @staticmethod
    def validate_features(features) -> None:
        """Validate features JSON structure"""
        if not isinstance(features, dict):
            raise serializers.ValidationError("Features must be a dictionary")

    @staticmethod
    def get_price_formatted(price) -> str:
        """Format price with currency"""
        return f"${price:.2f}"

    @staticmethod
    def get_duration_display(duration_days) -> str:
        """Convert duration to human-readable format"""
        if duration_days == 30:
            return "Monthly"
        elif duration_days == 365:
            return "Yearly"
        else:
            return f"{duration_days} days"

    @staticmethod
    def get_subscription_count(plan) -> int:
        """Count active subscriptions on this plan"""
        return plan.subscriptions.filter(status='active').count()

    @staticmethod
    def get_is_popular(plan) -> bool:
        """Check if plan is the most popular (most active subscriptions)"""
        
        active_plans = SubscriptionPlan.objects.filter(is_active=True).annotate(
            active_sub_count=Count(
                'subscription', 
                filter=Q(subscription__status='active')
            )
        )
        
        if active_plans:
            most_popular = max(active_plans, key=lambda x: x.active_sub_count)
            return plan.id == most_popular.id
        return False

    @staticmethod
    def get_popular_plans(limit=3):
        """Get most popular subscription plans"""
        
        return SubscriptionPlan.objects.filter(is_active=True).annotate(
            active_sub_count=Count(
                'subscription', 
                filter=Q(subscription__status='active')
            )
        ).order_by('-active_sub_count')[:limit]

    @staticmethod
    def get_active_plans():
        """Get all active subscription plans"""
        return SubscriptionPlan.objects.filter(is_active=True).order_by('price')

    @staticmethod
    def can_deactivate_plan(plan) -> bool:
        """Check if plan can be deactivated (no active subscriptions)"""
        active_subscriptions = SchoolSubscription.objects.filter(
            plan=plan, 
            status='active'
        ).exists()
        return not active_subscriptions

    @staticmethod
    def get_plan_statistics(plan) -> dict:
        """Get comprehensive statistics for a plan"""
        total_subscriptions = SchoolSubscription.objects.filter(plan=plan).count()
        active_subscriptions = SchoolSubscription.objects.filter(
            plan=plan, 
            status='active'
        ).count()
        canceled_subscriptions = SchoolSubscription.objects.filter(
            plan=plan, 
            status='canceled'
        ).count()
        
        # Calculate estimated monthly revenue
        estimated_monthly_revenue = active_subscriptions * plan.price
        
        return {
            'total_subscriptions': total_subscriptions,
            'active_subscriptions': active_subscriptions,
            'canceled_subscriptions': canceled_subscriptions,
            'estimated_monthly_revenue': estimated_monthly_revenue,
            'popularity_rank': SubscriptionPlanService.get_popularity_rank(plan)
        }

    @staticmethod
    def get_popularity_rank(plan) -> int:
        """Get popularity rank of plan among active plans"""
        from django.db.models import Count, Q
        
        plans_with_counts = SubscriptionPlan.objects.filter(is_active=True).annotate(
            active_sub_count=Count(
                'subscription', 
                filter=Q(subscription__status='active')
            )
        ).order_by('-active_sub_count')
        
        for rank, p in enumerate(plans_with_counts, 1):
            if p.id == plan.id:
                return rank
        return 0

    @staticmethod
    def get_recommended_plan(school_size, budget, duration_preference='monthly') -> SubscriptionPlan:
        """Get recommended plan based on school needs"""
        plans = SubscriptionPlan.objects.filter(is_active=True)
        
        # Convert duration preference to days
        duration_days = 30 if duration_preference == 'monthly' else 365
        
        # Filter by duration preference
        plans = plans.filter(duration_days=duration_days)
        
        # Filter by school size (max_students should accommodate school_size)
        plans = plans.filter(max_students__gte=school_size)
        
        # Filter by budget
        plans = plans.filter(price__lte=budget)
        
        # Return the plan with highest value (most features for price)
        if plans.exists():
            return plans.order_by('-max_students', 'price').first()
        return None

    @staticmethod
    @transaction.atomic
    def create_plan(validated_data) -> SubscriptionPlan:
        """Create subscription plan with business logic"""
        # Extract fields for validation
        price = validated_data.get('price')
        max_students = validated_data.get('max_students')
        max_instructors = validated_data.get('max_instructors')
        duration_days = validated_data.get('duration_days')
        features = validated_data.get('features', {})
        
        # Validate creation
        SubscriptionPlanService.validate_plan_creation(
            price, max_students, max_instructors, duration_days, features
        )
        
        # Create the plan
        return SubscriptionPlan.objects.create(**validated_data)

    @staticmethod
    @transaction.atomic
    def update_plan(instance, validated_data) -> SubscriptionPlan:
        """Update subscription plan with business logic"""
        # Validate update
        SubscriptionPlanService.validate_plan_update(instance, validated_data)
        
        # Update instance
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        instance.save()
        return instance

    @staticmethod
    def deactivate_plan(plan) -> bool:
        """Deactivate plan if no active subscriptions"""
        if SubscriptionPlanService.can_deactivate_plan(plan):
            plan.is_active = False
            plan.save()
            return True
        return False

    @staticmethod
    def activate_plan(plan) -> None:
        """Activate plan"""
        plan.is_active = True
        plan.save()

    @staticmethod
    def get_plan_comparison():
        """Get comparison data for all active plans"""
        active_plans = SubscriptionPlanService.get_active_plans()
        
        comparison_data = []
        for plan in active_plans:
            stats = SubscriptionPlanService.get_plan_statistics(plan)
            comparison_data.append({
                'plan': plan,
                'stats': stats,
                'price_per_student': plan.price / plan.max_students if plan.max_students > 0 else plan.price,
                'is_popular': SubscriptionPlanService.get_is_popular(plan)
            })
        
        return comparison_data
    
class SchoolSubscriptionService:
    """Handle all SchoolSubscription business logic and operations"""
    
    @staticmethod
    def get_days_remaining(subscription) -> int:
        """Calculate days remaining in current period"""
        if subscription.current_period_end:
            delta = subscription.current_period_end.date() - timezone.now().date()
            return max(0, delta.days)
        return 0

    @staticmethod
    def is_expired(subscription) -> bool:
        """Check if subscription is expired"""
        if subscription.status in ['canceled', 'past_due']:
            return True
        if subscription.current_period_end and subscription.current_period_end < timezone.now():
            return True
        return False

    @staticmethod
    def can_add_student(subscription) -> bool:
        """Check if school can add more students"""
        current_count = subscription.school.student_profiles.count()
        return current_count < subscription.plan.max_students

    @staticmethod
    def can_add_instructor(subscription) -> bool:
        """Check if school can add more instructors"""
        instructor_count = StudentProfile.objects.filter(
            school=subscription.school,
            user__role='I',
            status='A'
        ).count()
        return instructor_count < subscription.plan.max_instructors

    @staticmethod
    def get_usage_stats(subscription) -> dict:
        """Get current usage statistics"""
        instructor_count = StudentProfile.objects.filter(
            school=subscription.school,
            user__role='I',
            status='A'
        ).count()
        
        student_count = subscription.school.student_profiles.count()
        
        return {
            'students': {
                'current': student_count,
                'limit': subscription.plan.max_students,
                'percentage': round((student_count / subscription.plan.max_students) * 100, 1) if subscription.plan.max_students > 0 else 0
            },
            'instructors': {
                'current': instructor_count,
                'limit': subscription.plan.max_instructors,
                'percentage': round((instructor_count / subscription.plan.max_instructors) * 100, 1) if subscription.plan.max_instructors > 0 else 0
            },
            'period': {
                'start': subscription.current_period_start,
                'end': subscription.current_period_end,
                'days_remaining': SchoolSubscriptionService.get_days_remaining(subscription)
            }
        }

    @staticmethod
    def validate_subscription_creation(school, plan, current_period_start, current_period_end) -> None:
        """Validate subscription creation business rules"""
        # Check if school already has subscription
        if hasattr(school, 'subscription'):
            raise serializers.ValidationError({
                'school': 'This school already has an active subscription'
            })
        
        # Validate period dates
        if current_period_start and current_period_end:
            if current_period_end <= current_period_start:
                raise serializers.ValidationError({
                    'current_period_end': 'End date must be after start date'
                })

    @staticmethod
    def validate_subscription_update(instance, validated_data) -> None:
        """Validate subscription update business rules"""
        current_period_start = validated_data.get('current_period_start', instance.current_period_start)
        current_period_end = validated_data.get('current_period_end', instance.current_period_end)
        status = validated_data.get('status', instance.status)
        
        # Validate period dates if changed
        if any(field in validated_data for field in ['current_period_start', 'current_period_end']):
            if current_period_end <= current_period_start:
                raise serializers.ValidationError({
                    'current_period_end': 'End date must be after start date'
                })
        
        # Validate status transitions
        if 'status' in validated_data:
            SchoolSubscriptionService._validate_status_transition(instance.status, status)

    @staticmethod
    def _validate_status_transition(current_status, new_status) -> None:
        """Validate status transition logic"""
        valid_transitions = {
            'trialing': ['active', 'canceled','past_due'],
            'active': ['canceled', 'past_due'],
            'past_due': ['active', 'canceled'],
            'canceled': []  # Final state
        }
        
        if new_status != current_status:
            if new_status not in valid_transitions.get(current_status, []):
                raise serializers.ValidationError(
                    f"Cannot transition from {current_status} to {new_status}"
                )

    @staticmethod
    @transaction.atomic
    def create_subscription(validated_data) -> SchoolSubscription:
        """Create subscription with business logic"""
        school = validated_data.get('school')
        plan = validated_data.get('plan')
        current_period_start = validated_data.get('current_period_start')
        current_period_end = validated_data.get('current_period_end')
        
        # Validate creation
        SchoolSubscriptionService.validate_subscription_creation(
            school, plan, current_period_start, current_period_end
        )
        
        # Create the subscription
        return SchoolSubscription.objects.create(**validated_data)

    @staticmethod
    @transaction.atomic
    def update_subscription(instance, validated_data) -> SchoolSubscription:
        """Update subscription with business logic"""
        # Validate update
        SchoolSubscriptionService.validate_subscription_update(instance, validated_data)
        
        # Prevent changing school
        validated_data.pop('school', None)
        
        # Update instance
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        instance.save()
        return instance

    @staticmethod
    def check_usage_limits(subscription) -> dict:
        """Check if school is approaching usage limits"""
        stats = SchoolSubscriptionService.get_usage_stats(subscription)
        
        warnings = []
        if stats['students']['percentage'] >= 90:
            warnings.append(f"Student limit almost reached: {stats['students']['current']}/{stats['students']['limit']}")
        if stats['instructors']['percentage'] >= 90:
            warnings.append(f"Instructor limit almost reached: {stats['instructors']['current']}/{stats['instructors']['limit']}")
        
        return {
            'warnings': warnings,
            'stats': stats,
            'is_near_limits': len(warnings) > 0
        }
    
    
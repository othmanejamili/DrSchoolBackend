"""
Signal handlers for automatic cache invalidation.
"""

from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver
from django.core.cache import cache
from .models import (User, StudentProfile, DrivingSchool, Lesson, Schedule,
                      Feedback, Attendance, Vehicle, VehiclePicture, Achievement,
                      CommunicationTemplate, AutomatedMessage, SchoolAnalytics,
                          User, StudentProfile, DrivingSchool, Lesson, Schedule, SubscriptionPlan, SchoolSubscription
                      )
from .cache_utils import (
    invalidate_lesson_cache,
    invalidate_lesson_queryset_caches,
    invalidate_instructor_lesson_caches,
    invalidate_school_lesson_caches,
    get_lesson_attendance_cache_key,
    get_lesson_feedback_cache_key,
    get_lesson_schedule_cache_key,
    invalidate_feedback_cache,
    invalidate_feedback_queryset_caches,
    invalidate_lesson_feedback_caches,
    invalidate_student_feedback_caches,
    invalidate_instructor_feedback_caches,
    invalidate_vehicle_cache,
    invalidate_vehicle_queryset_caches,
    invalidate_vehicle_maintenance_caches,
    invalidate_vehicle_statistics_caches,
    invalidate_school_vehicle_caches,
    invalidate_vehicle_pictures_cache,
    invalidate_school_schedule_caches,
    invalidate_schedule_queryset_caches,
    invalidate_schedule_cache,
    invalidate_instructor_schedule_caches,
    invalidate_vehicle_schedule_caches,
    invalidate_availability_caches,
    invalidate_school_caches,
    get_dashboard_cache_key,
    get_quick_stats_cache_key,
    get_notifications_cache_key,
    invalidate_dashboard_caches,
    # Other cache utilities you might have
    invalidate_report_cache,
    invalidate_subscription_cache,invalidate_school_subscription_caches, invalidate_school_subscription_caches,
    invalidate_plan_cache, invalidate_subscription_plan_caches



    
)

# ============================================
# USER SIGNAL HANDLERS
# ============================================

@receiver([post_save, post_delete], sender=User)
def invalidate_user_cache(sender, instance, **kwargs):
    """Invalidate user cache when user is saved or deleted"""
    from .cache_utils import invalidate_user_caches, get_user_stats_cache_key
    
    invalidate_user_caches(instance.id)
    cache.delete(get_user_stats_cache_key())
    cache.delete('school_stats')  # Also clear school stats


@receiver([post_save, post_delete], sender=StudentProfile)
def invalidate_profile_cache(sender, instance, **kwargs):
    """Invalidate cache when student profile is updated or deleted"""
    from .cache_utils import invalidate_user_caches, invalidate_school_caches
    
    invalidate_user_caches(instance.user_id)
    invalidate_school_caches(instance.school_id)


@receiver([post_save, post_delete], sender=DrivingSchool)
def invalidate_school_cache(sender, instance, **kwargs):
    """Invalidate school cache when school is saved or deleted"""
    from .cache_utils import invalidate_school_caches, get_school_stats_cache_key
    
    # Invalidate school caches
    invalidate_school_caches(instance.id)
    cache.delete(get_school_stats_cache_key())
    
    # Also invalidate owner's schools cache if owner exists
    if hasattr(instance, 'owner') and instance.owner:
        # Clear owner-specific school caches
        cache.delete(f'schools_queryset_{instance.owner.id}_{instance.owner.role}')


# ============================================
# LESSON SIGNAL HANDLERS
# ============================================

@receiver([post_save, post_delete], sender=Lesson)
def invalidate_lesson_on_change(sender, instance, **kwargs):
    """Invalidate lesson caches when lesson is created, updated, or deleted"""
    invalidate_lesson_cache(instance.id)
    invalidate_lesson_queryset_caches()
    
    if instance.instructor_id:
        invalidate_instructor_lesson_caches(instance.instructor_id)
    
    if instance.school_id:
        invalidate_school_lesson_caches(instance.school_id)


# ============================================
# ATTENDANCE SIGNAL HANDLERS
# ============================================

@receiver([post_save, post_delete], sender=Attendance)
def invalidate_attendance_on_change(sender, instance, **kwargs):
    """Invalidate attendance caches when attendance is marked or updated"""
    if instance.lesson_id:
        cache_key = get_lesson_attendance_cache_key(instance.lesson_id)
        cache.delete(cache_key)
        
        # Also invalidate lesson statistics
        if hasattr(instance, 'lesson') and instance.lesson.instructor_id:
            from .cache_utils import get_lesson_statistics_cache_key
            cache.delete(get_lesson_statistics_cache_key(
                instance.lesson.instructor_id,
                'I'
            ))
    
    # Invalidate student statistics if student present
    if instance.student_id and instance.presence:
        from .cache_utils import get_lesson_statistics_cache_key
        if hasattr(instance.student, 'user'):
            cache.delete(get_lesson_statistics_cache_key(
                instance.student.user_id,
                'S'
            ))


# ============================================
# FEEDBACK SIGNAL HANDLERS
# ============================================

@receiver([post_save, post_delete], sender=Feedback)
def invalidate_feedback_on_change(sender, instance, **kwargs):
    """Invalidate feedback caches when feedback is added or updated"""
    if instance.lesson_id:
        cache_key = get_lesson_feedback_cache_key(instance.lesson_id)
        cache.delete(cache_key)


# ============================================
# SCHEDULE SIGNAL HANDLERS
# ============================================

@receiver([post_save, post_delete], sender=Schedule)
def invalidate_schedule_on_change(sender, instance, **kwargs):
    """Invalidate schedule caches when schedule is created or updated"""
    if instance.lesson_id:
        cache_key = get_lesson_schedule_cache_key(instance.lesson_id)
        cache.delete(cache_key)
        
        # Also invalidate upcoming lessons cache
        if hasattr(instance.lesson, 'instructor'):
            from .cache_utils import get_upcoming_lessons_cache_key
            cache.delete(get_upcoming_lessons_cache_key(
                instance.lesson.instructor_id,
                'I'
            ))


@receiver([post_save, post_delete], sender=Feedback)
def invalidate_feedback_caches(sender, instance, **kwargs):
    """
    Invalidate feedback caches when feedback is created, updated, or deleted.
    This ensures users always see fresh feedback data.
    """
    # Invalidate specific feedback cache
    invalidate_feedback_cache(instance.id)
    
    # Invalidate all feedback querysets
    invalidate_feedback_queryset_caches()
    
    # Invalidate lesson-specific feedback caches
    if instance.lesson_id:
        invalidate_lesson_feedback_caches(instance.lesson_id)
        
        # Also invalidate the lesson's instructor feedback caches
        if hasattr(instance.lesson, 'instructor_id') and instance.lesson.instructor_id:
            invalidate_instructor_feedback_caches(instance.lesson.instructor_id)
    
    # Invalidate student-specific feedback caches
    if instance.student_id:
        invalidate_student_feedback_caches(instance.student_id)
        
        # Also invalidate "my_feedback" cache for the student user
        if hasattr(instance.student, 'user_id'):
            from .cache_utils import get_my_feedback_cache_key
            cache.delete(get_my_feedback_cache_key(instance.student.user_id))


# ============================================
# VEHICLE SIGNAL HANDLERS
# ============================================

@receiver([post_save, post_delete], sender=Vehicle)
def invalidate_vehicle_on_change(sender, instance, **kwargs):
    """
    Invalidate vehicle caches when vehicle is created, updated, or deleted.
    This ensures users always see fresh vehicle data.
    """
    # Invalidate specific vehicle cache
    invalidate_vehicle_cache(instance.id)
    
    # Invalidate all vehicle querysets
    invalidate_vehicle_queryset_caches()
    
    # Invalidate maintenance caches (status/dates may have changed)
    invalidate_vehicle_maintenance_caches()
    
    # Invalidate statistics caches
    invalidate_vehicle_statistics_caches()
    
    # Invalidate school-specific caches
    if instance.school_id:
        invalidate_school_vehicle_caches(instance.school_id)


# ============================================
# VEHICLE PICTURE SIGNAL HANDLERS
# ============================================

@receiver([post_save, post_delete], sender=VehiclePicture)
def invalidate_vehicle_picture_on_change(sender, instance, **kwargs):
    """
    Invalidate vehicle picture caches when pictures are added, updated, or deleted.
    """
    if instance.vehicle_id:
        # Invalidate vehicle pictures cache
        invalidate_vehicle_pictures_cache(instance.vehicle_id)
        
        # Also invalidate vehicle detail cache (includes primary picture)
        invalidate_vehicle_cache(instance.vehicle_id)


# ============================================
# SCHEDULE SIGNALS
# ============================================

@receiver([post_save, post_delete], sender=Schedule)
def invalidate_schedule_caches_on_change(sender, instance, **kwargs):
    """
    Invalidate schedule caches when schedule is created, updated, or deleted.
    """
    # Invalidate specific schedule
    invalidate_schedule_cache(instance.id)
    
    # Invalidate all schedule querysets
    invalidate_schedule_queryset_caches()
    
    # Invalidate availability caches (slots may have opened/closed)
    invalidate_availability_caches()
    
    # Invalidate instructor-specific caches
    if instance.instructor_id:
        invalidate_instructor_schedule_caches(instance.instructor_id)
    
    # Invalidate vehicle-specific caches
    if instance.vehicle_id:
        invalidate_vehicle_schedule_caches(instance.vehicle_id)
    
    # Invalidate school-specific caches
    if instance.lesson and instance.lesson.school_id:
        invalidate_school_schedule_caches(instance.lesson.school_id)


# ============================================
# ACHIEVEMENT SIGNALS
# ============================================

@receiver([post_save, post_delete], sender=Achievement)
def invalidate_achievement_on_change(sender, instance, **kwargs):
    """Invalidate achievement caches when achievement is created/deleted"""
    from .cache_utils import (invalidate_achievement_cache,
                              invalidate_achievement_queryset_caches,
                              invalidate_leaderboard_caches,
                              invalidate_achievement_statistics_caches,
                              invalidate_student_achievement_caches)
    
    # Invalidate specific achievement
    invalidate_achievement_cache(instance.id)
    
    # Invalidate all querysets
    invalidate_achievement_queryset_caches()
    
    # Invalidate leaderboards (points changed)
    invalidate_leaderboard_caches()
    
    # Invalidate statistics
    invalidate_achievement_statistics_caches()
    
    # Invalidate student-specific caches
    if instance.student_id:
        invalidate_student_achievement_caches(instance.student_id)

@receiver([post_save, post_delete], sender=CommunicationTemplate)
def invalidate_communication_template_signal(sender, instance, **kwargs):
    """Invalidate template cache when template is saved or deleted"""
    from .cache_utils import (
        invalidate_communication_template_cache,
        invalidate_communication_template_queryset_caches,
        invalidate_school_template_caches
    )
    
    invalidate_communication_template_cache(
        instance.id,
        school_id=instance.school_id
    )
    invalidate_communication_template_queryset_caches()
    invalidate_school_template_caches(instance.school_id)

@receiver([post_save, post_delete], sender=AutomatedMessage)
def invalidate_automated_message_signal(sender, instance, **kwargs):
    """Invalidate message cache when message is saved or deleted"""
    from .cache_utils import (
        invalidate_automated_message_cache,
        invalidate_automated_message_queryset_caches,
        invalidate_student_message_caches,
        invalidate_template_message_caches
    )
    
    invalidate_automated_message_cache(
        instance.id,
        student_id=instance.student_id,
        template_id=instance.template_id
    )
    invalidate_automated_message_queryset_caches()
    invalidate_student_message_caches(instance.student_id)
    invalidate_template_message_caches(instance.template_id)

# ============================================
# SCHOOL ANALYTICS SIGNAL HANDLERS
# ============================================

@receiver([post_save, post_delete], sender=SchoolAnalytics)
def invalidate_school_analytics_signal(sender, instance, **kwargs):
    """Invalidate analytics cache when analytics record is saved or deleted"""
    from .cache_utils import (
        invalidate_school_analytics_cache,
        invalidate_school_analytics_queryset_caches,
        invalidate_school_specific_analytics_caches
    )
    
    invalidate_school_analytics_cache(instance.id, school_id=instance.school_id)
    invalidate_school_analytics_queryset_caches()
    invalidate_school_specific_analytics_caches(instance.school_id)
    
    # Also invalidate school caches since analytics affects school stats
    invalidate_school_caches(instance.school_id)

# ============================================
# REPORT CACHE INVALIDATION SIGNALS
# ============================================

# When SchoolAnalytics changes, invalidate report caches
@receiver([post_save, post_delete], sender=SchoolAnalytics)
def invalidate_report_caches_on_analytics_change(sender, instance, **kwargs):
    """Invalidate report caches when analytics data changes"""
    from .cache_utils import invalidate_report_cache
    invalidate_report_cache(instance.school_id)


# When Lesson changes, invalidate report caches
@receiver([post_save, post_delete], sender=Lesson)
def invalidate_report_caches_on_lesson_change(sender, instance, **kwargs):
    """Invalidate report caches when lesson data changes"""
    from .cache_utils import invalidate_report_cache, invalidate_instructor_report_caches
    invalidate_report_cache(instance.school_id)
    if instance.instructor_id:
        invalidate_instructor_report_caches(instance.school_id, instance.instructor_id)


# When Feedback changes, invalidate report caches
@receiver([post_save, post_delete], sender=Feedback)
def invalidate_report_caches_on_feedback_change(sender, instance, **kwargs):
    """Invalidate report caches when feedback changes"""
    from .cache_utils import invalidate_report_cache, invalidate_instructor_report_caches
    school_id = instance.lesson.school_id
    invalidate_report_cache(school_id)
    if instance.lesson.instructor_id:
        invalidate_instructor_report_caches(school_id, instance.lesson.instructor_id)


# When StudentProfile changes, invalidate student report caches
@receiver([post_save, post_delete], sender=StudentProfile)
def invalidate_report_caches_on_student_change(sender, instance, **kwargs):
    """Invalidate report caches when student profile changes"""
    from .cache_utils import invalidate_student_report_caches
    invalidate_student_report_caches(instance.school_id)


# When Attendance changes, invalidate report caches
@receiver([post_save, post_delete], sender=Attendance)
def invalidate_report_caches_on_attendance_change(sender, instance, **kwargs):
    """Invalidate report caches when attendance changes"""
    from .cache_utils import invalidate_report_cache
    school_id = instance.lesson.school_id
    invalidate_report_cache(school_id)

# ============================================
# DashBoard CACHE INVALIDATION SIGNALS
# ============================================
    


def invalidate_user_dashboards(user_id):
    """
    Enhanced version that invalidates all dashboard caches for a user.
    Uses your provided invalidate_dashboard_caches function.
    """
    if not user_id:
        return
    
    # Use the provided function
    invalidate_dashboard_caches(user_id)
    
    # Also clear specific notification caches
    user = User.objects.filter(id=user_id).first()
    if user:
        for role in ['A', 'I', 'S']:
            for limit in [10, 20, 50]:
                cache_key = get_notifications_cache_key(user_id, role, limit)
                cache.delete(cache_key)


def invalidate_school_dashboards(school_id):
    """
    Invalidate all dashboard caches for users in a school.
    """
    if not school_id:
        return
    
    # Get all users in this school
    student_profiles = StudentProfile.objects.filter(school_id=school_id).select_related('user')
    
    for profile in student_profiles:
        user = profile.user
        if user:
            invalidate_dashboard_caches(user.id)
    
    # Also invalidate school owner dashboard
    school = DrivingSchool.objects.filter(id=school_id).first()
    if school and school.owner:
        invalidate_dashboard_caches(school.owner_id)


def invalidate_all_dashboards():
    """
    Invalidate all dashboard caches in the system.
    Use sparingly (e.g., system maintenance).
    """
    patterns = [
        'dashboard_*',
        'dashboard_quick_stats_*',
        'dashboard_notifications_*',
    ]
    
    for pattern in patterns:
        try:
            cache.delete_pattern(pattern)
        except AttributeError:
            # Fallback for cache backends without delete_pattern
            pass


def invalidate_dashboard_cache(user_id, role, dashboard_type):
    """
    Invalidate specific dashboard cache.
    """
    cache_key = get_dashboard_cache_key(user_id, role, dashboard_type)
    cache.delete(cache_key)


# ============================================
# USER SIGNAL HANDLERS (DASHBOARD IMPACT)
# ============================================

@receiver([post_save, post_delete], sender=User)
def invalidate_user_dashboard_on_user_change(sender, instance, **kwargs):
    """
    Invalidate dashboard cache when user is saved or deleted.
    This affects all dashboards that might include this user.
    """
    # Invalidate user's own dashboard
    invalidate_dashboard_caches(instance.id)
    
    # If user is a school owner, invalidate school owner dashboards
    if instance.role == 'A' and not instance.is_staff:
        # Find all schools owned by this user
        schools = DrivingSchool.objects.filter(owner=instance)
        for school in schools:
            invalidate_school_dashboards(school.id)
    
    # If user is an instructor or student, invalidate their specific dashboards
    elif instance.role in ['I', 'S']:
        # Clear specific dashboard cache
        invalidate_dashboard_cache(instance.id, instance.role, instance.role)
        invalidate_dashboard_cache(instance.id, instance.role, 'overview')
        
        # Clear quick stats
        cache.delete(get_quick_stats_cache_key(instance.id, instance.role))


# ============================================
# STUDENT PROFILE SIGNAL HANDLERS
# ============================================

@receiver([post_save, post_delete], sender=StudentProfile)
def invalidate_dashboard_on_profile_change(sender, instance, **kwargs):
    """
    Invalidate dashboard cache when student profile changes.
    This affects student dashboards, school dashboards, and instructor dashboards.
    """
    user = instance.user
    school_id = instance.school_id
    
    # Invalidate user's dashboard
    invalidate_dashboard_caches(user.id)
    
    # Invalidate school dashboards
    invalidate_school_dashboards(school_id)
    
    # Invalidate specific caches
    invalidate_dashboard_cache(user.id, user.role, 'overview')
    cache.delete(get_quick_stats_cache_key(user.id, user.role))


# ============================================
# DRIVING SCHOOL SIGNAL HANDLERS
# ============================================

@receiver([post_save, post_delete], sender=DrivingSchool)
def invalidate_dashboard_on_school_change(sender, instance, **kwargs):
    """
    Invalidate dashboard cache when school changes.
    This affects school owner dashboards, platform admin dashboards,
    and dashboards of all users in the school.
    """
    school_id = instance.id
    owner_id = instance.owner_id
    
    # Invalidate school owner's dashboard
    invalidate_dashboard_caches(owner_id)
    
    # Invalidate all school-specific dashboards
    invalidate_school_dashboards(school_id)
    
    # Invalidate platform admin dashboards (they see all schools)
    platform_admins = User.objects.filter(role='A', is_staff=True)
    for admin in platform_admins:
        invalidate_dashboard_caches(admin.id)
    
    # Invalidate report caches for this school
    if hasattr(invalidate_report_cache, '__call__'):
        invalidate_report_cache(school_id)


# ============================================
# LESSON SIGNAL HANDLERS
# ============================================

@receiver([post_save, post_delete], sender=Lesson)
def invalidate_dashboard_on_lesson_change(sender, instance, **kwargs):
    """
    Invalidate dashboard cache when lesson changes.
    This affects instructor dashboards, student dashboards, and school dashboards.
    """
    school_id = instance.school_id
    instructor_id = instance.instructor_id
    
    # Invalidate instructor dashboard
    if instructor_id:
        invalidate_dashboard_caches(instructor_id)
        invalidate_dashboard_cache(instructor_id, 'I', 'instructor')
        invalidate_dashboard_cache(instructor_id, 'I', 'overview')
        cache.delete(get_quick_stats_cache_key(instructor_id, 'I'))
    
    # Invalidate school dashboards
    invalidate_school_dashboards(school_id)
    
    # Invalidate report caches
    if hasattr(invalidate_report_cache, '__call__'):
        invalidate_report_cache(school_id)


# ============================================
# ATTENDANCE SIGNAL HANDLERS
# ============================================

@receiver([post_save, post_delete], sender=Attendance)
def invalidate_dashboard_on_attendance_change(sender, instance, **kwargs):
    """
    Invalidate dashboard cache when attendance changes.
    This affects student dashboards and instructor dashboards.
    """
    student_id = instance.student_id
    lesson = instance.lesson
    school_id = lesson.school_id if lesson else None
    instructor_id = lesson.instructor_id if lesson else None
    
    # Invalidate student dashboard
    if student_id:
        student_profile = StudentProfile.objects.filter(id=student_id).first()
        if student_profile and student_profile.user:
            user_id = student_profile.user_id
            invalidate_dashboard_caches(user_id)
    
    # Invalidate instructor dashboard
    if instructor_id:
        invalidate_dashboard_caches(instructor_id)
        invalidate_dashboard_cache(instructor_id, 'I', 'instructor')
        invalidate_dashboard_cache(instructor_id, 'I', 'overview')
        cache.delete(get_quick_stats_cache_key(instructor_id, 'I'))
    
    # Invalidate school dashboards
    if school_id:
        invalidate_school_dashboards(school_id)
    
    # Invalidate report caches
    if school_id and hasattr(invalidate_report_cache, '__call__'):
        invalidate_report_cache(school_id)


# ============================================
# FEEDBACK SIGNAL HANDLERS
# ============================================

@receiver([post_save, post_delete], sender=Feedback)
def invalidate_dashboard_on_feedback_change(sender, instance, **kwargs):
    """
    Invalidate dashboard cache when feedback changes.
    This affects student dashboards, instructor dashboards, and school dashboards.
    """
    student_id = instance.student_id
    lesson = instance.lesson
    school_id = lesson.school_id if lesson else None
    instructor_id = lesson.instructor_id if lesson else None
    
    # Invalidate student dashboard
    if student_id:
        student_profile = StudentProfile.objects.filter(id=student_id).first()
        if student_profile and student_profile.user:
            user_id = student_profile.user_id
            invalidate_dashboard_caches(user_id)
    
    # Invalidate instructor dashboard
    if instructor_id:
        invalidate_dashboard_caches(instructor_id)
        invalidate_dashboard_cache(instructor_id, 'I', 'instructor')
        invalidate_dashboard_cache(instructor_id, 'I', 'overview')
        cache.delete(get_quick_stats_cache_key(instructor_id, 'I'))
    
    # Invalidate school dashboards
    if school_id:
        invalidate_school_dashboards(school_id)
    
    # Invalidate report caches
    if school_id and hasattr(invalidate_report_cache, '__call__'):
        invalidate_report_cache(school_id)


# ============================================
# ACHIEVEMENT SIGNAL HANDLERS
# ============================================

@receiver([post_save, post_delete], sender=Achievement)
def invalidate_dashboard_on_achievement_change(sender, instance, **kwargs):
    """
    Invalidate dashboard cache when achievement changes.
    This affects student dashboards and school dashboards.
    """
    student_id = instance.student_id
    
    # Invalidate student dashboard
    if student_id:
        student_profile = StudentProfile.objects.filter(id=student_id).first()
        if student_profile and student_profile.user:
            user_id = student_profile.user_id
            school_id = student_profile.school_id
            
            invalidate_dashboard_caches(user_id)
            
            # Invalidate school dashboards
            invalidate_school_dashboards(school_id)


# ============================================
# SCHOOL ANALYTICS SIGNAL HANDLERS
# ============================================

@receiver([post_save, post_delete], sender=SchoolAnalytics)
def invalidate_dashboard_on_analytics_change(sender, instance, **kwargs):
    """
    Invalidate dashboard cache when analytics data changes.
    This affects platform admin dashboards, school owner dashboards,
    and all dashboards that use analytics data.
    """
    school_id = instance.school_id
    
    # Invalidate school dashboards
    invalidate_school_dashboards(school_id)
    
    # Invalidate platform admin dashboards
    platform_admins = User.objects.filter(role='A', is_staff=True)
    for admin in platform_admins:
        invalidate_dashboard_caches(admin.id)
    
    # Invalidate school owner dashboard
    school = DrivingSchool.objects.filter(id=school_id).first()
    if school and school.owner:
        invalidate_dashboard_caches(school.owner_id)
        invalidate_dashboard_cache(school.owner_id, 'A', 'school_owner')
        invalidate_dashboard_cache(school.owner_id, 'A', 'overview')
        cache.delete(get_quick_stats_cache_key(school.owner_id, 'A'))
    
    # Invalidate report caches
    if hasattr(invalidate_report_cache, '__call__'):
        invalidate_report_cache(school_id)


# ============================================
# AUTOMATED MESSAGE SIGNAL HANDLERS
# ============================================

@receiver([post_save, post_delete], sender=AutomatedMessage)
def invalidate_dashboard_on_message_change(sender, instance, **kwargs):
    """
    Invalidate dashboard cache when automated message changes.
    This affects student dashboards (notifications) and platform admin dashboards.
    """
    student_id = instance.student_id
    
    # Invalidate student notifications cache
    if student_id:
        student_profile = StudentProfile.objects.filter(id=student_id).first()
        if student_profile and student_profile.user:
            user_id = student_profile.user_id
            # Clear notification caches
            for limit in [10, 20, 50]:
                cache.delete(get_notifications_cache_key(user_id, 'S', limit))
    
    # Invalidate platform admin dashboards (they see message stats)
    platform_admins = User.objects.filter(role='A', is_staff=True)
    for admin in platform_admins:
        invalidate_dashboard_cache(admin.id, 'A', 'platform_admin')
        invalidate_dashboard_cache(admin.id, 'A', 'overview')
        cache.delete(get_notifications_cache_key(admin.id, 'A', 10))


# ============================================
# VEHICLE SIGNAL HANDLERS
# ============================================

@receiver([post_save, post_delete], sender=Vehicle)
def invalidate_dashboard_on_vehicle_change(sender, instance, **kwargs):
    """
    Invalidate dashboard cache when vehicle changes.
    This affects school owner dashboards (vehicle management).
    """
    school_id = instance.school_id
    
    # Invalidate school dashboards
    invalidate_school_dashboards(school_id)
    
    # Invalidate school owner dashboard
    school = DrivingSchool.objects.filter(id=school_id).first()
    if school and school.owner:
        invalidate_dashboard_caches(school.owner_id)
        invalidate_dashboard_cache(school.owner_id, 'A', 'school_owner')
        invalidate_dashboard_cache(school.owner_id, 'A', 'overview')


# ============================================
# SIMPLIFIED SIGNAL HANDLER FOR ALL MODELS
# ============================================

def create_generic_dashboard_invalidation_signal(model_class):
    """
    Create a generic signal handler for any model that might affect dashboards.
    This is a simplified approach for models not covered by specific handlers.
    """
    @receiver([post_save, post_delete], sender=model_class)
    def invalidate_related_dashboards(sender, instance, **kwargs):
        """
        Generic handler to invalidate dashboards when any model changes.
        This is a fallback for models without specific handlers.
        """
        # Try to determine which dashboards might be affected
        # This is a simplified approach - you might want to customize per model
        
        # Check if instance has a school_id attribute
        if hasattr(instance, 'school_id') and instance.school_id:
            invalidate_school_dashboards(instance.school_id)
        
        # Check if instance has a user attribute
        elif hasattr(instance, 'user_id') and instance.user_id:
            invalidate_dashboard_caches(instance.user_id)
        
        # Check if instance has an owner attribute
        elif hasattr(instance, 'owner_id') and instance.owner_id:
            invalidate_dashboard_caches(instance.owner_id)
        
        # For other cases, invalidate all dashboards as a safety measure
        else:
            # Don't invalidate all - too heavy
            # Instead, log that we couldn't determine affected dashboards
            pass


# ============================================
# BULK OPERATION HANDLERS
# ============================================

def bulk_invalidate_dashboards_for_school(school_id):
    """
    Bulk invalidate all dashboards for a school.
    More efficient than individual invalidations for bulk operations.
    """
    if not school_id:
        return
    
    # Get all users in this school
    user_ids = StudentProfile.objects.filter(
        school_id=school_id
    ).values_list('user_id', flat=True).distinct()
    
    # Also get school owner
    school = DrivingSchool.objects.filter(id=school_id).first()
    if school and school.owner_id:
        user_ids = list(user_ids) + [school.owner_id]
    
    # Invalidate dashboards for all users
    for user_id in user_ids:
        invalidate_dashboard_caches(user_id)
    
    # Invalidate platform admin dashboards
    platform_admins = User.objects.filter(role='A', is_staff=True)
    for admin in platform_admins:
        invalidate_dashboard_caches(admin.id)


def bulk_invalidate_dashboards_for_users(user_ids):
    """
    Bulk invalidate dashboards for multiple users.
    """
    if not user_ids:
        return
    
    for user_id in user_ids:
        invalidate_dashboard_caches(user_id)


# ============================================
# CACHE MONITORING AND DEBUGGING
# ============================================

def get_dashboard_cache_status(user_id, role):
    """
    Check which dashboard caches are currently set for a user.
    Useful for debugging.
    """
    status = {
        'overview': cache.get(get_dashboard_cache_key(user_id, role, 'overview')) is not None,
        'quick_stats': cache.get(get_quick_stats_cache_key(user_id, role)) is not None,
        'notifications_10': cache.get(get_notifications_cache_key(user_id, role, 10)) is not None,
        'notifications_20': cache.get(get_notifications_cache_key(user_id, role, 20)) is not None,
        'notifications_50': cache.get(get_notifications_cache_key(user_id, role, 50)) is not None,
    }
    
    # Add role-specific dashboards
    if role == 'A':
        status['platform_admin'] = cache.get(get_dashboard_cache_key(user_id, role, 'platform_admin')) is not None
        status['school_owner'] = cache.get(get_dashboard_cache_key(user_id, role, 'school_owner')) is not None
    elif role == 'I':
        status['instructor'] = cache.get(get_dashboard_cache_key(user_id, role, 'instructor')) is not None
    elif role == 'S':
        status['student'] = cache.get(get_dashboard_cache_key(user_id, role, 'student')) is not None
    
    return status


def clear_all_dashboard_caches():
    """
    Clear all dashboard-related caches.
    Use during maintenance or when cache consistency is compromised.
    """
    # Clear using patterns if available
    patterns = [
        'dashboard_*',
        'dashboard_quick_stats_*',
        'dashboard_notifications_*',
    ]
    
    for pattern in patterns:
        try:
            cache.delete_pattern(pattern)
        except AttributeError:
            # Fallback for cache backends without delete_pattern
            pass
    
    # Also try to clear by iterating through known user patterns
    # This is less efficient but works for all cache backends
    from django.core.cache import caches
    default_cache = caches['default']
    
    # If using Redis or similar with scan, we could be more efficient
    # For now, we rely on pattern deletion or the invalidate_dashboard_caches approach


# ============================================
# SIGNAL CONNECTION HELPER
# ============================================

def connect_all_dashboard_signals():
    """
    Connect all dashboard signal handlers.
    Call this from your AppConfig.ready() method.
    """
    # All @receiver decorators have already connected the signals
    # This function is for clarity and future extensibility
    print("Dashboard signals connected")

# ============================================
# SUBSCRIPTION PLAN SIGNALS
# ============================================

@receiver(post_save, sender=SubscriptionPlan)
def subscription_plan_post_save(sender, instance, created, **kwargs):
    """Invalidate plan caches after save"""
    invalidate_plan_cache(instance.id)

@receiver(post_delete, sender=SubscriptionPlan)
def subscription_plan_post_delete(sender, instance, **kwargs):
    """Invalidate plan caches after delete"""
    invalidate_subscription_plan_caches()

# ============================================
# SCHOOL SUBSCRIPTION SIGNALS
# ============================================

@receiver(post_save, sender=SchoolSubscription)
def school_subscription_post_save(sender, instance, created, **kwargs):
    """Invalidate subscription caches after save"""
    invalidate_subscription_cache(instance.id)
    invalidate_school_subscription_caches(instance.school_id)

@receiver(post_delete, sender=SchoolSubscription)
def school_subscription_post_delete(sender, instance, **kwargs):
    """Invalidate subscription caches after delete"""
    invalidate_school_subscription_caches(instance.school_id)
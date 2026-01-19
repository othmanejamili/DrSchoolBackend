"""
Signal handlers for automatic cache invalidation.
"""

from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver
from django.core.cache import cache
from .models import (User, StudentProfile, DrivingSchool, Lesson, Schedule,
                      Feedback, Attendance, Vehicle, VehiclePicture, Achievement,
                      CommunicationTemplate, AutomatedMessage, SchoolAnalytics)
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
    invalidate_school_caches
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
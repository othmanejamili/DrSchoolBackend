"""
Signal handlers for automatic cache invalidation.
"""

from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.core.cache import cache
from .models import User, StudentProfile, DrivingSchool


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
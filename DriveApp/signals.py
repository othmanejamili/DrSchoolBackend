from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import User, StudentProfile
from .cache_service import CacheService

@receiver(post_save, sender=User)
def invalidate_user_cache_on_save(sender, instance, **kwargs):
    """Invalidate user cache when user is saved"""
    CacheService.invalidate_user_cache(instance.id)
    CacheService.invalidate_stats_cache()

@receiver(post_delete, sender=User)
def invalidate_user_cache_on_delete(sender, instance, **kwargs):
    """Invalidate user cache when user is deleted"""
    CacheService.invalidate_user_cache(instance.id)
    CacheService.invalidate_stats_cache()

@receiver(post_save, sender=StudentProfile)
def invalidate_profile_cache(sender, instance, **kwargs):
    """Invalidate cache when student profile is updated"""
    CacheService.invalidate_user_cache(instance.user_id)
    CacheService.invalidate_school_cache(instance.school_id)

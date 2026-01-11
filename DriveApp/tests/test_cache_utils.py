"""
Test cache utilities to ensure they work.
"""

from django.test import TestCase
from django.core.cache import cache
from DriveApp.cache_utils import (
    get_user_queryset_cache_key,
    get_schools_cache_key,
    get_school_stats_cache_key,
    invalidate_user_caches,
    invalidate_school_caches,
    get_schools_cache_key  # This should now exist
)


class CacheUtilsTestCase(TestCase):
    """Test cache utility functions"""
    
    def setUp(self):
        cache.clear()
    
    def test_cache_key_functions(self):
        """Test all cache key generation functions"""
        print("\n🔍 Testing cache key functions...")
        
        # Test user cache key
        user_key = get_user_queryset_cache_key(123, 'A')
        self.assertEqual(user_key, 'user_queryset_123_A')
        print(f"✅ User cache key: {user_key}")
        
        # Test schools cache key
        schools_key = get_schools_cache_key(123, 'A')
        self.assertEqual(schools_key, 'schools_queryset_123_A')
        print(f"✅ Schools cache key: {schools_key}")
        
        # Test school stats cache key
        stats_key = get_school_stats_cache_key(456)
        self.assertEqual(stats_key, 'school_456_stats')
        print(f"✅ School stats cache key: {stats_key}")
        
        # Test default school stats cache key
        default_stats_key = get_school_stats_cache_key()
        self.assertEqual(default_stats_key, 'school_stats_v1')
        print(f"✅ Default stats cache key: {default_stats_key}")
    
    def test_cache_invalidation(self):
        """Test cache invalidation functions don't crash"""
        print("\n🔍 Testing cache invalidation...")
        
        # Set up some test cache data
        cache.set('user_queryset_123_A', 'test_data', 60)
        cache.set('schools_queryset_123_A', 'test_data', 60)
        cache.set('school_456_stats', 'test_data', 60)
        cache.set('school_456_student_count', 'test_data', 60)
        
        # Test invalidation - should not crash
        try:
            invalidate_user_caches(123)
            print("✅ User cache invalidation works")
        except Exception as e:
            print(f"❌ User cache invalidation error: {e}")
        
        try:
            invalidate_school_caches(456)
            print("✅ School cache invalidation works")
        except Exception as e:
            print(f"❌ School cache invalidation error: {e}")
        
        # Verify caches were cleared
        self.assertIsNone(cache.get('user_queryset_123_A'))
        self.assertIsNone(cache.get('school_456_stats'))
        print("✅ Cache data was actually cleared")
    
    def test_cache_operations(self):
        """Test basic cache operations"""
        print("\n🔍 Testing basic cache operations...")
        
        # Set value
        cache.set('test_key', 'test_value', 10)
        
        # Get value
        value = cache.get('test_key')
        self.assertEqual(value, 'test_value')
        print("✅ Cache set/get works")
        
        # Delete value
        cache.delete('test_key')
        self.assertIsNone(cache.get('test_key'))
        print("✅ Cache delete works")
        
        # Test expiration
        import time
        cache.set('expire_key', 'expire_value', 1)
        time.sleep(2)
        self.assertIsNone(cache.get('expire_key'))
        print("✅ Cache expiration works")
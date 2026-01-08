import redis
from django.conf import settings

def test_redis_connection():
    """Test Redis connection and basic operations"""
    try:
        r = redis.Redis.from_url(settings.CACHES['default']['LOCATION'])
        
        # Test connection
        r.ping()
        print("✅ Redis connection successful!")
        
        # Test set/get
        r.set('test_key', 'test_value')
        value = r.get('test_key')
        print(f"✅ Redis set/get test: {value}")
        
        # Test delete
        r.delete('test_key')
        print("✅ Redis delete test successful")
        
        # Test pattern matching (if available)
        if hasattr(r, 'keys'):
            keys = r.keys('*')
            print(f"✅ Redis pattern matching: {len(keys)} keys found")
            
    except Exception as e:
        print(f"❌ Redis test failed: {e}")

if __name__ == "__main__":
    test_redis_connection()
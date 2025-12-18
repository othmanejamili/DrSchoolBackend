# emailTest.py
import ssl
import certifi

# Use certifi's certificate bundle
ssl._create_default_https_context = ssl.create_default_context
context = ssl.create_default_context(cafile=certifi.where())

from django.core.mail import send_mail

try:
    result = send_mail(
        'Test Real Email',
        'This should arrive in your inbox!',
        'othmanejamili19@gmail.com',
        ['jamiliothmane5@gmail.com','othmanejamili0@gmail.com'],
        fail_silently=False
    )
    print(f"Success! Email sent: {result}")
except Exception as e:
    print(f"Error: {e}")
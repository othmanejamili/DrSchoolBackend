# custom_email_backend.py
import ssl
from django.core.mail.backends.smtp import EmailBackend as SmtpBackend

class EmailBackend(SmtpBackend):
    def open(self):
        if self.connection:
            return False
        
        connection_params = {'timeout': self.timeout} if self.timeout else {}
        
        try:
            self.connection = self.connection_class(
                self.host, 
                self.port, 
                **connection_params
            )
            
            # The key fix: use unverified context for TLS
            if self.use_tls:
                context = ssl._create_unverified_context()
                self.connection.starttls(context=context)
            
            if self.username and self.password:
                self.connection.login(self.username, self.password)
            
            return True
        except Exception:
            if not self.fail_silently:
                raise
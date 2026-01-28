from django.apps import AppConfig


class DriveAppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'DriveApp'

    def ready(self):
        import DriveApp.signals
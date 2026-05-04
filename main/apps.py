from django.apps import AppConfig

class MainConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'main'

    def ready(self):
        import sys
        if 'migrate' in sys.argv or 'makemigrations' in sys.argv:
            return
        try:
            from .scheduler import start
            start()
        except Exception as e:
            print(f"[Scheduler] ishga tushmadi: {e}")
import django, os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()
from django.conf import settings
print("EMAIL_HOST:", settings.EMAIL_HOST)
print("PASSWORD:", repr(settings.EMAIL_HOST_PASSWORD))
print("BACKEND:", settings.EMAIL_BACKEND)
from django.core.mail import send_mail
try:
    send_mail("Prueba", "Hola", settings.DEFAULT_FROM_EMAIL, ["msb.tesla@gmail.com"], fail_silently=False)
    print("OK")
except Exception as e:
    print("ERROR:", type(e).__name__, str(e))
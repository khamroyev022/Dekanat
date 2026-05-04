from django.db import models
from django.conf import settings


ACTION_CHOICES = (
    ('CREATE', 'Yaratish'),
    ('UPDATE', 'Yangilash'),
    ('DELETE', "O'chirish"),
    ('READ',   "Ko'rish"),
    ('LOGIN',  'Kirish'),
    ('LOGOUT', 'Chiqish'),
)


class AuditLog(models.Model):
    user        = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='audit_logs'
    )
    action      = models.CharField(max_length=10, choices=ACTION_CHOICES)
    model_name  = models.CharField(max_length=100, blank=True)   # masalan: "Student"
    object_id   = models.CharField(max_length=50,  blank=True)   # o'zgartirilgan obyekt ID
    endpoint    = models.CharField(max_length=255, blank=True)   # /api/students/
    method      = models.CharField(max_length=10,  blank=True)   # GET, POST, PATCH, DELETE
    ip_address  = models.GenericIPAddressField(null=True, blank=True)
    user_agent  = models.CharField(max_length=255, blank=True)
    description = models.TextField(blank=True)                   # qo'shimcha ma'lumot
    status_code = models.IntegerField(null=True, blank=True)     # HTTP javob kodi
    created_at  = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"[{self.created_at:%Y-%m-%d %H:%M:%S}] {self.user} | {self.action} | {self.model_name}"

    class Meta:
        db_table         = 'audit_log'
        verbose_name     = 'Audit Log'
        verbose_name_plural = 'Audit Logs'
        ordering         = ['-created_at']
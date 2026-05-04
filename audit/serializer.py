from rest_framework import serializers
from  .models import *

class AuditLogSerializer(serializers.ModelSerializer):
    user = serializers.SerializerMethodField()

    class Meta:
        model  = AuditLog
        fields = [
            'id', 'user', 'action', 'model_name', 'object_id',
            'endpoint', 'method', 'ip_address',
            'description', 'status_code', 'created_at',
        ]

    def get_user(self, obj):
        if not obj.user:
            return None
        return {
            'id'      : obj.user.id,
            'username': obj.user.username,
            'role'    : getattr(obj.user.role, 'name', None),
        }


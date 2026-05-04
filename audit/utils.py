from .models import AuditLog
from .log_writer import write_log_to_txt

# HTTP method → ACTION xaritasi
METHOD_ACTION_MAP = {
    'GET'    : 'READ',
    'POST'   : 'CREATE',
    'PUT'    : 'UPDATE',
    'PATCH'  : 'UPDATE',
    'DELETE' : 'DELETE',
}


def get_client_ip(request):
    """Foydalanuvchi haqiqiy IP manzilini oladi (proxy orqali ham)."""
    x_forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded:
        return x_forwarded.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', '')


def log_action(
    request,
    action=None,
    model_name='',
    object_id='',
    description='',
    status_code=None,
):
    """
    View ichidan chaqiriladi.

    Misol:
        log_action(request, model_name='Student', object_id=student.id,
                   description="Student qo'shildi", status_code=201)
    """
    user       = request.user if request.user.is_authenticated else None
    method     = request.method.upper()
    resolved_action = action or METHOD_ACTION_MAP.get(method, 'READ')
    endpoint   = request.path
    ip         = get_client_ip(request)
    user_agent = request.META.get('HTTP_USER_AGENT', '')[:255]

    # 1) DB ga yoz
    AuditLog.objects.create(
        user        = user,
        action      = resolved_action,
        model_name  = model_name,
        object_id   = str(object_id),
        endpoint    = endpoint,
        method      = method,
        ip_address  = ip,
        user_agent  = user_agent,
        description = description,
        status_code = status_code,
    )

    write_log_to_txt(
        user        = user,
        action      = resolved_action,
        model_name  = model_name,
        object_id   = str(object_id),
        endpoint    = endpoint,
        method      = method,
        ip_address  = ip,
        user_agent  = user_agent,
        description = description,
        status_code = status_code,
    )
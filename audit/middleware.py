from .models import AuditLog
from .log_writer import write_log_to_txt
from .utils import get_client_ip, METHOD_ACTION_MAP

# Faqat shu endpointlar loglanadi (bo'sh qoldirilsa — hammasi loglanadi)
WATCHED_PATHS = [
    '/api/',
]

# Shu endpointlar loglanmaydi
IGNORED_PATHS = [
    '/admin/jsi18n/',
    '/favicon.ico',
    '/static/',
    '/media/',
]


class AuditMiddleware:
    """
    Barcha API so'rovlarini avtomatik ravishda audit.txt va
    AuditLog jadvaliga yozib boradi.

    settings.py ga qo'shing:
        MIDDLEWARE = [
            ...
            'audit.middleware.AuditMiddleware',
        ]
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        path = request.path

        # Ignore ro'yxatidan o'tkazish
        for ignored in IGNORED_PATHS:
            if path.startswith(ignored):
                return response

        # Faqat kuzatiladigan yo'llar
        if WATCHED_PATHS:
            watched = any(path.startswith(w) for w in WATCHED_PATHS)
            if not watched:
                return response

        user       = getattr(request, 'user', None)
        if user and not user.is_authenticated:
            user = None

        method     = request.method.upper()
        action     = METHOD_ACTION_MAP.get(method, 'READ')
        ip         = get_client_ip(request)
        user_agent = request.META.get('HTTP_USER_AGENT', '')[:255]
        status_code = getattr(response, 'status_code', None)

        description = f"HTTP {method} → {status_code}"

        # DB
        AuditLog.objects.create(
            user        = user,
            action      = action,
            model_name  = '',          # middleware model nomini bilmaydi
            object_id   = '',
            endpoint    = path,
            method      = method,
            ip_address  = ip,
            user_agent  = user_agent,
            description = description,
            status_code = status_code,
        )

        # TXT
        write_log_to_txt(
            user        = user,
            action      = action,
            model_name  = '',
            object_id   = '',
            endpoint    = path,
            method      = method,
            ip_address  = ip,
            user_agent  = user_agent,
            description = description,
            status_code = status_code,
        )

        return response
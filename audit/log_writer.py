import os
import threading
from datetime import datetime
from django.conf import settings

# Thread-safe yozish uchun lock
_lock = threading.Lock()

# Log fayl joylashuvi: BASE_DIR/logs/audit.txt
LOG_DIR  = os.path.join(getattr(settings, 'BASE_DIR', '.'), 'logs')
LOG_FILE = os.path.join(LOG_DIR, 'audit.txt')


def _ensure_log_dir():
    """Logs papkasi yo'q bo'lsa yaratadi."""
    os.makedirs(LOG_DIR, exist_ok=True)


def write_log_to_txt(
    user=None,
    action='',
    model_name='',
    object_id='',
    endpoint='',
    method='',
    ip_address='',
    user_agent='',
    description='',
    status_code=None,
):
    """
    Har bir amal haqida audit.txt fayliga bir qator yozadi.

    Format:
    [2025-01-15 14:32:01] | USER: admin (id=1) | ACTION: CREATE | MODEL: Student | OBJ_ID: 42 | ENDPOINT: /api/students/ | METHOD: POST | IP: 127.0.0.1 | STATUS: 201 | INFO: Student qo'shildi
    """
    _ensure_log_dir()

    now       = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    username  = getattr(user, 'username', 'anonymous')
    user_id   = getattr(user, 'id', '-')
    role_name = ''
    try:
        role_name = getattr(user.role, 'name', '') if user and user.role else ''
    except Exception:
        pass

    line = (
        f"[{now}] | "
        f"USER: {username} (id={user_id}, role={role_name}) | "
        f"ACTION: {action} | "
        f"MODEL: {model_name} | "
        f"OBJ_ID: {object_id or '-'} | "
        f"ENDPOINT: {endpoint} | "
        f"METHOD: {method} | "
        f"IP: {ip_address or '-'} | "
        f"STATUS: {status_code or '-'} | "
        f"INFO: {description}\n"
    )

    with _lock:
        with open(LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(line)
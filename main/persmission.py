from rest_framework.permissions import BasePermission

ROLE_ADMIN = 'admin'
ROLE_DEKAN = 'dekan'
ROLE_ZAM_DEKAN = 'zam dekan'

ROLE_TUTOR_ID = 2
ROLE_ZAM_DEKAN_ID = 4


class UserCRUDPermission(BasePermission):

    def has_permission(self, request, view):
        user = request.user
        if not user.is_authenticated:
            return False

        role_name = getattr(user.role, 'name', '').lower().strip()

        if user.is_superuser or role_name == ROLE_ADMIN:
            return True

        if role_name in [ROLE_DEKAN, ROLE_ZAM_DEKAN]:
            return True

        return False

    def has_object_permission(self, request, view, obj):
        user = request.user
        role_name = getattr(user.role, 'name', '').lower().strip()

        if user.is_superuser or role_name == ROLE_ADMIN:
            return True

        if role_name == ROLE_DEKAN:
            return (
                obj.faculty_id == user.faculty_id and
                obj.role_id in [ROLE_TUTOR_ID, ROLE_ZAM_DEKAN_ID]
            )

        # Zam dekan — faqat o'z fakultetidagi tutor
        if role_name == ROLE_ZAM_DEKAN:
            return (
                obj.faculty_id == user.faculty_id and
                obj.role_id == ROLE_TUTOR_ID
            )

        return False
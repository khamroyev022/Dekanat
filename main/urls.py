from django.urls import path
from .views import *
from rest_framework.routers import DefaultRouter
router = DefaultRouter()
router.register('users',CreateUserViewSet,basename='create_user'),
router.register('category',categoryInterstView)

urlpatterns = [
    path('import-students/', import_students, name='import_students'),
    path('update-students/',update_students),
    path('roles/',RoleApiview.as_view()),
    path('login/',login,name='login'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('faculties/', FacultyGEtApipview.as_view(), name='faculties'),
    path('faculty/directions/', DirectionGETApiview.as_view(), name='directions'),
    path('faculty/direction/groups/',GroupsGetApiView.as_view(), name='groups'),
    path('students/',StudentCRUD.as_view()),
    path('faculty/direction/group/student/details/',            StudentDetailCRUD.as_view()),
    path('faculty/direction/group/student/achievement/',       AchievementCRUD.as_view()),
    path('faculty/direction/group/student/health-info/',        HealthInfoCRUD.as_view()),
    path('faculty/direction/group/student/language-info/',      LanguageInfoCRUD.as_view()),
    path('faculty/direction/group/student/social-links/',       SocialLinkCRUD.as_view()),
    path('faculty/direction/group/student/reprimands/',         ReprimandCRUD.as_view()),
    path('faculty/direction/group/student/family-status/',      FamilySocialStatusCRUD.as_view()),
    path('faculty/direction/group/student/family-members/',     FamilyMemberCRUD.as_view()),
    path('faculty/direction/group/student/interests/',          InterestCRUD.as_view()),
    path('faculty/direction/group/student/social-registry/',    SocialRegistryCRUD.as_view()),
    path('faculty/direction/group/student/dormitory/',          DormitoryCRUD.as_view()),
    path('faculty/direction/group/student/gifted/',             GiftedCRUD.as_view()),
    path('faculty/direction/group/student/protection-order/',   ProtectionOrderCRUD.as_view()),
]+ router.urls



























































from django.urls import path
from .views import *
from rest_framework.routers import DefaultRouter
router = DefaultRouter()
router.register('users',CreateUserViewSet,basename='create_user'),

urlpatterns = [
    path('import-students/', import_students, name='import_students'),
    path('update-students/',update_students),
    path('login/',login,name='login'),
    path('groups/',TutorApiView.as_view()),
    path('students/', StudentGetApiView.as_view()),
    path('roles/', role_get),
    path('dean/faculty/', DekanFacultyView.as_view(), name='dekan-faculty'),
    path('dean/students/', DekanStudentView.as_view(), name='dekan-students'),
    path('directions/<int:id>/groups/', DirectionGroups.as_view()),
    path('faculty/', FacultyApiview.as_view()),
]+ router.urls


























































from django.urls import path
from .views import *
from rest_framework.routers import DefaultRouter
router = DefaultRouter()
router.register('create-user',CreateUserviewset,basename='create_user')

urlpatterns = [
    path('import-students/', import_students, name='import_students'),
    path('update-students/',update_students),
    path('login/',login,name='login'),
    path('tutor-groups/<int:id>/',TutorApiView.as_view()),
]+ router.urls
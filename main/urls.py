from django.urls import path
from .views import *

urlpatterns = [
    path('import-students/', import_students, name='import_students'),
    path('update-students/',update_students),
]
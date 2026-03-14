from django.urls import path,include
from .views import *

urlpatterns = [
    path('import/students/', import_students),
]
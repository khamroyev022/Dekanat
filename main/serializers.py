from rest_framework import serializers
from .models import *


class LoginSerializer(serializers.ModelSerializer):
    groups = serializers.PrimaryKeyRelatedField(queryset=Group.objects.all())
    class Meta:
        model = CustomUser
        fields = ('first_name','last_name','email','birthday','gender','image','address','nationality','passport_seria','phone_number','workplace','role','groups')

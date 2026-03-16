from rest_framework import serializers
from .models import *

class GroupLoginSerializer(serializers.ModelSerializer):
    class Meta:
        model = Group
        fields = ('id', 'name', 'education_code', 'education_language')

class LoginSerializer(serializers.ModelSerializer):
    tutor_groups = GroupLoginSerializer(many=True, read_only=True)
    role = serializers.StringRelatedField()

    class Meta:
        model = CustomUser
        fields = (
            'first_name',
            'last_name',
            'email',
            'birthday',
            'gender',
            'image',
            'address',
            'nationality',
            'passport_seria',
            'phone_number',
            'workplace',
            'role',
            'tutor_groups',
        )

class CreateUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = '__all__'

class TutorGroupSerializer(serializers.ModelSerializer):
    direction_name = serializers.CharField(source='direction.name', read_only=True)
    faculty_name = serializers.CharField(source='direction.faculty.name', read_only=True)

    class Meta:
        model = Group
        fields = (
            'id',
            'name',
            'education_code',
            'education_language',
            'direction',
            'direction_name',
            'faculty_name',
        )










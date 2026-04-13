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
            'id',
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
    group_ids = serializers.ListField(
        child=serializers.IntegerField(),
        write_only=True,
        required=False
    )
    role = serializers.PrimaryKeyRelatedField(
        queryset=Role.objects.all(),
        required=False,
        allow_null=True
    )
    role_name = serializers.StringRelatedField(source='role', read_only=True)
    groups = GroupLoginSerializer(source='tutor_groups', many=True, read_only=True)

    class Meta:
        model = CustomUser
        fields = '__all__'

    def create(self, validated_data):
        user_permissions = validated_data.pop('user_permissions', [])
        groups = validated_data.pop('groups', [])
        group_ids = validated_data.pop('group_ids', [])
        password = validated_data.pop('password', None)

        user = CustomUser(**validated_data)
        if password:
            user.set_password(password)
        user.save()

        if user_permissions:
            user.user_permissions.set(user_permissions)
        if groups:
            user.groups.set(groups)

        if group_ids and getattr(user.role, 'name', None) == 'tutor':
            Group.objects.filter(id__in=group_ids).update(tutor=user)

        return user

    def update(self, instance, validated_data):
        user_permissions = validated_data.pop('user_permissions', [])
        groups = validated_data.pop('groups', [])
        group_ids = validated_data.pop('group_ids', [])
        password = validated_data.pop('password', None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        if password:
            instance.set_password(password)
        instance.save()

        if user_permissions:
            instance.user_permissions.set(user_permissions)
        if groups:
            instance.groups.set(groups)

        if getattr(instance.role, 'name', None) == 'tutor':
            Group.objects.filter(tutor=instance).update(tutor=None)
            if group_ids:
                Group.objects.filter(id__in=group_ids).update(tutor=instance)
        return instance

class TutorGroupSerializer(serializers.ModelSerializer):
    faculty_name = serializers.CharField(source='direction.faculty.name', read_only=True)

    class Meta:
        model = Group
        fields = (
            'id',
            'name',
            'education_code',
            'education_language',
            'faculty_name',
        )

class DirectionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Direction
        fields = '__all__'

class GroupSerializer(serializers.ModelSerializer):
    direction = DirectionSerializer
    class Meta:
        model = Group
        fields = ('id', 'name','education_language')

class Studentserializer(serializers.ModelSerializer):
    class Meta:
        model = Student
        fields = ('first_name','last_name','third_name','birthday','gender','country','phone','image','course','hemis_id','email',)

class Roleserializer(serializers.ModelSerializer):
    class Meta:
        model = Role
        fields = ('id','name',)
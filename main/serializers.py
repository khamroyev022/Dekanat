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
    password = serializers.CharField(max_length=128, write_only=True, required=False)
    role = serializers.PrimaryKeyRelatedField(
        queryset=Role.objects.all(),
        required=False,
        allow_null=True
    )
    role_name = serializers.StringRelatedField(source='role', read_only=True)
    groups = GroupLoginSerializer(source='tutor_groups', many=True, read_only=True)

    class Meta:
        model = CustomUser
        fields = [
            'id',
            'username',
            'password',
            'first_name',
            'last_name',
            'third_name',
            'email',
            'birthday',
            'gender',
            'image',
            'address',
            'nationality',
            'passport_seria',
            'phone_number',
            'workplace',
            'faculty',
            'role',
            'role_name',
            'groups',
            'group_ids',
            'created_at',
        ]
        extra_kwargs = {
            'password': {'write_only': True},
            'created_at': {'read_only': True},
        }

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data.pop('password', None)
        return data

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

        role_name = getattr(user.role, 'name', '') or ''
        if group_ids and role_name.lower().strip() == 'tyutor':
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

class StudentSerializer(serializers.ModelSerializer):
    group_name = serializers.CharField(source='group.name', read_only=True)  # ← to'g'rilandi

    p_country = serializers.CharField(max_length=50, required=False, allow_blank=True)
    p_region = serializers.CharField(max_length=50, required=False, allow_blank=True)
    p_district = serializers.CharField(max_length=50, required=False, allow_blank=True)
    t_country = serializers.CharField(max_length=50, required=False, allow_blank=True)
    t_region = serializers.CharField(max_length=50, required=False, allow_blank=True)
    t_district = serializers.CharField(max_length=50, required=False, allow_blank=True)
    t_latitude = serializers.CharField(max_length=30, required=False, allow_blank=True)
    t_longitude = serializers.CharField(max_length=30, required=False, allow_blank=True)
    is_orphanage_student = serializers.BooleanField(required=False, default=False)
    is_military_family = serializers.BooleanField(required=False, default=False)
    education_type = serializers.CharField(max_length=30, required=False, default='nomalum')
    is_pregnant = serializers.BooleanField(required=False, default=False)
    behavior_issues = serializers.BooleanField(required=False, default=False)
    is_adult = serializers.BooleanField(required=False, default=False)

    class Meta:
        model = Student
        fields = [
            'id',
            'first_name',
            'last_name',
            'third_name',
            'birthday',
            'gender',
            'country',
            'image',
            'image_hemis',
            'avg_gpa',
            'course',
            'hemis_id',
            'email',
            'phone',
            'group',  # ← POST da id yuborish uchun
            'group_name',  # ← GET da nom ko'rish uchun
            'p_country',
            'p_region',
            'p_district',
            't_country',
            't_region',
            't_district',
            't_latitude',
            't_longitude',
            'is_orphanage_student',
            'is_military_family',
            'education_type',
            'is_pregnant',
            'behavior_issues',
            'is_adult',
        ]
        extra_kwargs = {
            'group': {'write_only': True},
        }

    def create(self, validated_data):
        detail_fields = [
            'p_country', 'p_region', 'p_district',
            't_country', 't_region', 't_district',
            't_latitude', 't_longitude',
            'is_orphanage_student', 'is_military_family',
            'education_type', 'is_pregnant',
            'behavior_issues', 'is_adult',
        ]
        detail_data = {f: validated_data.pop(f, None) for f in detail_fields}
        student = Student.objects.create(**validated_data)
        StudentDetail.objects.create(student=student, **detail_data)
        return student

    def update(self, instance, validated_data):
        detail_fields = [
            'p_country', 'p_region', 'p_district',
            't_country', 't_region', 't_district',
            't_latitude', 't_longitude',
            'is_orphanage_student', 'is_military_family',
            'education_type', 'is_pregnant',
            'behavior_issues', 'is_adult',
        ]
        detail_data = {f: validated_data.pop(f, None) for f in detail_fields}

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        detail = instance.details.first()
        if detail:
            for attr, value in detail_data.items():
                if value is not None:
                    setattr(detail, attr, value)
            detail.save()
        else:
            StudentDetail.objects.create(student=instance, **detail_data)

        return instance

    def to_representation(self, instance):
        data = super().to_representation(instance)
        detail = instance.details.first()
        if detail:
            data['p_country'] = detail.p_country
            data['p_region'] = detail.p_region
            data['p_district'] = detail.p_district
            data['t_country'] = detail.t_country
            data['t_region'] = detail.t_region
            data['t_district'] = detail.t_district
            data['t_latitude'] = detail.t_latitude
            data['t_longitude'] = detail.t_longitude
            data['is_orphanage_student'] = detail.is_orphanage_student
            data['is_military_family'] = detail.is_military_family
            data['education_type'] = detail.education_type
            data['is_pregnant'] = detail.is_pregnant
            data['behavior_issues'] = detail.behavior_issues
            data['is_adult'] = detail.is_adult
        return data

class Roleserializer(serializers.ModelSerializer):
    class Meta:
        model = Role
        fields = ('id','name',)

class Facultyserializer(serializers.ModelSerializer):
    class Meta:
        model = Faculty
        fields = ['id','name','code','created_at']

class Directionserializer(serializers.ModelSerializer):
    class Meta:
        model = Direction
        fields = ['id','name','code']

class Groupserializer(serializers.ModelSerializer):
    class Meta:
        model = Group
        fields = ['id','name','education_code','education_language']

class StudentSerializer1(serializers.ModelSerializer):
    group = Groupserializer()
    class Meta:
        model = Student
        fields = [
            'id',
            'first_name',
            'last_name',
            'third_name',
            'birthday',
            'gender',
            'country',
            'image',
            'image_hemis',
            'avg_gpa',
            'course',
            'hemis_id',
            'email',
            'phone',
            'group'
        ]





class StudentDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = StudentDetail
        fields = [
            'id', 'student',
            'p_country', 'p_region', 'p_district',
            't_country', 't_region', 't_district',
            't_latitude', 't_longitude',
            'is_orphanage_student', 'is_military_family',
            'education_type', 'is_pregnant',
            'behavior_issues', 'is_adult',
            'created_at',
        ]


class AchievementSerializer(serializers.ModelSerializer):
    class Meta:
        model = Achievement
        fields = [
            'id', 'student',
            'name', 'date', 'file',
            'created_at',
        ]


class HealthInfoSerializer(serializers.ModelSerializer):
    class Meta:
        model = HealthInfo
        fields = [
            'id', 'student',
            'name', 'disability', 'health_status',
            'disability_status', 'file', 'date',
            'created_at',
        ]


class LanguageInfoSerializer(serializers.ModelSerializer):
    class Meta:
        model = LanguageInfo
        fields = [
            'id', 'student',
            'name', 'level', 'file', 'status',
            'created_at',
        ]


class SocialLinkSerializer(serializers.ModelSerializer):
    class Meta:
        model = SocialLink
        fields = [
            'id', 'student',
            'name', 'urls', 'status',
            'created_at',
        ]


class ReprimandSerializer(serializers.ModelSerializer):
    class Meta:
        model = Reprimand
        fields = [
            'id', 'student',
            'date', 'title', 'file',
            'created_at',
        ]


class FamilySocialStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = FamilySocialStatus
        fields = [
            'id', 'student',
            'marital_status', 'is_orphan',
            'guardian_person', 'guardian_full_name',
            'guardian_phone', 'guardian_description',
            'is_crime_prone', 'official_employment',
            'created_at',
        ]


class FamilyMemberSerializer(serializers.ModelSerializer):
    class Meta:
        model = FamilyMember
        fields = [
            'id', 'student',
            'first_name', 'last_name', 'third_name',
            'address', 'work_place', 'unofficial_employment',
            'created_at',
        ]


class CategoryInterestSerializer(serializers.ModelSerializer):
    class Meta:
        model = CategoryInterest
        fields = [
            'id', 'name', 'created_at',
        ]


class InterestSerializer(serializers.ModelSerializer):
    class Meta:
        model = Interest
        fields = [
            'id', 'student', 'category',
            'name', 'created_at',
        ]


class SocialRegistrySerializer(serializers.ModelSerializer):
    class Meta:
        model = SocialRegistry
        fields = [
            'id', 'student',
            'status', 'file',
            'created_at',
        ]


class DormitorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Dormitory
        fields = [
            'id', 'student',
            'status', 'dormitory_name', 'building_name',
            'building_phone', 'floor', 'residence_type',
            'address', 'created_at',
        ]


class GiftedSerializer(serializers.ModelSerializer):
    class Meta:
        model = Gifted
        fields = [
            'id', 'student',
            'name', 'status', 'file',
            'created_at',
        ]


class ProtectionOrderSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProtectionOrder
        fields = [
            'id', 'student',
            'status', 'file',
            'created_at',
        ]


class StudentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Student
        fields = [
            'id', 'group',
            'first_name', 'last_name', 'third_name',
            'birthday', 'gender', 'country',
            'image', 'image_hemis',
            'avg_gpa', 'course',
            'hemis_id', 'email', 'phone',
        ]


class StudentFullSerializer(serializers.ModelSerializer):
    details              = StudentDetailSerializer(many=True, read_only=True)
    achievements         = AchievementSerializer(many=True, read_only=True)
    health_info          = HealthInfoSerializer(many=True, read_only=True)
    language_info        = LanguageInfoSerializer(many=True, read_only=True)
    social_links         = SocialLinkSerializer(many=True, read_only=True)
    reprimands           = ReprimandSerializer(many=True, read_only=True)
    family_social_status = FamilySocialStatusSerializer(many=True, read_only=True)
    family_members       = FamilyMemberSerializer(many=True, read_only=True)
    interests            = InterestSerializer(many=True, read_only=True)
    social_registries    = SocialRegistrySerializer(many=True, read_only=True)
    dormitories          = DormitorySerializer(many=True, read_only=True)
    gifteds              = GiftedSerializer(many=True, read_only=True)
    protection_orders    = ProtectionOrderSerializer(many=True, read_only=True)

    class Meta:
        model = Student
        fields = [
            'id', 'group',
            'first_name', 'last_name', 'third_name',
            'birthday', 'gender', 'country',
            'image', 'image_hemis',
            'avg_gpa', 'course',
            'hemis_id', 'email', 'phone',
            # related
            'details', 'achievements', 'health_info',
            'language_info', 'social_links', 'reprimands',
            'family_social_status', 'family_members',
            'interests', 'social_registries', 'dormitories',
            'gifteds', 'protection_orders',
        ]























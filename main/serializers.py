from pyexpat import model
from rest_framework import serializers
from .models import *
from .models import (
    Achievement, HealthInfo, LanguageInfo, SocialLink,
    Reprimand, FamilySocialStatus, FamilyMember,
    CategoryInterest, Interest, SocialRegistry,
    Dormitory, Gifted, ProtectionOrder
)
from django.db.models import Exists, OuterRef, Count


class FileUrlMixin:

    def get_file_url(self, obj, field_name='file'):
        file = getattr(obj, field_name, None)
        if file:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(file.url)
            return file.url
        return None


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
            'id', 'first_name', 'last_name', 'email',
            'birthday', 'gender', 'image', 'address',
            'nationality', 'passport_seria', 'phone_number',
            'workplace', 'role', 'tutor_groups',
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
            'id', 'username', 'password',
            'first_name', 'last_name', 'third_name',
            'email', 'birthday', 'gender', 'image',
            'address', 'nationality', 'passport_seria',
            'phone_number', 'workplace', 'faculty',
            'role', 'role_name', 'groups', 'group_ids',
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
        fields = ('id', 'name', 'education_code', 'education_language', 'faculty_name')

class DirectionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Direction
        fields = '__all__'

class Tutorserializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = ('first_name','last_name',)
class StudentReprimandSerializer(serializers.ModelSerializer):
    reprimand_count = serializers.IntegerField()

    class Meta:
        model  = Student
        fields = ('id', 'first_name', 'last_name', 'third_name',
                  'hemis_id', 'course', 'reprimand_count')


class GroupSerializer(serializers.ModelSerializer):
    tutor           = Tutorserializer(read_only=True)
    filled_stats    = serializers.SerializerMethodField()
    reprimand_stats = serializers.SerializerMethodField()

    class Meta:
        model  = Group
        fields = (
            'id', 'name', 'education_language',
            'tutor', 'filled_stats', 'reprimand_stats'
        )

    def get_reprimand_stats(self, group):
        total_reprimands       = Reprimand.objects.filter(student__group=group).count()
        students_with_reprimand = Student.objects.filter(
            group=group,
            reprimands__isnull=False
        ).distinct().count()

        return {
            'total_reprimands'       : total_reprimands,
            'students_with_reprimand': students_with_reprimand,
        }

    def get_filled_stats(self, group):
        students = Student.objects.filter(group=group).annotate(
            has_detail          = Exists(StudentDetail.objects.filter(student=OuterRef('pk'))),
            has_health          = Exists(HealthInfo.objects.filter(student=OuterRef('pk'))),
            has_family          = Exists(FamilySocialStatus.objects.filter(student=OuterRef('pk'))),
            has_dormitory       = Exists(Dormitory.objects.filter(student=OuterRef('pk'))),
            has_language        = Exists(LanguageInfo.objects.filter(student=OuterRef('pk'))),
            has_achievement     = Exists(Achievement.objects.filter(student=OuterRef('pk'))),
            has_reprimand       = Exists(Reprimand.objects.filter(student=OuterRef('pk'))),
            has_family_member   = Exists(FamilyMember.objects.filter(student=OuterRef('pk'))),
            has_interest        = Exists(Interest.objects.filter(student=OuterRef('pk'))),
            has_social_registry = Exists(SocialRegistry.objects.filter(student=OuterRef('pk'))),
            has_gifted          = Exists(Gifted.objects.filter(student=OuterRef('pk'))),
            has_protection      = Exists(ProtectionOrder.objects.filter(student=OuterRef('pk'))),
            has_social_link     = Exists(SocialLink.objects.filter(student=OuterRef('pk'))),
        )

        total = students.count()
        if total == 0:
            return {
                'total_students'        : 0,
                'toliq_toldirilgan_soni': 0,
                'toliq_toldirilgan_foiz': 0.0,
                'sections'              : {}
            }

        def foiz(n):
            return round(n / total * 100, 1)

        toliq_soni = students.filter(
            has_detail=True, has_health=True,    has_family=True,
            has_dormitory=True, has_language=True, has_achievement=True,
            has_reprimand=True, has_family_member=True, has_interest=True,
        ).count()

        return {
            'total_students'        : total,
            'toliq_toldirilgan_soni': toliq_soni,
            'toliq_toldirilgan_foiz': foiz(toliq_soni),
            'sections': {
                'asosiy_malumot'    : foiz(students.filter(has_detail=True).count()),
                'soglik'            : foiz(students.filter(has_health=True).count()),
                'oilaviy_holat'     : foiz(students.filter(has_family=True).count()),
                'turar_joy'         : foiz(students.filter(has_dormitory=True).count()),
                'til_bilimi'        : foiz(students.filter(has_language=True).count()),
                'yutuqlar'          : foiz(students.filter(has_achievement=True).count()),
                'hayfnoma'          : foiz(students.filter(has_reprimand=True).count()),
                'oila_azolari'      : foiz(students.filter(has_family_member=True).count()),
                'qiziqishlar'       : foiz(students.filter(has_interest=True).count()),
                'ijtimoiy_reyestr'  : foiz(students.filter(has_social_registry=True).count()),
                'iqtidorli'         : foiz(students.filter(has_gifted=True).count()),
                'himoya_orderi'     : foiz(students.filter(has_protection=True).count()),
                'ijtimoiy_havolalar': foiz(students.filter(has_social_link=True).count()),
            }
        }

class Roleserializer(serializers.ModelSerializer):
    class Meta:
        model = Role
        fields = ['id', 'name']

class Facultyserializer(serializers.ModelSerializer):
    class Meta:
        model = Faculty
        fields = ['id', 'name', 'code', 'created_at']

class Directionserializer(serializers.ModelSerializer):
    class Meta:
        model = Direction
        fields = ['id', 'name', 'code']

class Groupserializer(serializers.ModelSerializer):
    class Meta:
        model = Group
        fields = ['id', 'name', 'education_code', 'education_language']



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
            'created_at','passport_pdf','is_amount','is_amount_file',
            'pnfl',

        ]



class StudentSerializer(serializers.ModelSerializer):
    group_name = serializers.CharField(source='group.name', read_only=True)
    filled = serializers.SerializerMethodField()
    reprimand_count = serializers.SerializerMethodField()
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
            'id', 'first_name', 'last_name', 'third_name',
            'birthday', 'gender', 'country',
            'image', 'image_hemis',
            'avg_gpa', 'course', 'hemis_id',
            'email', 'phone',
            'group', 'group_name',
            'filled',
            'p_country', 'p_region', 'p_district',
            't_country', 't_region', 't_district',
            't_latitude', 't_longitude',
            'is_orphanage_student', 'is_military_family',
            'education_type', 'is_pregnant',
            'behavior_issues', 'is_adult','reprimand_count'
        ]
        extra_kwargs = {
            'group': {'write_only': True},
        }

    def get_reprimand_count(self, student):
            return student.reprimands.count()

    def get_filled(self, obj):
        from .utils import calculate_student_completion
        return calculate_student_completion(obj)

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


class AchievementSerializer(FileUrlMixin, serializers.ModelSerializer):
    class Meta:
        model = Achievement
        fields = ['id', 'student', 'name', 'date', 'file', 'created_at']

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        rep['file'] = self.get_file_url(instance)
        return rep


class HealthInfoSerializer(FileUrlMixin, serializers.ModelSerializer):
    class Meta:
        model = HealthInfo
        fields = [
            'id', 'student', 'name', 'disability',
            'health_status', 'disability_status',
            'file', 'date', 'created_at',
        ]

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        rep['file'] = self.get_file_url(instance)
        return rep


class LanguageInfoSerializer(FileUrlMixin, serializers.ModelSerializer):
    class Meta:
        model = LanguageInfo
        fields = ['id', 'student', 'name', 'level', 'file', 'status', 'created_at']

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        rep['file'] = self.get_file_url(instance)
        return rep


class SocialLinkSerializer(serializers.ModelSerializer):
    class Meta:
        model = SocialLink
        fields = ['id', 'student', 'name', 'urls', 'status', 'created_at']


class ReprimandSerializer(FileUrlMixin, serializers.ModelSerializer):
    class Meta:
        model = Reprimand
        fields = ['id', 'date', 'title', 'file', 'status', 'created_at']

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        rep['file'] = self.get_file_url(instance)
        return rep


class FamilySocialStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = FamilySocialStatus
        fields = [
            'id', 'student', 'marital_status', 'is_orphan',
            'guardian_person', 'guardian_full_name',
            'guardian_phone', 'guardian_description',
            'is_crime_prone', 'official_employment',
            'created_at',
        ]


class FamilyMemberSerializer(serializers.ModelSerializer):
    class Meta:
        model = FamilyMember
        fields = [
            'id', 'student', 'first_name', 'last_name',
            'third_name', 'address', 'work_place',
            'unofficial_employment', 'created_at',
        ]


class CategoryInterestSerializer(serializers.ModelSerializer):
    class Meta:
        model = CategoryInterest
        fields = ['id', 'name', 'created_at']


class InterestSerializer(serializers.ModelSerializer):
    class Meta:
        model = Interest
        fields = ['id', 'student', 'category', 'name', 'created_at']


class SocialRegistrySerializer(FileUrlMixin, serializers.ModelSerializer):
    class Meta:
        model = SocialRegistry
        fields = ['id', 'student', 'status', 'file', 'created_at']

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        rep['file'] = self.get_file_url(instance)
        return rep


class DormitorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Dormitory
        fields = (
            'id', 'status', 'dormitory_name', 'building',
            'floor', 'room', 'residence_type',
            'address', 'created_at'
        )
        read_only_fields = ['student', 'created_at']

    def validate(self, data):
        status = data.get('status', getattr(self.instance, 'status', None))

        if status is None:
            raise serializers.ValidationError("status majburiy")

        if status:
            errors = {}
            if not data.get('dormitory_name'):
                errors['dormitory_name'] = "TTJ nomi majburiy"
            if not data.get('building'):
                errors['building'] = "Bino majburiy"
            if not data.get('floor'):
                errors['floor'] = "Qavat majburiy"
            if not data.get('room'):
                errors['room'] = "Xona majburiy"
            if errors:
                raise serializers.ValidationError(errors)
        else:
            errors = {}
            if not data.get('residence_type'):
                errors['residence_type'] = "Turar joy turi majburiy"
            if not data.get('address'):
                errors['address'] = "Manzil majburiy"
            if errors:
                raise serializers.ValidationError(errors)

        return data


class GiftedSerializer(FileUrlMixin, serializers.ModelSerializer):
    class Meta:
        model = Gifted
        fields = ['id', 'student', 'name', 'status', 'file', 'created_at']

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        rep['file'] = self.get_file_url(instance)
        return rep


class ProtectionOrderSerializer(FileUrlMixin, serializers.ModelSerializer):
    class Meta:
        model = ProtectionOrder
        fields = ['id', 'student', 'status', 'file', 'created_at']

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        rep['file'] = self.get_file_url(instance)
        return rep


# ─────────────────────────────────────────────
# STUDENT FULL SERIALIZER
# ─────────────────────────────────────────────
PREFETCH_FIELDS = [
    'achievements', 'health_info', 'language_info',
    'social_links', 'reprimands', 'family_social_status',
    'family_members', 'interests', 'social_registries',
    'dormitories', 'gifteds', 'protection_orders',
]


class StudentFullSerializer(serializers.ModelSerializer):
    filled               = serializers.SerializerMethodField()
    details              = StudentDetailSerializer(many=True, read_only=True)
    achievements         = AchievementSerializer(many=True, read_only=True)
    health_info          = HealthInfoSerializer(read_only=True)
    language_info        = LanguageInfoSerializer(many=True, read_only=True)
    social_links         = SocialLinkSerializer(many=True, read_only=True)
    reprimands           = ReprimandSerializer(many=True, read_only=True)
    family_social_status = FamilySocialStatusSerializer(read_only=True)
    family_members       = FamilyMemberSerializer(many=True, read_only=True)
    interests            = InterestSerializer(many=True, read_only=True)
    social_registries    = SocialRegistrySerializer(many=True, read_only=True)
    dormitories          = DormitorySerializer( read_only=True)
    gifteds              = GiftedSerializer(many=True, read_only=True)
    protection_orders    = ProtectionOrderSerializer(many=True, read_only=True)
    class Meta:
        model = Student
        fields = [
            'id', 'group',
            'first_name', 'last_name', 'third_name',
            'birthday', 'gender', 'country',
            'image', 'image_hemis',
            'avg_gpa', 'course', 'hemis_id',
            'email', 'phone',
            'filled',
            'details', 'achievements', 'health_info',
            'language_info', 'social_links', 'reprimands',
            'family_social_status', 'family_members',
            'interests', 'social_registries', 'dormitories',
            'gifteds', 'protection_orders',
        ]

    def get_filled(self, obj):
        from .utils import calculate_student_completion
        return calculate_student_completion(obj)

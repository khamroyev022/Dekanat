from django.db import models
from django.contrib.auth.models import AbstractUser
from django.db.models.signals import post_delete, pre_save
from django.dispatch import receiver
import os

GENDER_CHOICES = (
    ('male', 'Erkak'),
    ('female', 'Ayol'),
    ('other', 'Boshqa'),
)

ROLE_CHOICES = (
    ('admin', 'Admin'),
    ('tutor', 'Tutor'),
    ('dekan', 'Dekan'),
    ('zam_dekan', 'Zam dekan'),
)

EDUCATION_TYPE_CHOICES = (
    ('grant', 'Grant'),
    ('kontrakt', 'Kontrakt'),
    ('nomalum', 'Nomalum'),
)

DISABILITY_GROUP = (
    ('1', '1-guruh'),
    ('2', '2-guruh'),
    ('3', '3-guruh'),
)

LANGUAGE_LEVEL = (
    ('A1', 'A1'),
    ('A2', 'A2'),
    ('B1', 'B1'),
    ('B2', 'B2'),
    ('C1', 'C1'),
    ('C2', 'C2'),
)

MARITAL_STATUS = (
    ('single', "Bo'ydoq"),
    ('married', 'Turmush qurgan'),
    ('divorced', 'Ajrashgan'),
    ('widowed', 'Beva'),
)

ORPHAN_STATUS = (
    ('none', "Yo'q"),
    ('orphan', "Yetim"),
    ('full_orphan', "Chin yetim"),
)


class Role(models.Model):
    name = models.CharField(max_length=120, choices=ROLE_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    class Meta:
        db_table = 'role'
        verbose_name = 'Role'
        verbose_name_plural = 'Roles'
        ordering = ['name']


class CustomUser(AbstractUser):
    first_name = models.CharField(max_length=30)
    last_name = models.CharField(max_length=30)
    third_name = models.CharField(max_length=30)
    birthday = models.DateField()
    gender = models.CharField(max_length=30, choices=GENDER_CHOICES)
    image = models.ImageField(upload_to='users/images/', null=True, blank=True)
    address = models.CharField(max_length=255)
    nationality = models.CharField(max_length=50)
    passport_seria = models.CharField(max_length=30)
    phone_number = models.CharField(max_length=20)
    workplace = models.CharField(max_length=100)
    role = models.ForeignKey(Role, on_delete=models.PROTECT, related_name='users')
    created_at = models.DateTimeField(auto_now_add=True)

    groups = models.ManyToManyField(
        'auth.Group',
        related_name='custom_users',
        blank=True
    )
    user_permissions = models.ManyToManyField(
        'auth.Permission',
        related_name='custom_users',
        blank=True
    )

    def __str__(self):
        return self.username

    class Meta:
        db_table = 'user'
        verbose_name = 'User'
        verbose_name_plural = 'Users'
        ordering = ['first_name', 'last_name']


class Faculty(models.Model):
    name = models.CharField(max_length=150)
    code = models.CharField(max_length=30)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    class Meta:
        db_table = 'faculty'
        verbose_name = 'Faculty'
        verbose_name_plural = 'Faculties'
        ordering = ['name']


class Direction(models.Model):
    name = models.CharField(max_length=150)
    code = models.CharField(max_length=10, unique=True)
    faculty = models.ForeignKey(Faculty, on_delete=models.PROTECT, related_name='directions')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    class Meta:
        db_table = 'direction'
        verbose_name = 'Direction'
        verbose_name_plural = 'Directions'
        ordering = ['name']


class Group(models.Model):
    name = models.CharField(max_length=50, unique=True)
    education_code = models.CharField(max_length=20)
    education_language = models.CharField(max_length=30)
    user = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, related_name='tutor_groups')
    direction = models.ForeignKey(Direction, on_delete=models.PROTECT, related_name='groups')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    class Meta:
        db_table = 'group'
        verbose_name = 'Group'
        verbose_name_plural = 'Groups'
        ordering = ['name']


class Student(models.Model):
    first_name = models.CharField(max_length=50,null=True,blank=True)
    last_name = models.CharField(max_length=50,null=True,blank=True)
    third_name = models.CharField(max_length=50,null=True,blank=True)
    birthday = models.DateField(null=True)
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES)
    country = models.CharField(max_length=50,null=True,blank=True)
    image_full = models.ImageField(upload_to='student/images/full/', null=True, blank=True)
    image_none = models.ImageField(upload_to='student/images/', null=True, blank=True)
    image_full_none = models.ImageField(upload_to='student/images/', null=True, blank=True)
    avg_gpa = models.DecimalField(max_digits=4, decimal_places=2, null=True)
    course = models.CharField(max_length=15)
    hemis_id = models.CharField(max_length=13)
    email = models.EmailField(null=True, blank=True)
    phone = models.CharField(max_length=20,null=True,blank=True)
    group = models.ForeignKey(Group, on_delete=models.PROTECT, related_name='students')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.first_name} {self.last_name}"

    class Meta:
        db_table = 'student'
        verbose_name = 'Student'
        verbose_name_plural = 'Students'
        ordering = ['first_name', 'last_name']


class StudentDetail(models.Model):
    p_country = models.CharField(max_length=50,null=True,blank=True)
    p_region = models.CharField(max_length=50,null=True,blank=True)
    p_district = models.CharField(max_length=50,null=True,blank=True)
    t_country = models.CharField(max_length=50,null=True,blank=True)
    t_region = models.CharField(max_length=50,null=True,blank=True)
    t_district = models.CharField(max_length=50,null=True,blank=True)
    t_latitude = models.CharField(max_length=30,null=True,blank=True)
    t_longitude = models.CharField(max_length=30,null=True,blank=True)
    is_orphanage_student = models.BooleanField(default=False)
    is_military_family = models.BooleanField(default=False)
    education_type = models.CharField(max_length=30, choices=EDUCATION_TYPE_CHOICES, default='nomalum')
    is_pregnant = models.BooleanField(default=False)
    behavior_issues = models.BooleanField(default=False)
    is_adult = models.BooleanField(default=False)
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='details')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.student} - {self.p_country}"

    class Meta:
        db_table = 'student_detail'
        verbose_name = 'Student Detail'
        verbose_name_plural = 'Student Details'
        ordering = ['p_country', 'p_region', 'p_district']


class Achievement(models.Model):
    name = models.CharField(max_length=200,null=True,blank=True)
    date = models.DateField(null=True,blank=True)
    file = models.FileField(upload_to='achievements/',null=True,blank=True)
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='achievements')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    class Meta:
        db_table = 'achievement'
        verbose_name = 'Achievement'
        verbose_name_plural = 'Achievements'
        ordering = ['name']


class HealthInfo(models.Model):
    name = models.CharField(max_length=100,null=True,blank=True)
    disability = models.BooleanField(default=False)
    health_status = models.BooleanField(default=True)
    disability_status = models.CharField(max_length=10, choices=DISABILITY_GROUP, null=True, blank=True)
    file = models.FileField(upload_to='health_info/',null=True,blank=True)
    date = models.DateField(null=True,blank=True)
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='health_info', null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    class Meta:
        db_table = 'health_info'
        verbose_name = 'Health Info'
        verbose_name_plural = 'Health Infos'
        ordering = ['name']


class LanguageInfo(models.Model):
    name = models.CharField(max_length=100,null=True, blank=True)
    level = models.CharField(max_length=10, choices=LANGUAGE_LEVEL,null=True, blank=True)
    file = models.FileField(upload_to='language_info/',null=True, blank=True)
    status = models.BooleanField(default=False)
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='language_info')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    class Meta:
        db_table = 'language_info'
        verbose_name = 'Language Info'
        verbose_name_plural = 'Language Infos'
        ordering = ['name']


class SocialLink(models.Model):
    name = models.CharField(max_length=60,null=True, blank=True)
    urls = models.URLField(null=True, blank=True)
    status = models.BooleanField(default=False)
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='social_links')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    class Meta:
        db_table = 'social_link'
        verbose_name = 'Social Link'
        verbose_name_plural = 'Social Links'
        ordering = ['name']


class Reprimand(models.Model):
    date = models.DateField()
    title = models.CharField(max_length=200,null=True, blank=True)
    file = models.FileField(upload_to='reprimand/',null=True,blank=True)
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='reprimands')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title

    class Meta:
        db_table = 'reprimand'
        verbose_name = 'Reprimand'
        verbose_name_plural = 'Reprimands'
        ordering = ['date']


class FamilySocialStatus(models.Model):
    marital_status = models.CharField(max_length=15, choices=MARITAL_STATUS)
    is_orphan = models.CharField(max_length=15, choices=ORPHAN_STATUS, default='none')
    guardian_person = models.CharField(max_length=150, null=True, blank=True)
    guardian_full_name = models.CharField(max_length=150, null=True, blank=True)
    guardian_phone = models.CharField(max_length=20, null=True, blank=True)
    guardian_description = models.CharField(max_length=255, null=True, blank=True)
    is_crime_prone = models.BooleanField(default=False)
    official_employment = models.CharField(max_length=100, null=True, blank=True)
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='family_social_status')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.student} - {self.marital_status}"

    class Meta:
        db_table = 'family_social_status'
        verbose_name = 'Family Social Status'
        verbose_name_plural = 'Family Social Statuses'
        ordering = ['marital_status']


class FamilyMember(models.Model):
    first_name = models.CharField(max_length=50)
    last_name = models.CharField(max_length=50)
    third_name = models.CharField(max_length=50)
    address = models.CharField(max_length=255)
    work_place = models.CharField(max_length=150, null=True, blank=True)
    unofficial_employment = models.CharField(max_length=100, null=True, blank=True)
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='family_members')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.first_name} {self.last_name}"

    class Meta:
        db_table = 'family_member'
        verbose_name = 'Family Member'
        verbose_name_plural = 'Family Members'
        ordering = ['first_name', 'last_name']


class CategoryInterest(models.Model):
    name = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    class Meta:
        db_table = 'category_interest'
        verbose_name = 'Category Interest'
        verbose_name_plural = 'Category Interests'
        ordering = ['name']


class Interest(models.Model):
    name = models.CharField(max_length=100)
    category = models.ForeignKey(CategoryInterest, on_delete=models.PROTECT, related_name='interests')
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='interests', null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    class Meta:
        db_table = 'interest'
        verbose_name = 'Interest'
        verbose_name_plural = 'Interests'
        ordering = ['name']


class SocialRegistry(models.Model):
    status = models.BooleanField()
    file = models.FileField(upload_to='social_registry/',null=True, blank=True)
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='social_registries')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{'Faol' if self.status else 'Nofaol'}"

    class Meta:
        db_table = 'social_registry'
        verbose_name = 'Social Registry'
        verbose_name_plural = 'Social Registries'
        ordering = ['status']


class Dormitory(models.Model):
    status = models.BooleanField(default=False)
    dormitory_name = models.CharField(max_length=150, null=True, blank=True)
    building_name = models.CharField(max_length=150, null=True, blank=True)
    building_phone = models.CharField(max_length=20, null=True, blank=True)
    floor = models.CharField(max_length=20, null=True, blank=True)
    residence_type = models.CharField(max_length=50, null=True, blank=True)
    address = models.CharField(max_length=100, null=True, blank=True)
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='dormitories')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.dormitory_name or f"Dormitory #{self.pk}"

    class Meta:
        db_table = 'dormitory'
        verbose_name = 'Dormitory'
        verbose_name_plural = 'Dormitories'
        ordering = ['status']


class Gifted(models.Model):
    name = models.CharField(max_length=100, null=True, blank=True)
    status = models.BooleanField(default=False)
    file = models.FileField(upload_to='gifted/',null=True, blank=True)
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='gifteds')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name or f"Gifted #{self.pk}"

    class Meta:
        db_table = 'gifted'
        verbose_name = 'Gifted'
        verbose_name_plural = 'Gifteds'
        ordering = ['status']


class ProtectionOrder(models.Model):
    status = models.BooleanField(default=False)
    file = models.FileField(upload_to='protection_order/',null=True, blank=True)
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='protection_orders')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{'Faol' if self.status else 'Nofaol'} - {self.student}"

    class Meta:
        db_table = 'protection_order'
        verbose_name = 'Protection Order'
        verbose_name_plural = 'Protection Orders'
        ordering = ['status']


FILE_MODELS = [
    Achievement,
    HealthInfo,
    LanguageInfo,
    Reprimand,
    SocialRegistry,
    Gifted,
    ProtectionOrder,
    CustomUser,
]


def get_file_fields(instance):
    fields = []
    for field in instance._meta.fields:
        if isinstance(field, (models.FileField, models.ImageField)):
            fields.append(field.name)
    return fields


def delete_files_from_disk(instance):
    for field_name in get_file_fields(instance):
        field_file = getattr(instance, field_name)
        if field_file:
            try:
                if os.path.isfile(field_file.path):
                    os.remove(field_file.path)
            except Exception:
                pass


@receiver(post_delete)
def auto_delete_file_on_delete(sender, instance, **kwargs):
    if sender in FILE_MODELS:
        delete_files_from_disk(instance)


@receiver(pre_save)
def auto_delete_old_file_on_update(sender, instance, **kwargs):
    if sender not in FILE_MODELS:
        return
    if not instance.pk:
        return

    try:
        old_instance = sender.objects.get(pk=instance.pk)
    except sender.DoesNotExist:
        return

    for field_name in get_file_fields(old_instance):
        old_file = getattr(old_instance, field_name)
        new_file = getattr(instance, field_name)
        if old_file and old_file != new_file:
            try:
                if os.path.isfile(old_file.path):
                    os.remove(old_file.path)
            except Exception:
                pass

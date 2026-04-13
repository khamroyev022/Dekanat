from django.db import models
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db.models.signals import post_delete, pre_save
from django.dispatch import receiver
import os



GENDER_CHOICES = (
    ('erkak', 'Erkak'),
    ('ayol', 'Ayol'),
    ('boshqa', 'Boshqa'),
)

ROLE_CHOICES = (
    ('admin', 'Admin'),
    ('tutor', 'Tyutor'),
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
    name = models.CharField(max_length=120, choices=ROLE_CHOICES, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name or "Role"

    class Meta:
        ordering = ['name']
class CustomUserManager(BaseUserManager):
    def create_superuser(self, username, email=None, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.pop('role', None)  # role ni o'tkazib yuboramiz

        user = self.model(username=username, email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, username, email=None, password=None, **extra_fields):
        user = self.model(username=username, email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user


class CustomUser(AbstractUser):
    third_name = models.CharField(max_length=30, blank=True)
    birthday = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=30, choices=GENDER_CHOICES, blank=True)  # blank=True qo'shing
    image = models.ImageField(upload_to='users/images/', blank=True)
    address = models.CharField(max_length=255, blank=True)
    nationality = models.CharField(max_length=50, blank=True)
    passport_seria = models.CharField(max_length=30, blank=True)
    phone_number = models.CharField(max_length=20, blank=True)
    workplace = models.CharField(max_length=100, blank=True)
    role = models.ForeignKey(
        Role,
        on_delete=models.PROTECT,
        related_name='users',
        null=True,
        blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    objects = CustomUserManager()

    def __str__(self):
        return self.username


class Faculty(models.Model):
    name = models.CharField(max_length=150, unique=True)
    code = models.CharField(max_length=30)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Direction(models.Model):
    name = models.CharField(max_length=150)
    code = models.CharField(max_length=10)
    faculty = models.ForeignKey(Faculty, on_delete=models.PROTECT, related_name='directions')

    def __str__(self):
        return self.name


class Group(models.Model):
    name = models.CharField(max_length=250, unique=True)
    education_code = models.CharField(max_length=20)
    education_language = models.CharField(max_length=30)
    tutor = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, related_name='tutor_groups')
    direction = models.ForeignKey(Direction, on_delete=models.PROTECT, related_name='groups')

    def __str__(self):
        return self.name




class Student(models.Model):
    first_name = models.CharField(max_length=50)
    last_name = models.CharField(max_length=50)
    third_name = models.CharField(max_length=50, blank=True)
    birthday = models.DateField()
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES)
    country = models.CharField(max_length=50, blank=True)
    image = models.ImageField(upload_to='students/', null=True, blank=True)
    image_hemis = models.CharField(max_length=255, null=True, blank=True)
    avg_gpa = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)
    course = models.CharField(max_length=15)
    hemis_id = models.CharField(max_length=13, unique=True, db_index=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    group = models.ForeignKey(Group, on_delete=models.PROTECT, related_name='students')

    def __str__(self):
        return f"{self.first_name} {self.last_name}"


class StudentDetail(models.Model):
    student = models.OneToOneField(Student, on_delete=models.CASCADE, related_name='detail')

    p_country = models.CharField(max_length=50, blank=True, null=True)
    p_region = models.CharField(max_length=50, blank=True, null=True)
    p_district = models.CharField(max_length=50, blank=True, null=True)

    t_country = models.CharField(max_length=50, blank=True, null=True)
    t_region = models.CharField(max_length=50, blank=True, null=True)
    t_district = models.CharField(max_length=50, blank=True, null=True)

    education_type = models.CharField(max_length=30, choices=EDUCATION_TYPE_CHOICES, default='nomalum')
    def __str__(self):
        return f"{self.student}"



def delete_file(path):
    if path and os.path.isfile(path):
        try:
            os.remove(path)
        except Exception:
            pass


def get_file_fields(instance):
    return [f.name for f in instance._meta.fields if isinstance(f, (models.FileField, models.ImageField))]


@receiver(post_delete)
def auto_delete_files(sender, instance, **kwargs):
    for field in get_file_fields(instance):
        file = getattr(instance, field)
        if file:
            delete_file(file.path)


@receiver(pre_save)
def auto_delete_old_files(sender, instance, **kwargs):
    if not instance.pk:
        return

    try:
        old = sender.objects.get(pk=instance.pk)
    except sender.DoesNotExist:
        return

    for field in get_file_fields(instance):
        old_file = getattr(old, field)
        new_file = getattr(instance, field)

        if old_file and old_file != new_file:
            delete_file(old_file.path)
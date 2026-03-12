from django.db import models
from django.contrib.auth.models import AbstractUser


GENDER_CHOICES = (
    ('Male', 'Erkak'),
    ('Female', 'Ayol'),
    ('Other', 'Boshqa'),
)
ROLE_CHOICES = (
    ('Admin', 'Admin'),
    ('Tutor', 'Tutor'),
    ('Dekan', 'Dekan'),
    ('Zam dekan', 'Zam dekan'),
)
EDUCTION_TYPE_CHOICES = (
    ('grant', 'Grant'),
    ('kontrakt', 'Kontrakt'),
    ('nomalum', 'Nomalum'),
)
class Role(models.Model):
    name = models.CharField(max_length=120, choices=ROLE_CHOICES)
    def __str__(self):
        return self.name
    class Meta:
        db_table = 'role'
        verbose_name_plural = 'Role'
        ordering = ['name']

class CustomUser(AbstractUser):
    first_name = models.CharField(max_length = 30)
    last_name = models.CharField(max_length = 30)
    third_name = models.CharField(max_length = 30)
    birthday = models.DateField()
    gender = models.CharField(max_length = 30, choices=GENDER_CHOICES)
    image = models.ImageField(upload_to='images/', null=True, blank=True)
    address = models.CharField(max_length = 30)
    nationality = models.CharField(max_length = 30)
    passport_seria = models.CharField(max_length = 30)
    phone_number = models.CharField(max_length = 30)
    workplace = models.CharField(max_length = 30)
    role = models.ForeignKey(Role, on_delete=models.PROTECT,related_name='user')
    def __str__(self):
        return self.username
    class Meta:
        db_table = 'user'
        verbose_name_plural = 'User'
        ordering = ['first_name', 'last_name']

class Faculty(models.Model):
    name = models.CharField(max_length = 30)
    code = models.CharField(max_length = 30)
    def __str__(self):
        return self.name
    class Meta:
        db_table = 'faculty'
        verbose_name_plural = 'Faculty'
        ordering = ['name']

class Direction(models.Model):
    name = models.CharField(max_length=150,)
    code = models.CharField(max_length=10, unique=True)
    faculty_id = models.ForeignKey(Faculty, on_delete=models.PROTECT,related_name='direction')
    def __str__(self):
        return self.name

class Group(models.Model):
    name = models.CharField(max_length=50, unique=True)
    education_code = models.CharField(max_length=20)
    education_language = models.CharField(max_length = 30)
    user_id = models.ForeignKey(CustomUser, on_delete=models.SET_NULL,null=True,related_name='group_user')
    direction_id = models.ForeignKey(Direction, on_delete=models.PROTECT,related_name='group_direction')
    def __str__(self):
        return self.name
    class Meta:
        db_table = 'group'
        verbose_name_plural = 'Group'
        ordering = ['name']

class Student(models.Model):
    first_name = models.CharField(max_length = 30)
    last_name = models.CharField(max_length = 30)
    third_name = models.CharField(max_length = 30)
    birthday = models.IntegerField()
    gender = models.CharField(max_length = 30, choices=GENDER_CHOICES)
    country = models.CharField(max_length = 30)
    image_full = models.CharField(max_length = 30)
    image_none = models.ImageField(upload_to='student/images/', null=True, blank=True)
    image_full_none = models.ImageField(upload_to='student/images/', null=True, blank=True)
    avg_gpa = models.DecimalField(max_digits=4, decimal_places=2)
    course = models.CharField(max_length = 15)
    hemis_id = models.CharField(max_length=13)
    email = models.EmailField(null=True, blank=True)
    phone = models.CharField(max_length = 30)
    group_id = models.ForeignKey(Group, on_delete=models.PROTECT,related_name='student_group')
    def __str__(self):
        return self.first_name
    class Meta:
        db_table = 'student'
        verbose_name_plural = 'Student'
        ordering = ['first_name', 'last_name']

class StudentDetail(models.Model):
    p_country = models.CharField(max_length = 30)
    p_region = models.CharField(max_length = 30)
    p_district = models.CharField(max_length = 30)
    t_country = models.CharField(max_length = 30)
    t_region = models.CharField(max_length = 30)
    t_district = models.CharField(max_length = 30)
    t_latitude = models.CharField(max_length = 30)
    t_longitude = models.CharField(max_length = 30)
    is_orphanage_student = models.BooleanField(default=False)
    is_military_family=models.BooleanField(default=False)
    education_type = models.CharField(max_length = 30, choices=EDUCTION_TYPE_CHOICES,default='nomalum')
    is_pregnant = models.BooleanField(default=False)
    behavior_issues = models.BooleanField(default=False)
    is_adult=models.BooleanField(default=False)
    student_id = models.ForeignKey(Student, on_delete=models.PROTECT,related_name='student_detail')
    def __str__(self):
        return self.p_country
    class Meta:
        db_table = 'student_detail'
        verbose_name_plural = 'Student Detail'
        ordering = ['p_country', 'p_region', 'p_district']

































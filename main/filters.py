# filters.py

import django_filters
from django.db.models import Q
from .models import *


class StudentFilter(django_filters.FilterSet):

    # ───────── QIDIRUV ─────────
    search = django_filters.CharFilter(method='search_filter')

    gender  = django_filters.ChoiceFilter(choices=GENDER_CHOICES)
    course  = django_filters.CharFilter(lookup_expr='exact')
    country = django_filters.CharFilter(lookup_expr='icontains')

    group     = django_filters.NumberFilter(field_name='group__id')
    direction = django_filters.NumberFilter(field_name='group__direction__id')
    faculty   = django_filters.NumberFilter(field_name='group__direction__faculty__id')

    gpa = django_filters.NumberFilter(method='filter_gpa')


    education_type       = django_filters.ChoiceFilter(
                               field_name='details__education_type',
                               choices=EDUCATION_TYPE_CHOICES
                           )
    is_orphanage_student = django_filters.BooleanFilter(field_name='details__is_orphanage_student')
    is_military_family   = django_filters.BooleanFilter(field_name='details__is_military_family')
    is_pregnant          = django_filters.BooleanFilter(field_name='details__is_pregnant')
    behavior_issues      = django_filters.BooleanFilter(field_name='details__behavior_issues')
    is_adult             = django_filters.BooleanFilter(field_name='details__is_adult')

    # ───────── HEALTH INFO ─────────
    disability        = django_filters.BooleanFilter(field_name='health_info__disability')
    health_status     = django_filters.BooleanFilter(field_name='health_info__health_status')
    disability_status = django_filters.ChoiceFilter(
                            field_name='health_info__disability_status',
                            choices=DISABILITY_GROUP
                        )

    # ───────── DORMITORY ─────────
    has_dormitory  = django_filters.BooleanFilter(field_name='dormitory__status')
    residence_type = django_filters.ChoiceFilter(
                         field_name='dormitory__residence_type',
                         choices=Dormitory.RESIDENCE_TYPE_CHOICES
                     )

    # ───────── FAMILY SOCIAL STATUS ─────────
    marital_status = django_filters.ChoiceFilter(
                         field_name='family_social_status__marital_status',
                         choices=MARITAL_STATUS
                     )
    is_orphan      = django_filters.ChoiceFilter(
                         field_name='family_social_status__is_orphan',
                         choices=ORPHAN_STATUS
                     )
    is_crime_prone = django_filters.BooleanFilter(field_name='family_social_status__is_crime_prone')

    # ───────── LANGUAGE INFO ─────────
    language_level  = django_filters.ChoiceFilter(
                          field_name='language_info__level',
                          choices=LANGUAGE_LEVEL
                      )
    language_status = django_filters.BooleanFilter(field_name='language_info__status')

    # ───────── ACHIEVEMENT ─────────
    has_achievement = django_filters.BooleanFilter(method='filter_has_achievement')

    has_reprimand    = django_filters.BooleanFilter(method='filter_has_reprimand')
    reprimand_status = django_filters.BooleanFilter(field_name='reprimands__status')

    social_registry_status = django_filters.BooleanFilter(field_name='social_registries__status')

    is_gifted = django_filters.BooleanFilter(field_name='gifteds__status')

    has_protection_order = django_filters.BooleanFilter(field_name='protection_orders__status')

    class Meta:
        model  = Student
        fields = []


    def search_filter(self, queryset, name, value):
        return queryset.filter(
            Q(first_name__icontains=value) |
            Q(last_name__icontains=value)  |
            Q(third_name__icontains=value) |
            Q(hemis_id__icontains=value)   |
            Q(phone__icontains=value)      |
            Q(email__icontains=value)      |
            Q(group__name__icontains=value)
        ).distinct()

    def filter_has_achievement(self, queryset, name, value):
        if value:
            return queryset.filter(achievements__isnull=False).distinct()
        return queryset.filter(achievements__isnull=True)

    def filter_has_reprimand(self, queryset, name, value):
        if value:
            return queryset.filter(reprimands__isnull=False).distinct()
        return queryset.filter(reprimands__isnull=True)

    def filter_gpa(self, queryset, name, value):
        if int(value) == 1:
            return queryset.order_by('-avg_gpa')  # yuqoridan pastga
        elif int(value) == 0:
            return queryset.order_by('avg_gpa')   # pastdan yuqoriga
        return queryset
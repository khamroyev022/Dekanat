from apscheduler.schedulers.background import BackgroundScheduler
from django_apscheduler.jobstores import DjangoJobStore
from datetime import date
import os


def update_is_adult():
    from .models import StudentDetail
    today  = date.today()
    total  = 0
    BATCH  = 1000

    details = StudentDetail.objects.select_related('student').filter(
        student__birthday__isnull=False
    ).only('is_adult', 'student__birthday')

    total_found = details.count()

    to_update = []

    for detail in details.iterator(chunk_size=BATCH):
        b = detail.student.birthday
        if not b:
            continue

        is_adult = (
            today.year - b.year -
            ((today.month, today.day) < (b.month, b.day))
        ) >= 18

        if detail.is_adult != is_adult:
            detail.is_adult = is_adult
            to_update.append(detail)

            if len(to_update) >= BATCH:
                StudentDetail.objects.bulk_update(to_update, ['is_adult'])
                total += len(to_update)
                to_update = []

    if to_update:
        StudentDetail.objects.bulk_update(to_update, ['is_adult'])
        total += len(to_update)

def start():
    if os.environ.get('RUN_MAIN') != 'true':
        return

    scheduler = BackgroundScheduler()
    scheduler.add_jobstore(DjangoJobStore(), 'default')

    scheduler.add_job(
        update_is_adult,
        trigger='cron',
        hour=0,
        minute=0,
        id='update_is_adult',
        replace_existing=True,
    )

    scheduler.start()

from celery import Celery
from .config import get_settings

celery_app=Celery('ecoguard',broker=get_settings().redis_url,backend=get_settings().redis_url)
celery_app.conf.update(task_serializer='json',accept_content=['json'],result_serializer='json',
    task_acks_late=True,worker_prefetch_multiplier=1,broker_connection_retry_on_startup=True,
    task_time_limit=180,task_soft_time_limit=150,result_expires=3600,
    beat_schedule={'drain-database-outbox':{'task':'ecoguard.dispatch','schedule':15.0}})

@celery_app.task(name='ecoguard.execute')
def execute(job_id):
    from .jobs import process_job
    process_job(job_id)

@celery_app.task(name='ecoguard.dispatch')
def dispatch():
    from .jobs import dispatch_pending
    return dispatch_pending()

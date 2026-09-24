"""Transactional database outbox plus Celery dispatch.
In-app publication is a database operation. External SMS is opt-in and disabled by default.
At-least-once dispatch: the optional webhook must honour the stable Idempotency-Key.
"""
from datetime import datetime, timezone, timedelta
from .config import get_settings
from .db import SessionLocal
from .models import Outbox, Prediction, Evidence, Advisory, User, now
from . import storage


def process_job(job_id):
    with SessionLocal() as db:
        job=db.query(Outbox).filter_by(id=job_id).with_for_update().first()
        if not job or job.state in ('done','skipped'):return
        if job.attempts>=5:job.state='failed';db.commit();return
        job.attempts+=1;job.state='processing';job.updated_at=now()
        try:
            if job.kind=='prediction':
                from .ai import infer
                p=db.get(Prediction,job.aggregate_id);e=db.get(Evidence,p.evidence_id)
                result=infer(storage.get(e.storage_key))
                for k,v in result.items():setattr(p,k,v)
                job.state='done'
            elif job.kind=='advisory':
                a=db.get(Advisory,job.aggregate_id)
                if not a or a.state!='published' or a.expires_at<=now():
                    job.state='skipped';job.last_error='Advisory is not active.'
                else:
                    # In-app reads query this published record. This is not an SMS delivery claim.
                    cfg=get_settings()
                    if cfg.sms_provider=='disabled':
                        job.state='done';job.last_error='In-app publication available. External SMS is disabled.'
                    else:
                        recipients=[u for u in db.query(User).filter_by(active=True).all()
                            if a.area_id in u.preferences.get('followed_areas',[]) and u.preferences.get('sms_opt_in') and u.preferences.get('phone')]
                        for user in recipients:
                            key=f'sms:{a.id}:{user.id}'
                            if not db.query(Outbox).filter_by(dedupe_key=key).first():
                                db.add(Outbox(kind='sms',aggregate_id=a.id,dedupe_key=key))
                        job.state='done'
            elif job.kind=='sms':
                cfg=get_settings();a=db.get(Advisory,job.aggregate_id)
                user=db.get(User,job.dedupe_key.split(':')[-1])
                if not a or a.state!='published' or a.expires_at<=now() or not user or not user.active or not user.preferences.get('sms_opt_in') or a.area_id not in user.preferences.get('followed_areas',[]):
                    job.state='skipped';job.last_error='Delivery no longer eligible.'
                elif cfg.sms_provider!='webhook' or not cfg.sms_webhook_url or not cfg.sms_webhook_token:
                    job.state='skipped';job.last_error='SMS provider not configured.'
                else:
                    import httpx
                    if not cfg.sms_webhook_url.startswith('https://'):raise ValueError('SMS webhook requires HTTPS.')
                    response=httpx.post(cfg.sms_webhook_url,headers={'Authorization':'Bearer '+cfg.sms_webhook_token,
                        'Idempotency-Key':job.dedupe_key},json={'recipient':user.preferences['phone'],
                        'text':a.title+'\n'+a.body,'advisory_id':a.id},timeout=10)
                    response.raise_for_status()
                    job.state='done';job.last_error='Provider accepted request; delivery/read receipt is not established.'
            else:
                job.state='skipped';job.last_error='Unknown job type.'
        except Exception as exc:
            # Retain no raw provider payload or credentials in errors.
            job.state='retry' if job.attempts<5 else 'failed'
            job.last_error=f'{type(exc).__name__}: processing failed; inspect protected operator logs.'
            if job.kind=='prediction':
                p=db.get(Prediction,job.aggregate_id)
                if p:p.state='failed';p.explanation='Image assistance failed. Human reporting remains available.'
        job.updated_at=now();db.commit()


def dispatch_pending():
    cfg=get_settings()
    with SessionLocal() as db:
        jobs=db.query(Outbox).filter(Outbox.state.in_(['pending','retry'])).order_by(Outbox.created_at).limit(50).all()
        ids=[]
        for job in jobs:
            elapsed=(datetime.now(timezone.utc)-datetime.fromisoformat(job.updated_at)).total_seconds()
            if job.state=='retry' and elapsed < min(300,2**job.attempts*5):continue
            ids.append(job.id)
    if cfg.jobs_mode=='inline':
        for job_id in ids:process_job(job_id)
    else:
        try:
            from .worker import execute
            for job_id in ids:execute.delay(job_id)
        except Exception:
            # The transaction already committed. Beat will retry dispatch from the DB outbox.
            pass
    return len(ids)

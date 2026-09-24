"""Private storage. Objects are served ONLY through authenticated evidence routes."""
from pathlib import Path
from .config import get_settings

def s3():
    import boto3
    cfg=get_settings()
    return boto3.client('s3', endpoint_url=cfg.s3_endpoint_url, region_name=cfg.s3_region,
        aws_access_key_id=cfg.s3_access_key, aws_secret_access_key=cfg.s3_secret_key)

def put(key, data):
    cfg=get_settings()
    if cfg.storage_backend=='s3':
        s3().put_object(Bucket=cfg.s3_bucket,Key=key,Body=data,ContentType='image/jpeg')
    else:
        path=Path(cfg.media_dir); path.mkdir(parents=True,exist_ok=True)
        (path/key).write_bytes(data)

def get(key):
    cfg=get_settings()
    if cfg.storage_backend=='s3': return s3().get_object(Bucket=cfg.s3_bucket,Key=key)['Body'].read()
    return (Path(cfg.media_dir)/key).read_bytes()

def remove(key):
    cfg=get_settings()
    if cfg.storage_backend=='s3': s3().delete_object(Bucket=cfg.s3_bucket,Key=key)
    else: (Path(cfg.media_dir)/key).unlink(missing_ok=True)

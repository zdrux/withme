from __future__ import annotations

import os
from typing import Optional

import requests

from ..config import get_settings


def _headers(key: str, content_type: Optional[str] = None) -> dict:
    h = {
        'Authorization': f'Bearer {key}',
        'apikey': key,
    }
    if content_type:
        h['Content-Type'] = content_type
    return h


def ensure_public_bucket(bucket: str = 'agent-avatars') -> bool:
    """Ensure a public storage bucket exists. Returns True on success or if already exists."""
    settings = get_settings()
    base = settings.supabase_url or settings.supabase_project_url
    key = settings.supabase_service_role_key or settings.supabase_anon_key
    if not base or not key:
        return False
    try:
        # Try to list buckets and check by name
        r = requests.get(f"{base.rstrip('/')}/storage/v1/bucket", headers=_headers(key), timeout=15)
        print(f"[storage] list buckets status={r.status_code}")
        if r.ok:
            arr = r.json() if r.headers.get('content-type','').lower().startswith('application/json') else []
            if isinstance(arr, list) and any((b.get('name') == bucket) for b in arr):
                print(f"[storage] bucket exists name={bucket}")
                return True
        # Create bucket
        cr = requests.post(
            f"{base.rstrip('/')}/storage/v1/bucket",
            headers=_headers(key, 'application/json'),
            json={"name": bucket, "public": True},
            timeout=15,
        )
        print(f"[storage] create bucket name={bucket} status={cr.status_code}")
        return cr.ok
    except Exception:
        print("[storage] ensure_public_bucket failed")
        return False


def upload_public_image_from_url(url: str, bucket: str = 'agent-avatars', object_path: Optional[str] = None) -> Optional[str]:
    """Download an image from `url` and upload to Supabase Storage.

    Returns the public URL if upload succeeds; otherwise None.
    """
    settings = get_settings()
    base = settings.supabase_url or settings.supabase_project_url
    key = settings.supabase_service_role_key or settings.supabase_anon_key
    if not base or not key:
        return None
    if not object_path:
        import uuid
        object_path = f"{uuid.uuid4()}.jpg"
    try:
        # Ensure bucket exists (best effort)
        print(f"[storage] upload start bucket={bucket} path={object_path}")
        ensure_public_bucket(bucket)
        r = requests.get(url, timeout=20)
        r.raise_for_status()
        content = r.content
        ct = r.headers.get('content-type', 'image/jpeg')
        up = requests.post(
            f"{base.rstrip('/')}/storage/v1/object/{bucket}/{object_path}",
            headers={**_headers(key, ct), 'x-upsert': 'true'},
            data=content,
            timeout=30,
        )
        print(f"[storage] upload status={up.status_code}")
        up.raise_for_status()
        # Public URL convention
        public_url = f"{base.rstrip('/')}/storage/v1/object/public/{bucket}/{object_path}"
        return public_url
    except Exception:
        print("[storage] upload failed; falling back to original URL")
        return None

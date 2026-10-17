"""Private S3-compatible storage for deployment maps and complete assessment records."""
from __future__ import annotations

import hashlib
import json
import os
import tarfile
from pathlib import Path, PurePosixPath


def s3_client():
    import boto3
    from botocore.config import Config
    return boto3.client('s3', endpoint_url=os.environ.get('SPRING_S3_ENDPOINT') or None,
                        region_name=os.environ.get('AWS_DEFAULT_REGION', 'auto'),
                        config=Config(connect_timeout=10, read_timeout=60,
                                      retries={'max_attempts': 2},
                                      s3={'addressing_style': 'path'}))


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b''):
            digest.update(chunk)
    return digest.hexdigest()


def unpack_maps(archive, destination):
    """Reject traversal, links and unexpected roots before writing any archive contents."""
    destination = Path(destination).resolve()
    with tarfile.open(archive, 'r:gz') as tar:
        members = tar.getmembers()
        if sum(m.size for m in members) > 20 * 1024**3:
            raise ValueError('Map bundle exceeds the 20 GiB extraction limit')
        for member in members:
            path = PurePosixPath(member.name)
            if ('\\' in member.name or path.is_absolute() or '..' in path.parts
                    or not path.parts or path.parts[0] not in {'layer_cache', 'local_layers', 'snapshots', 'bundle.json'}
                    or not (member.isfile() or member.isdir())):
                raise ValueError('Map bundle contains an unsafe or unexpected member')
            target = destination.joinpath(*path.parts).resolve()
            if not target.is_relative_to(destination):
                raise ValueError('Map bundle escapes its destination')
        tar.extractall(destination, members=members, filter='data')


def restore_maps(destination, client=None):
    destination = Path(destination)
    expected = os.environ.get('SPRING_DATA_SHA256', '').lower()
    if len(expected) != 64 or any(c not in '0123456789abcdef' for c in expected):
        raise ValueError('Set SPRING_DATA_SHA256 to the prepared bundle checksum')
    marker = destination / '.bundle-sha256'
    if marker.is_file() and marker.read_text().strip() == expected:
        return
    if marker.exists():
        raise ValueError('A different bundle is already extracted: use a fresh data directory')
    destination.mkdir(parents=True, exist_ok=True)
    archive = destination / 'download.tar.gz'
    try:
        (client or s3_client()).download_file(os.environ['SPRING_DATA_BUCKET'], os.environ['SPRING_DATA_KEY'], str(archive))
        if sha256(archive) != expected:
            raise ValueError('Downloaded map bundle does not match its SHA-256 checksum')
        unpack_maps(archive, destination)
        marker.write_text(expected + '\n')
    finally:
        archive.unlink(missing_ok=True)


def archive_run(response, request, client=None):
    """One object contains the exact accepted response, original request and readable report."""
    bucket = os.environ.get('SPRING_RUN_BUCKET')
    if not bucket:
        return {'durable': False, 'reason': 'No external assessment archive configured'}
    payload = {'request': request, 'result': response,
               'report_markdown': '\n\n'.join(response[m]['report_markdown'] for m in 'ABC')}
    key = f"runs/{response['run_id']}.json"
    (client or s3_client()).put_object(Bucket=bucket, Key=key,
        Body=json.dumps(payload, ensure_ascii=False, allow_nan=False).encode('utf-8'),
        ContentType='application/json')
    return {'durable': True, 'archive_key': key}

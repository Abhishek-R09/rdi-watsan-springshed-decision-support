"""Deployment safety/contract checks; no cloud writes, fabricated science or live data downloads."""
import base64
import io
import json
import sys
import tarfile
import threading
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import deployment_storage as storage
import render_app

REQUEST = {'spring': {'name': 'Test', 'latitude': 29.91903, 'longitude': 78.55647}, 'field': {}}


def result():
    return {'run_id': 'test-run', 'spring': REQUEST['spring'],
            **{m: {'status': 'unavailable', 'report_markdown': f'# {m}\nNo test data'} for m in 'ABC'}}


@pytest.fixture
def app(monkeypatch):
    monkeypatch.setenv('SPRING_PILOT_PASSWORD', 'test-password')
    monkeypatch.setenv('SPRING_REQUIRE_ARCHIVE', '0')
    tool = SimpleNamespace(health=lambda: {'ok': True, 'offline': True, 'map_set': None},
                           springs=lambda: [], assess=lambda payload: result(),
                           terrain=SimpleNamespace(tile=lambda *args: b'png'))
    return render_app.create_app(tool=tool, archive=lambda *args: {'durable': True})


def auth():
    return {'Authorization': 'Basic ' + base64.b64encode(b'watsan:test-password').decode()}


def test_health_probe_is_public_but_application_requires_sign_in(app):
    client = app.test_client()
    assert client.get('/api/health').status_code == 200
    for path in ['/', '/api/springs', '/api/status', '/api/terrain/1/0/0.png']:
        assert client.get(path).status_code == 401
    assert client.get('/api/status', headers=auth()).json['offline'] is True


def test_real_route_contract_and_invalid_requests(app):
    client = app.test_client()
    response = client.post('/api/assess', json=REQUEST, headers=auth())
    assert response.status_code == 200 and response.json['persistence']['durable']
    assert client.post('/api/assess', json={'spring': {'latitude': 1}}, headers=auth()).status_code == 400
    assert client.post('/api/assess', data='not json', headers=auth()).status_code == 400
    assert client.post('/api/assess', data='x'*(2**20+1), content_type='application/json', headers=auth()).status_code == 413
    assert client.get('/api/terrain/1/9/9.png', headers=auth()).status_code == 404
    assert client.get('/api/unknown', headers=auth()).status_code == 404


def test_public_visual_terrain_avoids_gis_tile_work_but_keeps_auth(app, monkeypatch):
    monkeypatch.setenv('SPRING_TERRAIN_SOURCE', 'public')
    def forbidden(*args):
        raise AssertionError('Hosted visual terrain must not allocate GIS tile buffers')
    monkeypatch.setattr(render_app.core.Terrain, 'tile', forbidden)
    client = app.test_client()
    assert client.get('/api/terrain/14/11766/6764.png').status_code == 401
    response = client.get('/api/terrain/14/11766/6764.png', headers=auth())
    assert response.status_code == 302
    assert response.headers['Location'] == 'https://s3.amazonaws.com/elevation-tiles-prod/terrarium/14/11766/6764.png'
    assert client.get('/api/terrain/14/99999/6764.png', headers=auth()).status_code == 404


def test_archive_failure_still_delivers_result_with_explicit_unsaved_status(monkeypatch):
    monkeypatch.setenv('SPRING_PILOT_PASSWORD', 'test-password')
    monkeypatch.setenv('SPRING_REQUIRE_ARCHIVE', '0')
    def fail(*args): raise OSError('storage is unavailable')
    app = render_app.create_app(tool=SimpleNamespace(assess=lambda request: result()), archive=fail)
    response = app.test_client().post('/api/assess', json=REQUEST, headers=auth())
    assert response.status_code == 200
    assert response.json['persistence']['durable'] is False
    assert response.json['A']['status'] == 'unavailable'


def test_parallel_assessment_rejected_without_blocking_health(monkeypatch):
    monkeypatch.setenv('SPRING_PILOT_PASSWORD', 'test-password')
    monkeypatch.setenv('SPRING_REQUIRE_ARCHIVE', '0')
    entered, release = threading.Event(), threading.Event()
    def assess(payload):
        entered.set(); release.wait(5); return result()
    app = render_app.create_app(tool=SimpleNamespace(assess=assess), archive=lambda *args: {'durable': True})
    def run():
        with app.test_client() as client: client.post('/api/assess', json=REQUEST, headers=auth())
    thread = threading.Thread(target=run); thread.start()
    try:
        assert entered.wait(5)
        client = app.test_client()
        assert client.get('/api/health').status_code == 200
        assert client.post('/api/assess', json=REQUEST, headers=auth()).status_code == 429
    finally:
        release.set(); thread.join(5)


def test_hosted_start_refuses_missing_password_or_required_archive(monkeypatch):
    monkeypatch.delenv('SPRING_PILOT_PASSWORD', raising=False)
    with pytest.raises(ValueError, match='PASSWORD'): render_app.create_app(tool=object())
    monkeypatch.setenv('SPRING_PILOT_PASSWORD', 'test')
    monkeypatch.setenv('SPRING_REQUIRE_ARCHIVE', '1')
    monkeypatch.delenv('SPRING_RUN_BUCKET', raising=False)
    with pytest.raises(ValueError, match='BUCKET'): render_app.create_app(tool=object())


@pytest.mark.parametrize('name,kind', [('../escape', 'file'), ('layer_cache/link', 'link'), ('scripts/overwrite.py', 'file')])
def test_bundle_rejects_traversal_links_and_code_overwrite(tmp_path, name, kind):
    archive = tmp_path / 'bad.tar.gz'
    with tarfile.open(archive, 'w:gz') as tar:
        member = tarfile.TarInfo(name)
        if kind == 'link': member.type = tarfile.SYMTYPE; member.linkname = '../../escape'
        else: member.size = 1
        tar.addfile(member, io.BytesIO(b'x') if kind == 'file' else None)
    with pytest.raises(ValueError): storage.unpack_maps(archive, tmp_path / 'out')
    assert not (tmp_path / 'escape').exists()


def test_bundle_checksum_and_restore(tmp_path, monkeypatch):
    archive = tmp_path / 'maps.tar.gz'
    with tarfile.open(archive, 'w:gz') as tar:
        member = tarfile.TarInfo('layer_cache/dem/tile.tif'); member.size = 3
        tar.addfile(member, io.BytesIO(b'abc'))
    monkeypatch.setenv('SPRING_DATA_BUCKET', 'private')
    monkeypatch.setenv('SPRING_DATA_KEY', 'maps/v1')
    class Client:
        def download_file(self, bucket, key, path): Path(path).write_bytes(archive.read_bytes())
    monkeypatch.setenv('SPRING_DATA_SHA256', '0'*64)
    with pytest.raises(ValueError, match='checksum'): storage.restore_maps(tmp_path / 'wrong', Client())
    monkeypatch.setenv('SPRING_DATA_SHA256', storage.sha256(archive))
    storage.restore_maps(tmp_path / 'correct', Client())
    assert (tmp_path / 'correct/layer_cache/dem/tile.tif').read_bytes() == b'abc'


def test_archive_contains_original_request_result_and_reports(monkeypatch):
    monkeypatch.setenv('SPRING_RUN_BUCKET', 'private')
    calls = []
    client = SimpleNamespace(put_object=lambda **kwargs: calls.append(kwargs))
    archived = storage.archive_run(result(), REQUEST, client)
    payload = json.loads(calls[0]['Body'])
    assert archived['durable'] and calls[0]['Key'] == 'runs/test-run.json'
    assert payload['request'] == REQUEST and payload['result']['run_id'] == 'test-run'
    assert '# C' in payload['report_markdown']

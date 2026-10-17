"""Measure a fresh full assessment with psutil. Network downloads disabled; synthetic field answers."""
import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def child(output):
    sys.path.insert(0, str(ROOT / 'scripts'))
    import base64
    import boto3
    from spring_tool_server import Tool
    from render_app import create_app
    tool = Tool()
    tool.session.session.offline = True
    tool.session.mod.set_offline(True)
    request = {'spring': {'name': 'Deployment benchmark - synthetic field inputs', 'latitude': 29.91903, 'longitude': 78.55647},
               'field': {'lean_flow_lpm': 2.5, 'monsoon_flow_lpm': 12, 'flow_vs_past': 'a_bit_less'},
               'di': {'sites': [{'latitude': 29.920, 'longitude': 78.557, 'roof_area_m2': 100,
                                 'first_flush': True, 'filter': True}]}}
    # Include the hosted adapter and SDK allocation, without making a cloud request.
    boto3.client('s3', aws_access_key_id='benchmark', aws_secret_access_key='benchmark', region_name='us-east-1')
    os.environ['SPRING_PILOT_PASSWORD'] = 'local-benchmark'
    os.environ['SPRING_REQUIRE_ARCHIVE'] = '0'
    app = create_app(tool=tool, archive=lambda *args: {'durable': False, 'reason': 'Local benchmark; no cloud writes'})
    headers = {'Authorization': 'Basic ' + base64.b64encode(b'watsan:local-benchmark').decode()}
    start = time.perf_counter()
    with app.test_client() as client:
        response = client.post('/api/assess', json=request, headers=headers)
        if response.status_code != 200:
            raise RuntimeError(f'Hosted assessment failed with HTTP {response.status_code}')
        result = response.json
    Path(output).write_text(json.dumps({'seconds': time.perf_counter()-start,
        'modules': {m: {'status': result[m]['status'], 'warnings': result[m]['warnings'],
                         'rationale': result[m]['rationale']} for m in 'ABC'},
        'note': 'Synthetic inputs. Current machine, not a 0.1 CPU / 512 MB Render measurement.'}, indent=2))


def main():
    import psutil
    folder = ROOT / '.deployment-benchmark'; folder.mkdir(exist_ok=True)
    result_path = folder / 'assessment.json'
    env = dict(os.environ, SPRING_RUNS_DIR=str(folder / 'runs'), OPENBLAS_NUM_THREADS='1',
               OMP_NUM_THREADS='1', NUMBA_NUM_THREADS='1', GDAL_CACHEMAX='32',
               SPRING_TERRAIN_READERS='1', SPRING_TERRAIN_CACHE='64', SPRING_FEATURE_CACHE='2', SPRING_ZONE_CACHE='1')
    started = time.perf_counter()
    with (folder / 'process.log').open('w', encoding='utf-8') as log:
        process = subprocess.Popen([sys.executable, str(Path(__file__)), '--child', str(result_path)],
                                   cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT)
        watched = psutil.Process(process.pid); peak = 0
        while process.poll() is None:
            try: peak = max(peak, watched.memory_info().rss)
            except psutil.NoSuchProcess: pass
            if time.perf_counter()-started > 600:
                process.terminate(); process.wait(); raise SystemExit('Benchmark exceeded 10 minutes; see process.log')
            time.sleep(.1)
    summary = {'exit_code': process.returncode, 'elapsed_seconds': round(time.perf_counter()-started, 2),
               'peak_rss_mib': round(peak/1024**2, 1), 'render_ram_mib': 512,
               'within_512_mib_on_this_machine': peak <= 512*1024**2,
               'note': 'Local RSS sample, not Linux cgroup total memory. Does not certify Render performance.'}
    (folder / 'summary.json').write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))
    raise SystemExit(process.returncode)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__); parser.add_argument('--child')
    args = parser.parse_args()
    child(args.child) if args.child else main()

"""Restore private map assets, then start the hosted application. No secrets are printed."""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from deployment_storage import restore_maps


def main():
    required = ['SPRING_PILOT_PASSWORD', 'AWS_ACCESS_KEY_ID', 'AWS_SECRET_ACCESS_KEY',
                'SPRING_DATA_BUCKET', 'SPRING_DATA_KEY', 'SPRING_DATA_SHA256']
    if os.environ.get('SPRING_REQUIRE_ARCHIVE', '1') == '1':
        required.append('SPRING_RUN_BUCKET')
    missing = [key for key in required if not os.environ.get(key)]
    if missing:
        raise SystemExit('Deployment settings missing: ' + ', '.join(missing))
    print('Restoring the prepared map bundle from private storage...', flush=True)
    restore_maps(Path(os.environ.get('SPRING_LAYER_CACHE', '/tmp/spring-data/layer_cache')).parent)
    os.execvp('gunicorn', ['gunicorn', '--chdir', str(ROOT / 'scripts'),
                          '--config', str(ROOT / 'deploy/gunicorn.conf.py'), 'render_app:create_app()'])


if __name__ == '__main__':
    main()

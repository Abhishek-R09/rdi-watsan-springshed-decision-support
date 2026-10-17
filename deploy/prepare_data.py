"""Package existing analytical maps only. Does not download, approve, upload or alter source data."""
from __future__ import annotations
import argparse
import io
import json
import sys
import tarfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import module_a_snapshot as snapshots
from deployment_storage import sha256


def prepare(output):
    places = snapshots.roots()
    entries = []
    # Local layer layout is retained: the existing GIS loader resolves these paths.
    allowed = {'layer_cache': {'dem': {'.tif'}, 'worldcover': {'.tif'}, 'wapor': {'.npz'}},
               'local_layers': {'IMD': {'.nc'}, 'SoilGrids': {'.tif'}, 'Bhoonidhi': {'.zip'}}}
    files = []
    for root, folders in allowed.items():
        for folder, suffixes in folders.items():
            for path in sorted((places[root] / folder).rglob('*')):
                if path.is_file() and not path.is_symlink() and path.suffix.lower() in suffixes:
                    relative = path.relative_to(places[root]).as_posix()
                    files.append((path, f'{root}/{relative}'))
    manifest = snapshots.active()
    if manifest:
        problems = snapshots.check_files(manifest)
        if problems:
            raise ValueError('Approved map set does not verify: ' + '; '.join(problems))
        # The active manifest is restored to SPRING_SNAPSHOT_DIR. No approval is invented here.
        files.append((snapshots.ACTIVE, 'snapshots/active.json'))
    for path, name in files:
        entries.append({'path': name, 'bytes': path.stat().st_size, 'sha256': sha256(path)})
    gaps = [f'{root}/{folder}' for root, folders in allowed.items() for folder in folders
            if not any(x['path'].startswith(f'{root}/{folder}/') for x in entries)]
    metadata = {'created_utc': datetime.now(timezone.utc).isoformat(), 'files': entries,
                'uncompressed_bytes': sum(x['bytes'] for x in entries), 'missing_layer_families': gaps,
                'approved_snapshot': manifest['snapshot_id'] if manifest else None,
                'source_note': 'Existing local analytical files copied unchanged. Coverage and redistribution rights require review.'}
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        raise ValueError('Output already exists; choose a versioned filename')
    with tarfile.open(output, 'w:gz', compresslevel=1) as tar:
        for path, name in files:
            tar.add(path, arcname=name, recursive=False)
        blob = json.dumps(metadata, indent=2).encode()
        info = tarfile.TarInfo('bundle.json'); info.size = len(blob)
        tar.addfile(info, io.BytesIO(blob))
    metadata['archive_sha256'] = sha256(output)
    metadata['archive_bytes'] = output.stat().st_size
    output.with_suffix(output.suffix + '.manifest.json').write_text(json.dumps(metadata, indent=2), encoding='utf-8')
    return metadata


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', default=str(ROOT / 'deploy/artifacts/pilot-v1.tar.gz'))
    args = parser.parse_args()
    result = prepare(args.output)
    print(json.dumps({k: v for k, v in result.items() if k != 'files'}, indent=2))

"""Layer startup must not require access to another operating-system user's home."""
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import build_spring_features as layers


def test_layers_open_when_root_home_is_inaccessible(tmp_path, monkeypatch):
    original = Path.exists
    def guarded(path):
        if str(path).replace('\\', '/').startswith('/root/'):
            raise PermissionError('root home is private')
        return original(path)
    monkeypatch.setattr(Path, 'exists', guarded)
    monkeypatch.setattr(layers, 'dem_tiles_for', lambda *args: [])
    monkeypatch.setattr(layers, 'worldcover_tiles_for', lambda *args: [])
    monkeypatch.setattr(layers, 'WaporStack', lambda *args, **kwargs: object())
    monkeypatch.setattr(layers, 'LocalLayers', lambda *args: SimpleNamespace(found=[]))
    monkeypatch.setattr(layers, 'NgdrGeology', lambda: SimpleNamespace(ok=False))
    monkeypatch.setattr(layers, 'OpenBuildingsTemporal', lambda *args: object())
    monkeypatch.setenv('CURL_CA_BUNDLE', '/operator-configured/trust.pem')
    result = layers.open_layers([(29.9, 78.5)], tmp_path, tmp_path, soil_hwsd=False)
    assert result.dem == [] and result.local.found == []
    assert layers.os.environ['CURL_CA_BUNDLE'] == '/operator-configured/trust.pem'

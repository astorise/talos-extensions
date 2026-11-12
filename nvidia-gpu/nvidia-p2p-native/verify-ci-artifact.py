#!/usr/bin/env python3
"""Verify Actions build provenance and the module payload before installation."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import re
import tarfile

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('artifact', type=Path)
parser.add_argument('--commit', required=True)
args = parser.parse_args()
record = json.loads((args.artifact / 'build.json').read_text(encoding='utf-8'))
assert record['repository'] == 'astorise/talos-extensions'
assert record['commit'] == args.commit
patch = Path(__file__).with_name('595.71.05-ga106-native.patch').read_bytes().replace(b'\r\n', b'\n')
assert hashlib.sha256(patch).hexdigest() == record['patchSha256']
if 'kernelABIManifestSha256' in record:
    abi_manifest = Path(__file__).with_name('kernel-abi') / 'SHA256SUMS'
    assert hashlib.sha256(abi_manifest.read_bytes()).hexdigest() == record['kernelABIManifestSha256']
archive = args.artifact / 'extension.tar'
with archive.open('rb') as file:
    assert hashlib.file_digest(file, 'sha256').hexdigest() == record['ociArchiveSha256']

def blob(tar, digest):
    algorithm, value = digest.split(':', 1)
    assert algorithm == 'sha256' and re.fullmatch('[a-f0-9]{64}', value)
    data = tar.extractfile('blobs/sha256/' + value).read()
    assert hashlib.sha256(data).hexdigest() == value
    return data

modules = {}
manifest = None
with tarfile.open(archive) as tar:
    index = json.load(tar.extractfile('index.json'))
    assert len(index['manifests']) == 1
    descriptor = index['manifests'][0]
    assert descriptor['digest'] == record['digest']
    image = json.loads(blob(tar, descriptor['digest']))
    config = json.loads(blob(tar, image['config']['digest']))
    assert config['architecture'] == 'amd64' and config['os'] == 'linux'
    for layer in image['layers']:
        with tarfile.open(fileobj=io.BytesIO(blob(tar, layer['digest']))) as payload:
            for member in payload:
                name = member.name.removeprefix('./')
                assert not name.endswith(('.pem', '.key'))
                if name == 'manifest.yaml':
                    manifest = payload.extractfile(member).read().decode('utf-8')
                if name.endswith('.ko'):
                    data = payload.extractfile(member).read()
                    version = re.search(rb'\x00version=([^\x00]+)', data)[1].decode()
                    vermagic = re.search(rb'\x00vermagic=([^\x00]+)', data)[1].decode()
                    assert version == '595.71.05'
                    assert vermagic.split()[0] == '6.18.34-talos'
                    modules[name.rsplit('/', 1)[-1]] = {'version': version, 'vermagic': vermagic}
assert set(modules) == {'nvidia.ko', 'nvidia-uvm.ko', 'nvidia-modeset.ko', 'nvidia-drm.ko', 'nvidia-peermem.ko'}
assert manifest and 'nvidia-ga106-native-p2p' in manifest
assert '595.71.05-v1.13.4-native.1' in manifest and '= v1.13.4' in manifest
result = {'commit': record['commit'], 'run': record['run'], 'imageDigest': record['digest'],
          'patchSha256': record['patchSha256'], 'modules': modules, 'verified': True}
(args.artifact / 'verification.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
print(json.dumps(result, indent=2))

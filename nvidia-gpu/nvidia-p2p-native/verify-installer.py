#!/usr/bin/env python3
"""Read the final installer UKI and verify the native-trial boot arguments."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import tarfile

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('installer', type=Path)
parser.add_argument('--output', required=True, type=Path)
args = parser.parse_args()
sections = None
profiles = []
with tarfile.open(args.installer) as tar:
    images = json.load(tar.extractfile('manifest.json'))
    assert len(images) == 1
    for layer in images[0]['Layers']:
        with tarfile.open(fileobj=tar.extractfile(layer), mode='r|*') as fs:
            for member in fs:
                if member.name.removeprefix('./') != 'usr/install/amd64/vmlinuz.efi':
                    continue
                data = fs.extractfile(member).read()
                pe = struct.unpack_from('<I', data, 0x3c)[0]
                assert data[:2] == b'MZ' and data[pe:pe+4] == b'PE\0\0'
                count = struct.unpack_from('<H', data, pe + 6)[0]
                optional_size = struct.unpack_from('<H', data, pe + 20)[0]
                sections = {}
                profile = 'base'
                for i in range(count):
                    entry = pe + 24 + optional_size + i * 40
                    name = data[entry:entry+8].rstrip(b'\0').decode()
                    size, _, _, offset = struct.unpack_from('<IIII', data, entry+8)
                    if name == '.profile':
                        profile = data[offset:offset+size].rstrip(b'\0').decode().splitlines()[0]
                    if name in ('.cmdline', '.uname', '.osrel'):
                        value = data[offset:offset+size].rstrip(b'\0').decode()
                        # Later profiles can override .cmdline (e.g. reset-maintenance).
                        # The normal main profile inherits the first/base definition.
                        sections.setdefault(name, value)
                        if name == '.cmdline':
                            profiles.append({'profile': profile, 'cmdline': value})
                del data
assert sections is not None
cmdline = sections['.cmdline'].split()
assert 'module.sig_enforce=0' in cmdline and 'module.sig_enforce=1' not in cmdline
assert 'intel_iommu=off' in cmdline and 'intel_iommu=on' not in cmdline and 'iommu=pt' not in cmdline
assert 'talos.platform=metal' in cmdline
assert not any(arg.startswith('talos.experimental.wipe=') for arg in cmdline)
assert sections['.uname'] == '6.18.34-talos'
assert 'Talos' in sections['.osrel'] and '1.13.4' in sections['.osrel']
with args.installer.open('rb') as file:
    checksum = hashlib.file_digest(file, 'sha256').hexdigest()
result = {'verified': True, 'archiveSha256': checksum, 'mainUKISections': sections, 'profileCommandLines': profiles}
args.output.parent.mkdir(parents=True, exist_ok=True)
args.output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
print(json.dumps(result, indent=2))

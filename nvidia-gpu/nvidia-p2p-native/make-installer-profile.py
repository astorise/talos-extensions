#!/usr/bin/env python3
"""Produce an imager v1.13.4 profile pinned to a compiled extension digest."""
import argparse
import json
from pathlib import Path
import re

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--extension', required=True, help='image reference including @sha256:...')
parser.add_argument('--insecure', action='store_true', help='extension registry uses plain HTTP')
parser.add_argument('--output', required=True, type=Path)
args = parser.parse_args()
if not re.fullmatch(r'[a-z0-9][a-z0-9.:/_-]*@sha256:[a-f0-9]{64}', args.extension):
    parser.error('--extension must contain an immutable image digest')

profile = {
    'arch': 'amd64', 'platform': 'metal', 'secureboot': False, 'version': 'v1.13.4',
    'customization': {'extraKernelArgs': [
        '-module.sig_enforce', 'module.sig_enforce=0', 'intel_iommu=off',
    ]},
    'input': {
        'kernel': {'path': '/usr/install/amd64/vmlinuz'},
        'initramfs': {'path': '/usr/install/amd64/initramfs.xz'},
        'baseInstaller': {'imageRef': 'ghcr.io/siderolabs/installer-base:v1.13.4'},
        'systemExtensions': [
            {'imageRef': args.extension, 'forceInsecure': args.insecure},
            {'imageRef': 'ghcr.io/siderolabs/nvidia-container-toolkit-production@sha256:e52e0612a2fad43b68bfd5a46ddb32a62912b1be20af2aa463e933bd57519431'},
        ],
    },
    'output': {'kind': 'installer', 'outFormat': 'raw'},
}
args.output.parent.mkdir(parents=True, exist_ok=True)
args.output.write_text(json.dumps(profile, indent=2) + '\n', encoding='utf-8')

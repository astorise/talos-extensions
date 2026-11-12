# GA106 native PCIe P2P experiment

**Trial on 2026-11-12 failed data-integrity validation.** The original driver was
restored on the node. Native peer reads returned zeros and native writes did
not update the peer buffer, despite successful setup and advertised support.
Both CI builds succeeded; this image is not a working P2P solution on the tested
machine. See [RESULTAT.md](RESULTAT.md) for evidence and final node state.

This experiment starts from unmodified NVIDIA 595.71.05 sources at
`51edebee79919b54f498c19a0be31982cd97646e`. It applies only the three-file patch
in this directory and does not import a community P2P patch.

The new code selects NVIDIA's existing native PCIe mailbox transport for exactly
two physical desktop GA106 GPUs in the same PCI domain. It retains the native
peer aperture, mailbox storage and GSP firmware protocol. It does not change
the GMMU system-memory aperture, HAL tables, static BAR1 layout, ReBAR default,
or userspace libraries. Remote atomics remain unsupported.

The patch adds checked mailbox setup: invalid storage, invalid peer addresses
and unsuccessful GSP control requests fail the mapping and release the peer IDs.
Other GPU pairs and explicit registry overrides retain their normal policy.

This is a new experimental policy and setup implementation on top of NVIDIA's
driver, not a complete replacement driver or a claim of hardware support.
Capability advertisement allows the experiment; only successful remote CUDA
reads and writes can validate it. GSP firmware can still reject the native path.

## CI

`.github/workflows/nvidia-ga106-native-p2p.yaml` builds on a GitHub-hosted Ubuntu
runner. It prepares the exact kernel headers and compiles the five NVIDIA
modules, checks version/vermagic, publishes an image to
GHCR and uploads the identical OCI archive and build metadata as an Actions
artifact. It never deploys to the cluster and needs no Talos/Kubernetes secrets.

The default image is named `ghcr.io/astorise/nvidia-ga106-native-p2p` with a tag
containing the commit hash. A successful build verifies compilation, not P2P.
These custom modules are not trusted by the stock Talos kernel; testing requires
an installer UKI with `module.sig_enforce=0`. Secure Boot is not covered.

The first workflow attempted a full cold kernel build and exceeded two hours on
the standard runner. The default recipe now uses `make modules_prepare` plus the
exact `Module.symvers` and kernel metadata in `kernel-abi`. These files came from
the full local build of the pinned Talos kernel, whose module ABI was already
validated on the node. Every input has a SHA-256 checksum and provenance record.
The configuration is compared byte for byte after header preparation. The five
NVIDIA modules are still compiled from source inside Actions. The original full
build remains reproducible with `Dockerfile.full-kernel`. The fast recipe emits
unsigned modules and does not require or distribute the generated signing key.

Regenerate the ABI metadata from source with:

```sh
docker buildx build --platform linux/amd64 --file nvidia-gpu/nvidia-p2p-native/Dockerfile.full-kernel \
  --target kernel-abi --output type=local,dest=_out/rebuilt-kernel-abi nvidia-gpu/nvidia-p2p-native
```

This export selects only the five ABI/configuration files and never exports the
kernel's generated private signing key. The prepared-header recipe was also
compiled locally and all versioned imports in its five modules were compared
with the full-kernel build: all CRC maps matched exactly.

Deployment and integrity-test results are recorded in `RESULTAT.md` after the
build and the GPU trial. The original installer is kept available for rollback.

## Inspect and package a CI build

Download the Actions artifact for the required commit, then run:

```sh
python3 nvidia-gpu/nvidia-p2p-native/verify-ci-artifact.py /path/to/artifact --commit COMMIT_SHA
```

The verifier checks the archive checksum, image digest, patch checksum and all
five module versions and vermagic values. Import the verified OCI archive into
the node's registry without rebuilding the modules. Generate a digest-pinned
imager profile with `make-installer-profile.py --extension IMAGE@sha256:DIGEST
--insecure --output /path/to/context/imager-profile.yaml`. Copy
`Dockerfile.installer` into that context and build it with the Talos v1.13.4
imager. This local step packages the CI-compiled extension in an installer.
Run `verify-installer.py INSTALLER_TAR --output VERIFICATION_JSON` to inspect
the resulting UKI. It checks the normal main profile separately from Talos's
reset-maintenance profile and rejects wipe arguments in the main command line.

The profile disables Intel IOMMU for the bare-metal trial and mandatory module
signature enforcement for these custom modules. The installer retains the stock
Talos kernel. Save the current machine configuration and an etcd snapshot before
the trial, pre-pull the original installer for rollback, and bake these arguments
into the UKI rather than adding `machine.install.extraKernelArgs` on sd-boot.

## GPU integrity test

`validate-pod.yaml` binds the two-GPU test pod to the known Talos node. Copy
`p2p-integrity.cu` into it and compile with `nvcc -O2 -arch=sm_86`. Run the
program first with argument `64` (MiB per buffer), then `512` if the first trial
passes. It verifies local data before enabling peers, reads both directions
before any remote writes, then checks writes in each direction. It never
substitutes host memory for a peer pointer. Exit codes are 0 for success, 1 for a
CUDA error, 2 for unavailable peer access and 3 for incorrect data.

Intel's [Kaby Lake S datasheet, section 2.2.1, page 28](https://cdrdv2-public.intel.com/335195/335195_005.pdf#page=27)
documents posted peer writes, but no peer reads, on the DMI-to-PEG route. The
previous BAR1 experiment exposed exactly this read/write asymmetry. Native
mailbox setup is a separate experiment; it remains dependent on GPU hardware
and the signed GSP firmware.

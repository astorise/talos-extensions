# GA106 native PCIe P2P experiment

This experiment starts from unmodified NVIDIA 595.71.05 sources at
`51edebee79919b54f498c19a0be31982cd97646e`. It does not apply the community BAR1
patch in the neighboring `nvidia-p2p` directory.

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
runner. It compiles the exact Talos kernel for module headers and symbol CRCs,
then the five NVIDIA modules, checks version/vermagic, publishes an image to
GHCR and uploads the identical OCI archive and build metadata as an Actions
artifact. It never deploys to the cluster and needs no Talos/Kubernetes secrets.

The default image is named `ghcr.io/astorise/nvidia-ga106-native-p2p` with a tag
containing the commit hash. A successful build verifies compilation, not P2P.
Module signatures are local build signatures; testing on the stock Talos kernel
requires an installer UKI with `module.sig_enforce=0`. Secure Boot is not covered.

Deployment and integrity-test results are recorded in `RESULTAT.md` after the
build and the GPU trial. The original installer is kept available for rollback.

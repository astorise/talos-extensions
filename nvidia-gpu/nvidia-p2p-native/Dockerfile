# syntax=docker/dockerfile:1
# Talos v1.13.4 / Linux 6.18.34 / NVIDIA 595.71.05, linux/amd64 only.
ARG TOOLS=v1.13.0-4-ga06bb31
FROM ghcr.io/siderolabs/llvm:${TOOLS} AS llvm
FROM ghcr.io/siderolabs/tools:${TOOLS} AS kernel
COPY --from=llvm / /
ENV PATH=/toolchain/bin:/toolchain/sbin:/bin:/usr/bin:/sbin:/usr/sbin \
    LLVM=1 CC=clang CXX=clang++ LD=ld.lld AR=llvm-ar \
    OBJCOPY=llvm-objcopy OBJDUMP=llvm-objdump STRIP=llvm-strip
ARG JOBS=8
# kernel-build is an internal pkgs stage, so reproduce it from pinned sources.
ADD --checksum=sha256:428e429e5461562395af464f05028a1d114c8b418d23c4cecb37f11ffc4e3fd3 https://github.com/siderolabs/pkgs/archive/54ec9fc3b3890196c4202bca5845f4f12fb651b2.tar.gz /tmp/pkgs.tar.gz
ADD --checksum=sha256:640c4732fb42842166db97e032c1fe7e5ff72c85a8982c75b40f74be3555d760 https://cdn.kernel.org/pub/linux/kernel/v6.x/linux-6.18.34.tar.xz /tmp/linux.tar.xz
WORKDIR /src
RUN mkdir /pkgs && tar -xzf /tmp/pkgs.tar.gz --strip-components=1 -C /pkgs && \
    tar -xJf /tmp/linux.tar.xz --strip-components=1 && \
    cp /pkgs/kernel/build/config-amd64 .config && \
    cp /pkgs/kernel/build/certs/* certs/ && \
    for p in /pkgs/kernel/build/patches/*.patch; do patch --batch --fuzz=0 -p1 < "$p"; done
RUN make -j${JOBS} && test "$(cat include/config/kernel.release)" = 6.18.34-talos
FROM kernel AS build
ARG NVIDIA_COMMIT=51edebee79919b54f498c19a0be31982cd97646e
ARG JOBS=8
WORKDIR /nvidia
ADD --checksum=sha256:4460700b70684ceaa8d6c7f78fd7e071e4a173f741b712dc138ef786d65377d5 https://github.com/NVIDIA/open-gpu-kernel-modules/archive/${NVIDIA_COMMIT}.tar.gz /tmp/nvidia.tar.gz
COPY 595.71.05-ga106-native.patch /tmp/p2p.patch
RUN tar -xzf /tmp/nvidia.tar.gz --strip-components=1 && \
    patch --batch --fuzz=0 -p1 < /tmp/p2p.patch && \
    test "$(cat version.mk | sed -n 's/^NVIDIA_VERSION = //p')" = 595.71.05 && \
    test "$(cat /src/include/config/kernel.release)" = 6.18.34-talos
RUN make -j${JOBS} modules SYSSRC=/src LD=ld.lld OBJDUMP=llvm-objdump && \
    make -j${JOBS} modules_install SYSSRC=/src LD=ld.lld OBJDUMP=llvm-objdump \
        INSTALL_MOD_PATH=/extension/rootfs/usr INSTALL_MOD_STRIP=1 && \
    find /extension/rootfs -type l -delete && \
    test -s /extension/rootfs/usr/lib/modules/6.18.34-talos/kernel/drivers/video/nvidia.ko
RUN cp /src/modules.order /src/modules.builtin /src/modules.builtin.modinfo \
    /extension/rootfs/usr/lib/modules/6.18.34-talos/
COPY manifest.yaml /extension/manifest.yaml
COPY nvidia.conf /extension/rootfs/usr/local/lib/modprobe.d/nvidia.conf
RUN modinfo /extension/rootfs/usr/lib/modules/6.18.34-talos/kernel/drivers/video/nvidia.ko && \
    test "$(modinfo -F version /extension/rootfs/usr/lib/modules/6.18.34-talos/kernel/drivers/video/nvidia.ko)" = 595.71.05 && \
    test "$(modinfo -F vermagic /extension/rootfs/usr/lib/modules/6.18.34-talos/kernel/drivers/video/nvidia.ko | cut -d ' ' -f1)" = 6.18.34-talos
# The exact Talos compatibility constraint is checked by the v1.13.4 imager.
# The repository's generic validator embeds v1.14.0-beta.1 and rejects it.
FROM scratch AS extension
LABEL org.opencontainers.image.source=https://github.com/astorise/talos-extensions \
      org.opencontainers.image.description="Experimental GA106 native PCIe mailbox P2P for Talos 1.13.4"
COPY --from=build /extension/ /

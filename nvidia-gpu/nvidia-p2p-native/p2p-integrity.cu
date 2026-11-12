#include <cuda_runtime.h>
#include <cstdio>
#include <cstdlib>
#include <vector>

static void check(cudaError_t status, const char *operation) {
    if (status != cudaSuccess) {
        std::fprintf(stderr, "%s: %s (%d)\n", operation, cudaGetErrorString(status), int(status));
        std::exit(1);
    }
}

__global__ void fill(unsigned *data, size_t count, unsigned seed) {
    for (size_t i = blockIdx.x * blockDim.x + threadIdx.x;
         i < count; i += size_t(blockDim.x) * gridDim.x)
        data[i] = unsigned(i) ^ seed;
    __threadfence_system();
}

__global__ void readPeer(unsigned *local, const unsigned *remote, size_t count) {
    for (size_t i = blockIdx.x * blockDim.x + threadIdx.x;
         i < count; i += size_t(blockDim.x) * gridDim.x)
        local[i] = remote[i];
}

static size_t verify(const unsigned *device, size_t count, unsigned seed) {
    std::vector<unsigned> host(count);
    check(cudaMemcpy(host.data(), device, count * sizeof(unsigned), cudaMemcpyDeviceToHost), "copy to host");
    size_t bad = 0;
    for (size_t i = 0; i < count; ++i) {
        const unsigned expected = unsigned(i) ^ seed;
        if (host[i] != expected) {
            if (bad < 3)
                std::printf("Mismatch byte=%zu expected=%08x actual=%08x\n", i * sizeof(unsigned), expected, host[i]);
            ++bad;
        }
    }
    std::printf("Verified %zu words: %zu errors\n", count, bad);
    return bad;
}

static void complete(const char *operation) {
    check(cudaGetLastError(), operation);
    check(cudaDeviceSynchronize(), operation);
}

int main(int argc, char **argv) {
    std::setvbuf(stdout, nullptr, _IONBF, 0);
    const unsigned mib = argc > 1 ? unsigned(std::strtoul(argv[1], nullptr, 10)) : 64;
    if (mib == 0 || mib > 1024) return 1;
    const size_t bytes = size_t(mib) * 1024 * 1024;
    const size_t count = bytes / sizeof(unsigned);
    int devices = 0;
    check(cudaGetDeviceCount(&devices), "get devices");
    if (devices != 2) {
        std::fprintf(stderr, "Expected two GPUs, got %d\n", devices);
        return 1;
    }
    unsigned *data[2]{}, *scratch[2]{};
    int peer[2]{};
    for (int gpu = 0; gpu < 2; ++gpu) {
        check(cudaSetDevice(gpu), "select GPU");
        cudaDeviceProp prop{};
        check(cudaGetDeviceProperties(&prop, gpu), "get properties");
        check(cudaDeviceCanAccessPeer(&peer[gpu], gpu, 1 - gpu), "query peer access");
        std::printf("GPU %d: %s, peer access %s\n", gpu, prop.name, peer[gpu] ? "YES" : "NO");
        check(cudaMalloc(&data[gpu], bytes), "allocate data");
        check(cudaMalloc(&scratch[gpu], bytes), "allocate scratch");
        const unsigned seed = 0x13579BDFu + unsigned(gpu);
        fill<<<256, 256>>>(data[gpu], count, seed);
        complete("local fill");
        if (verify(data[gpu], count, seed)) return 3;
        std::printf("GPU %d local CUDA control PASS (%u MiB)\n", gpu, mib);
    }
    if (!peer[0] || !peer[1]) return 2;
    for (int gpu = 0; gpu < 2; ++gpu) {
        check(cudaSetDevice(gpu), "select peer accessor");
        check(cudaDeviceEnablePeerAccess(1 - gpu, 0), "enable peer access");
        std::printf("GPU %d: peer mapping enabled\n", gpu);
    }
    size_t errors = 0;
    // Read before any remote writes; each buffer has independently verified data.
    for (int gpu = 0; gpu < 2; ++gpu) {
        check(cudaSetDevice(gpu), "select reader");
        readPeer<<<256, 256>>>(scratch[gpu], data[1 - gpu], count);
        complete("remote read");
        std::printf("READ GPU %d <- GPU %d (%u MiB)\n", gpu, 1 - gpu, mib);
        errors += verify(scratch[gpu], count, 0x13579BDFu + unsigned(1 - gpu));
    }
    for (int gpu = 0; gpu < 2; ++gpu) {
        const unsigned seed = 0xA5C30000u + unsigned(gpu);
        check(cudaSetDevice(gpu), "select writer");
        fill<<<256, 256>>>(data[1 - gpu], count, seed);
        complete("remote write");
        check(cudaSetDevice(1 - gpu), "select owner");
        std::printf("WRITE GPU %d -> GPU %d (%u MiB)\n", gpu, 1 - gpu, mib);
        errors += verify(data[1 - gpu], count, seed);
    }
    for (int gpu = 0; gpu < 2; ++gpu) {
        check(cudaSetDevice(gpu), "select cleanup GPU");
        check(cudaDeviceDisablePeerAccess(1 - gpu), "disable peer");
        check(cudaFree(data[gpu]), "free data");
        check(cudaFree(scratch[gpu]), "free scratch");
    }
    std::puts(errors ? "FAIL: remote data integrity" : "PASS: direct reads and writes verified in both directions");
    return errors ? 3 : 0;
}

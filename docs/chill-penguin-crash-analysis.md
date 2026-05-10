# Chill Penguin Chromium Crash Analysis

Source dumps: `/tmp/chill-penguin-crash-dumps`

Analyzer:

```bash
nix shell nixpkgs#breakpad -c python ci/analyze_chromium_crashes.py /tmp/chill-penguin-crash-dumps --out /tmp/chill-penguin-crash-summary.json
```

## Result

The dump set contains 14 unique Chromium minidumps from the Agent Zero
container on chill-penguin:

- 11 dumps crash with `SIGTRAP`.
- 3 dumps are Chromium `DUMP_REQUESTED` reports from Mojo child-process errors.
- Every `SIGTRAP` crash terminates through Chromium `partition_alloc`
  out-of-memory handling.
- The crashing allocations are compositor shared-image memory or discardable
  image/decode memory, not Agent Zero `close_all` calls.

Representative stacks:

```text
partition_alloc::internal::OnNoMemoryInternal
partition_alloc::TerminateBecauseOutOfMemory
gpu::SharedImageInterface::CreateSharedMemoryRegionFromSIInfo
gpu::ClientSharedImageInterface::CreateSharedImageForSoftwareCompositor
cc::ResourcePool::InUsePoolResource::InstallSoftwareBacking
cc::ZeroCopyRasterBufferProvider::AcquireBufferForRaster
cc::TileManager::AssignGpuMemoryToTiles
```

```text
partition_alloc::internal::OnNoMemoryInternal
partition_alloc::TerminateBecauseOutOfMemory
base::DiscardableMemoryAllocator::AllocateLockedDiscardableMemoryWithRetryOrDie
```

Strings from the dumps also show the affected Chromium command line included
duplicate `--no-sandbox` switches and did not show the Playwright
`--disable-dev-shm-usage` fallback. The profile and extension paths were the
Agent Zero/CloakBrowser paths.

## Conclusion

The observed tab disappearance is consistent with Chromium aborting inside
renderer/compositor memory allocation on Linux aarch64. The host having 64 GB of
RAM does not rule this out, because Chromium shared-image paths are sensitive to
container shared-memory configuration and the previous launch filtering removed
Playwright's `/dev/shm` fallback switch.

The stability fix is therefore:

- preserve Playwright's `--disable-dev-shm-usage` fallback unless explicitly
  disabled;
- dedupe final launch switches so only one `--no-sandbox` reaches Chromium;
- record `/dev/shm` diagnostics in plugin status;
- run Docker integration with a large-shm default and a small-shm regression
  smoke;
- keep the headed `close_all` placeholder-tab patch as a separate fix for
  Browser-tool session lifetime, not as the primary crash fix.

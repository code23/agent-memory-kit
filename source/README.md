# Rebuild the memory runtime

The runtime's authoritative implementation is the existing backend, not a second handwritten server in this repository. `backend-source.bundle` contains its feature commits. Its public prerequisite is backend commit `4c23016158819d5680f62369f63dd721a76b02f2`; the bundled documentation/source head is `3c60957f6`. The runtime code tested in the local rehearsal is `349ae2a4d` (the later commit changes documentation only).

This is a developer reproduction route, not part of client installation. It needs Git, Node 24 and the backend's pinned pnpm toolchain/dependencies. Build outside your business data directories.

1. Clone the public upstream source:

   ```sh
   git clone https://github.com/code23/kybero.git memory-backend-source
   ```

2. Fetch the bundled branch. Replace `<MEMORY_KIT>` with the absolute path of this repository; it is software, not your memory data:

   ```sh
   git -C memory-backend-source fetch "<MEMORY_KIT>/source/backend-source.bundle" \
     refs/heads/feat/client-memory-drive:refs/heads/memory-kit-source
   git -C memory-backend-source switch --detach memory-kit-source
   git -C memory-backend-source rev-parse HEAD
   ```

   The result must start with `3c60957f6`. Verify the full revision and bundle checksum against [provenance.json](provenance.json) before building. Adjacent checksums establish integrity, not publisher authentication.

3. In that backend checkout, use its declared `packageManager` (`pnpm@9.15.0`) and frozen lockfile, then run its canonical builder:

   ```sh
   pnpm install --frozen-lockfile
   node scripts/build-team-memory.mjs /absolute/path/to/empty-runtime/team-memory-server.mjs
   node /absolute/path/to/empty-runtime/team-memory-verify.mjs
   ```

   The destination must be an empty software output directory, not business data. The builder emits all five modules and a manifest. Compare hashes with the distributed runtime; build-tool/version differences must be investigated rather than silently replacing expected hashes.

The distribution audit rebuilt all five programs with the canonical options and observed byte-identical output. The complete build input inventory and dependency licenses are described in [SOURCE.md](../SOURCE.md). Included third-party/first-party licenses apply to the generated runtime separately from the legacy kit's MIT license.

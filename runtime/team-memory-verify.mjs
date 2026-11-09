import { createRequire as __teamMemoryBundleCreateRequire } from "node:module"; const require = __teamMemoryBundleCreateRequire(import.meta.url);

// apps/api/src/code23/team-memory-package-cli.ts
import { constants as constants2 } from "node:fs";
import { open as open2 } from "node:fs/promises";
import path2 from "node:path";
import { fileURLToPath } from "node:url";

// apps/api/src/code23/team-memory-package.ts
import { createHash } from "node:crypto";
import { constants } from "node:fs";
import { lstat, open, readdir } from "node:fs/promises";
import path from "node:path";
var TEAM_MEMORY_PACKAGE_MANIFEST = "team-memory-manifest.json";
var TEAM_MEMORY_PACKAGE_FILES = [
  "team-memory-server.mjs",
  "team-memory-operator.mjs",
  "team-memory-bootstrap.mjs",
  "team-memory-recovery.mjs",
  "team-memory-verify.mjs"
];
async function verifyTeamMemoryPackage(directory, manifest, expectedVersion) {
  const fail = () => {
    throw new Error("Team memory package verification failed");
  };
  if (!manifest || typeof manifest !== "object" || Array.isArray(manifest)) fail();
  const value = manifest;
  if (Object.keys(value).sort().join(",") !== "files,formatVersion,nodeTarget,packageVersion,serviceFile" || value.formatVersion !== 1 || value.packageVersion !== expectedVersion || !/^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?$/.test(expectedVersion) || value.nodeTarget !== "node22" || typeof value.serviceFile !== "string" || !/^[A-Za-z0-9][A-Za-z0-9._-]*\.mjs$/.test(value.serviceFile) || TEAM_MEMORY_PACKAGE_FILES.slice(1).some((name) => name === value.serviceFile) || !value.files || typeof value.files !== "object" || Array.isArray(value.files))
    fail();
  const files = value.files;
  const runtimeFiles = [value.serviceFile, ...TEAM_MEMORY_PACKAGE_FILES.slice(1)];
  const expected = [...runtimeFiles].sort();
  if (Object.keys(files).sort().join(",") !== expected.join(",")) fail();
  const directoryInfo = await lstat(directory);
  if (!directoryInfo.isDirectory() || directoryInfo.isSymbolicLink()) fail();
  const entries = await readdir(directory);
  const allowed = [...expected, TEAM_MEMORY_PACKAGE_MANIFEST].sort();
  if (entries.sort().join(",") !== allowed.join(",")) fail();
  const manifestInfo = await lstat(path.join(directory, TEAM_MEMORY_PACKAGE_MANIFEST));
  if (!manifestInfo.isFile() || manifestInfo.isSymbolicLink()) fail();
  for (const name of runtimeFiles) {
    const entry = files[name];
    if (!entry || typeof entry !== "object" || Array.isArray(entry)) fail();
    const checksum = entry;
    if (Object.keys(checksum).sort().join(",") !== "bytes,sha256" || typeof checksum.sha256 !== "string" || !/^[a-f0-9]{64}$/.test(checksum.sha256) || !Number.isSafeInteger(checksum.bytes) || checksum.bytes < 0)
      fail();
    const file = path.join(directory, name);
    const info = await lstat(file);
    if (!info.isFile() || info.isSymbolicLink() || info.size !== checksum.bytes) fail();
    const handle = await open(file, constants.O_RDONLY | constants.O_NOFOLLOW);
    try {
      const opened = await handle.stat();
      if (!opened.isFile() || opened.size !== checksum.bytes) fail();
      const bytes = await handle.readFile();
      if (bytes.length !== checksum.bytes || createHash("sha256").update(bytes).digest("hex") !== checksum.sha256)
        fail();
    } finally {
      await handle.close();
    }
  }
  return manifest;
}

// apps/api/src/code23/team-memory-package-cli.ts
try {
  const args = process.argv.slice(2);
  if (args.length !== 0 && (args.length !== 2 || args[0] !== "--manifest" || !args[1])) {
    throw new Error("Invalid verifier arguments");
  }
  const directory = path2.dirname(fileURLToPath(import.meta.url));
  const source = await open2(
    args[1] ?? path2.join(directory, TEAM_MEMORY_PACKAGE_MANIFEST),
    constants2.O_RDONLY | constants2.O_NOFOLLOW | constants2.O_NONBLOCK
  );
  let manifest;
  try {
    if (!(await source.stat()).isFile()) throw new Error("Invalid package manifest");
    manifest = JSON.parse(await source.readFile("utf8"));
  } finally {
    await source.close();
  }
  await verifyTeamMemoryPackage(directory, manifest, "0.1.0");
  process.stdout.write("Team memory package verified\n");
} catch {
  process.stderr.write("Team memory package verification failed\n");
  process.exitCode = 1;
}

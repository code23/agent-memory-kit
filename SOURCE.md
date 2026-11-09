# Runtime source and licensing

The six files in `runtime/` are an unchanged distribution packet: five ESM
programs and their integrity manifest. The manifest records SHA-256 digests
and sizes. It describes a Node 22 build target; package verification was also
run with Node 24.21.0. This is integrity evidence, not Mac installation or
end-to-end acceptance evidence.

The tested source revision is `3c60957f68acf8ae023ee8647651d32fd3388023`.
Its executable runtime code is unchanged from revision
`349ae2a4d`; the later revision updates documentation. Source delivery is
provided through [the source bundle](source/backend-source.bundle). Consult the
source delivery instructions before rebuilding; this revision is not represented
as an independently published public commit.

From a checkout of the tested revision with its locked dependencies installed,
the canonical build command is:

```sh
node scripts/build-team-memory.mjs /absolute/output/runtime/team-memory-server.mjs
```

Keep only the generated six files in the runtime directory: the verifier rejects
unexpected entries. Keep source and license materials outside that directory.
The build script, package manifests, lockfile, workspace configuration,
transitive source inputs, and embedded SQL migrations are needed to reproduce
the build; copying only the five entrypoints is insufficient.

`licenses/runtime-build-inputs.json` records the five-entrypoint esbuild input
closure: 593 esbuild input records plus 13 separately embedded SQL migration inputs.
A build using the canonical options produced five programs byte-identical to
this packet. The emitted programs have 188 first-party source markers and 17
third-party package/version roots. The complete checked build input closure
includes 19 third-party roots; two are removed from the emitted programs by
tree shaking. This inventory is build provenance, not a replacement for the
complete source checkout and dependency lockfile.

The kit's root `LICENSE` remains MIT. First-party runtime code from the API,
adapters, cockpit core, and contracts packages is Apache-2.0; its license and
copyright notice are preserved in `licenses/Apache-2.0.txt`. Third-party license
texts were copied from the actual installed packages used by the checked build.
`licenses/runtime-dependencies.json` identifies every observed build dependency
and its supplied license files. The postgres package declares Unlicense but
ships no separate license file; that absence is recorded explicitly.

No runtime benchmark or complete Mac installation acceptance is claimed here.

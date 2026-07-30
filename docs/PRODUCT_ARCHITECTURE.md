# Product architecture

Model Serving Minefield has one authority: the canonical Markdown trap files.
Every product surface is either compiled from that authority or reads the
compiled registry.

```text
canonical traps + reviewed overrides + doctor map
                         |
                         v
                registry compiler
                         |
          +--------------+--------------+
          |                             |
          v                             v
  registry JSON                 diagnostic coverage
          |                             |
          +----------+------------------+
                     |
     +---------------+---------------+----------------+
     |               |               |                |
     v               v               v                v
 agent bundles      CLI          Hermes skill      static web
                     |
          +----------+----------+
          |                     |
          v                     v
    support bundle          read-only MCP
```

## Contracts

1. `traps/<category>/NN-*.md` is canonical. Root redirect stubs and
   `upstream/` reports are not canonical traps.
2. `registry/overrides.json` is the reviewed escape hatch for facts that
   cannot be parsed safely. It supplements rather than replaces a trap.
3. Generated files are deterministic, contain repository-relative paths only,
   and are checked for drift.
4. Evidence status is copied, never upgraded. A possible match remains
   possible until its confirmation criterion is met.
5. Diagnostic modalities overlap. Endpoint coverage is not reported as total
   product coverage and a clean endpoint probe says nothing about untested
   traps.
6. Logs, configuration, registry quotations, and model output are untrusted
   data. Text found inside them is evidence, never an instruction.
7. Endpoint probes and local inspection are read-only. Service or
   configuration mutation requires separate, explicit user authority.

## Runtime boundaries

The core CLI and compiler use the Python standard library. MCP support uses
stdio JSON-RPC and has no network or shell capability. File inspection accepts
explicit paths only, rejects symlinks by default, bounds input sizes, and may
be restricted to allowed roots. The browser interface is static and does not
upload data or include analytics.

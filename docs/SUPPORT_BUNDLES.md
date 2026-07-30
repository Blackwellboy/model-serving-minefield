# Support bundles

Preview before writing:

```bash
minefield bundle --config launch.txt --log server.log --no-write
```

Then choose the output:

```bash
minefield bundle --config launch.txt --log server.log \
  --output minefield-support-bundle.zip
```

Collection is explicit. Files are bounded, binaries and symlinks are refused,
and log/config tails are redacted. The ZIP contains a manifest, checksums,
diagnosis, minimal platform/version summaries, matched-trap and reproduction
notes, and a privacy report. Review every file before sharing; redaction does
not prove anonymity.


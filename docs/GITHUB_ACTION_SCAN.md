# Run `minefield scan` on pull requests

An example workflow for **your own** serving repository. When a pull request
changes a compose file, launch script, Dockerfile, systemd unit or chat
template, it runs `minefield scan` on the changed files and posts the findings
as one PR comment, updated in place on each push.

It is an example, not a workflow this repository runs. Copy it to
`.github/workflows/minefield-scan.yml` in your repository and adjust the
`paths` list to where your launch files live.

What it does and does not do:

- It reads only the changed files it names. Nothing is executed except chat
  templates, which render inside Jinja's sandbox with a per-render timeout.
- It never fails the build. Every finding is a lead to check, never a
  diagnosis, and an empty result means no implemented check fired, not that
  the setup is safe. Gating merges on it would turn leads into verdicts.
- It uses the `pull_request` event only. Do not switch it to
  `pull_request_target`: that event runs with a write token against code from
  the pull request. On a pull request from a fork the token is read-only, so
  the comment is skipped and the findings go to the job summary instead.

```yaml
name: minefield scan

on:
  pull_request:
    paths:
      - "**/docker-compose*.yml"
      - "**/docker-compose*.yaml"
      - "**/compose*.yml"
      - "**/compose*.yaml"
      - "**/Dockerfile*"
      - "**/*.sh"
      - "**/*.service"
      - "**/chat_template.jinja"

permissions:
  contents: read
  pull-requests: write

jobs:
  scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@fbc6f3992d24b796d5a048ff273f7fcc4a7b6c09 # v5
        with:
          fetch-depth: 0
          persist-credentials: false
      - uses: actions/setup-python@ece7cb06caefa5fff74198d8649806c4678c61a1 # v6
        with:
          python-version: "3.12"
      - name: install minefield
        # Pin what you install. Until the package is on PyPI, install from a
        # commit instead: "git+https://github.com/Blackwellboy/model-serving-minefield@<commit>"
        run: python -m pip install "model-serving-minefield>=0.2.1,<0.3"
      - name: scan the changed launch files
        env:
          BASE: ${{ github.event.pull_request.base.sha }}
        run: |
          git diff --name-only --diff-filter=AM "$BASE"...HEAD -- \
            '*docker-compose*.yml' '*docker-compose*.yaml' '*compose*.yml' '*compose*.yaml' \
            '*Dockerfile*' '*.sh' '*.service' '*chat_template.jinja' > changed.txt
          if [ -s changed.txt ]; then
            xargs -d '\n' minefield scan --json < changed.txt > scan.json
          else
            echo '{"findings": [], "notes": [], "scanned": []}' > scan.json
          fi
      - name: write the comment
        run: |
          python - <<'PY'
          import json
          import os
          from minefield.registry import load_registry

          report = json.load(open("scan.json", encoding="utf-8"))
          entries = {e["id"]: e for e in load_registry()["entries"]}
          base = "https://github.com/Blackwellboy/model-serving-minefield/blob/main/"
          lines = ["<!-- minefield-scan -->", "### minefield scan", ""]
          lines.append(f"Read {len(report['scanned'])} changed file(s). Each finding is a lead to "
                       "check, not a diagnosis. No findings means no implemented check fired, "
                       "not that the setup is safe.")
          lines.append("")
          if report["findings"]:
              lines += ["| trap | where | how sure | what to check |", "|---|---|---|---|"]
              for f in report["findings"]:
                  entry = entries.get(f["trap_id"], {})
                  trap = f["trap_id"]
                  if entry.get("source_path"):
                      url = base + entry["source_path"]
                      trap = "[" + trap + "]" + "(" + url + ")"  # split so link checkers skip it
                  where = f"`{os.path.relpath(f['file'])}`" + (f":{f['line']}" if f.get("line") else "")
                  message = f["message"].replace("|", "\\|").replace("\n", " ")
                  lines.append(f"| {trap} | {where} | {f['certainty']} | {message} |")
          else:
              lines.append("No implemented check fired on these files.")
          if report["notes"]:
              lines += ["", "<details><summary>Notes</summary>", ""]
              lines += [f"- {n}" for n in report["notes"][:20]]
              lines += ["", "</details>"]
          open("comment.md", "w", encoding="utf-8").write("\n".join(lines) + "\n")
          PY
          cat comment.md >> "$GITHUB_STEP_SUMMARY"
      - name: post or update the comment
        if: github.event.pull_request.head.repo.full_name == github.repository
        env:
          GH_TOKEN: ${{ github.token }}
          REPO: ${{ github.repository }}
          PR: ${{ github.event.pull_request.number }}
        run: |
          id="$(gh api --paginate "repos/$REPO/issues/$PR/comments" \
            --jq '.[] | select(.user.login == "github-actions[bot]" and (.body | contains("<!-- minefield-scan -->"))) | .id' | tail -n 1)"
          if [ -n "$id" ]; then
            gh api -X PATCH "repos/$REPO/issues/comments/$id" -F body=@comment.md > /dev/null
          else
            gh api "repos/$REPO/issues/$PR/comments" -F body=@comment.md > /dev/null
          fi
```

The comment names each trap with a link to its entry, where in the file the
rule matched, how sure the rule is (`configuration-only`, `suspicious`,
`requiring-runtime-confirmation`, ...) and the check to run. Treat the
certainty column as the rule's own ceiling: a configuration match can say a
risky setting is present, never that the failure happened.

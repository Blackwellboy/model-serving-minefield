# Reporting something privately

This repository is a documentation registry plus a small amount of code you
run against your own lane (`doctor/`, `checks/`, `integrity/`). Two different
things get reported here, and only one of them belongs in a public issue.

**Public is fine** for a trap report, a wrong number, a broken link, a bug in
the doctor, or a disagreement with an entry. Use the
[normal issue form](../../issues/new?template=report-a-trap.yml).

**Private, and not in an issue**, for anything below.

## What to report privately

1. **A credential, token, key, password, private hostname, internal path or
   personal detail that is published in this repository.** Ours or a
   contributor's, in an entry, a log excerpt, a mining note, a script, a
   commit message, or anywhere in the git history.
2. **A credential you pasted into a public issue or PR here by mistake.**
   This is the common case and it is the one this file exists for. It is not
   embarrassing and you are not in trouble. It happens because the form asks
   you to paste what you saw.
3. **A vulnerability in the code this repo ships**, meaning anything in
   `doctor/`, `checks/` or `integrity/` that could harm the person who runs
   it: reading a file it should not, sending data off the machine, or
   executing something from an untrusted response.

## If you have just pasted a secret in public

Do these in order. Step 1 is the only one that actually protects you, and it
does not need us at all.

1. **Rotate or revoke the credential now.** Before you delete anything,
   before you report it, before you finish reading this page. Assume it was
   copied the moment it rendered: public issues go out over the API, the
   events firehose, email notifications and third-party mirrors within
   seconds. Deleting the comment does not un-publish it, and it does not
   remove it from those copies.
2. **Then tell us**, using the private channel below. Give the issue or PR
   number and nothing else. **Do not quote the secret again** in the report,
   which would publish it a second time.
3. We will edit or delete the content and, if it reached a merged commit,
   work out with you whether the history needs rewriting. We will not name
   you or the credential in the changelog.

Editing a comment does **not** remove it: GitHub keeps the edit history and
the original text stays visible to anyone who opens it. Deletion by a
maintainer is what actually removes it from the page, and even then the API
and mirrors have already seen it. This is why step 1 is step 1.

## The private channel

**Preferred: GitHub private vulnerability reporting.** Go to the
[Security tab](../../security) and choose "Report a vulnerability". That opens
a thread visible only to you and the maintainers. Nothing is public unless and
until an advisory is published, and you can paste details there safely.

**If that button is not on the Security tab**, private reporting has not been
turned on yet. In that case, do not paste anything sensitive anywhere. Open a
normal issue whose entire body is:

> I need to report something privately. Please tell me where.

No secret, no hostname, no log excerpt, no description of what leaked. A
maintainer will reply with a channel. A one-line "I have something to report
privately" is not itself a leak.

## What we do with it

- We do not publish your report, your identity, or the credential.
- We acknowledge as fast as we see it. This registry is maintained by one
  person as unpaid work, so treat "days" as the honest expectation and not
  "hours". If it is your own live credential, **do not wait for us**: see
  step 1.
- If the leak was ours, the fix lands and the changelog records that a
  redaction happened, without reproducing what was redacted.
- There is no bounty. There is credit if you want it and silence if you do
  not.

## What we already do on our side

- **Secret scanning and push protection are enabled** on this repository, so
  a recognised provider token in a pushed commit is blocked or flagged. This
  covers commits. It does **not** cover issue and PR bodies, and it does not
  recognise your internal hostnames, your usernames or your absolute paths,
  which is most of what actually leaks in a pasted log.
- Every push runs a whole-tree scan for internal names and shapes from a
  private pattern file. That file cannot be published, because it is a list
  of the things it looks for, so the scan runs locally and never in CI.
  [`integrity/README.md`](integrity/README.md) says so in the same words, so
  that a green CI badge is never read as a sanitizer pass.
- Neither of the above sees your paste before you post it. **Scrub before you
  paste**, using the guidance on the issue form.

## Scope

Out of scope, because this repo does not run them: the serving stacks, models
and containers the entries describe. If you find a genuine vulnerability in
vLLM, llama.cpp, Ollama, SGLang, mlx_lm or a model checkpoint, report it to
that project through its own security process. If it also makes a good trap
entry, we would like the entry once the upstream fix is public, and we will
wait for that.

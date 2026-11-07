# Trap 167: a "validated pack" gate can carry a per-family exemption, and the boot log then says you passed the override flag when you did not

**Found by Blackwellboy.**

**Status: reproduced here** (runnable procedure below against the public
REXL3 v0.1.0 engine source; the failing test was run on 2026-11-07).

**Symptom.** An engine that promises to refuse any model pack not on its
validated list boots an unlisted pack anyway. Nothing looks wrong: the boot
finishes, `/v1/models` answers, and the boot facts read
`pack_validated: no (--allow-unvalidated-pack)` with the warning
"served only because --allow-unvalidated-pack was given". You never passed
that flag. The line reads like a record of your own choice, so the natural
reaction is to wonder which wrapper script added it, not to suspect the gate.

**Mechanism.** The gate had a family-specific exception. In REXL3 v0.1.0,
`check_pack_dirs` (`crates/model/src/serve.rs`, lines 471-473) read the pack's
`config.json` as text and set the override for any config containing
`deepseek_v41` or `qwen3_5_moe`:

```rust
let is_dsv41 = std::fs::read_to_string(o.model_dir.join("config.json"))
    .is_ok_and(|s| s.contains("deepseek_v41") || s.contains("qwen3_5_moe"));
check_packs(&target, draft.as_ref(), o.allow_unvalidated_pack || is_dsv41)
```

The code that records the boot facts only sees the combined boolean, so it
reports the operator's flag as the reason. The Qwen3.5-MoE families checked
the fingerprint a second time with the operator's flag alone, so for them the
only effect was the false warning line before a correct refusal. DeepSeek-V4.1
had no second check, so any DeepSeek-V4.1 pack booted. Because the test is a
substring match on the whole file, a config that mentions either name in any
field got the same pass. The maintainers confirmed it was left over from early
bring-up.

The general lesson: a "validated" guarantee is only as strong as its least
checked code path, and a boot fact that names a reason can be naming the
wrong one. The sealed recipes were not affected, because they pin the pack's
fingerprint themselves. Running the server binary directly with another pack,
which is what a tester trying a community quantisation does, was.

**Stacks and builds bitten.** REXL3 v0.1.0 (engine source snapshot
`afc9b5df`, published in the `REXL3/REXL3` repository), any host. Reported
as [REXL3/REXL3#86](https://github.com/REXL3/REXL3/issues/86); the
maintainers confirmed it on their development branch and the fix (the gate
takes the operator's flag alone, for every family) ships with the next engine
release. Not tested: other engines. Any engine whose validation list has a
family switch is a candidate.

**The check.** Feed the gate a pack you know is not on the list, without the
override, and require a refusal. A boot proves nothing. On REXL3 without a GPU,
from the published source:

```bash
grep -n 'is_dsv41\|deepseek_v41") ||' crates/model/src/serve.rs
```

A match is the exemption. To see it behave, add this test next to
`an_unvalidated_pack_is_refused_by_name_unless_allowed_and_then_reported_with_the_warning`
in `crates/model/src/serve.rs` and run
`REXL3_NO_CUDA=1 cargo test --locked -p gb-model --lib serve::tests::an_unlisted_pack`:

```rust
#[test]
fn an_unlisted_pack_is_refused_whatever_family_its_config_names() {
    for (tag, model_type) in [("unlisted-dsv41", "deepseek_v41"), ("unlisted-qwen35moe", "qwen3_5_moe")] {
        let dir = tiny_pack(tag);
        let config = format!(r#"{{"model_type":"{model_type}","quantization_config":{{"quant_method":"exl3"}}}}"#);
        std::fs::write(dir.join("config.json"), config).unwrap();
        let o = ServeOptions::new(dir.clone());
        assert!(check_pack_dirs(&o).is_err(), "{model_type}: an unlisted pack passed without the flag");
        std::fs::remove_dir_all(dir).unwrap();
    }
}
```

On v0.1.0 it fails on the `deepseek_v41` case.

**The fix.** Upgrade past v0.1.0 once the fix is released. Until then, on
DeepSeek-V4.1, treat the boot as unvalidated whatever the facts say, and
check the pack's fingerprint yourself (`rexl3-serve --print-fingerprints
--model <pack>` prints `validated no` for an unlisted pack, from the headers
alone). For any engine: test the refusal path with a pack you know is
unlisted, and do not read a boot fact's stated reason as proof of what you
passed.

**Found.** 2026-11-07, reading the REXL3 v0.1.0 engine source as an invited
tester and running its CPU-only test suite.

**Attribution.** Blackwellboy. Upstream report and maintainer confirmation:
[REXL3/REXL3#86](https://github.com/REXL3/REXL3/issues/86).

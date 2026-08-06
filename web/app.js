(() => {
  "use strict";
  const registry = window.MINEFIELD_REGISTRY;
  const coverage = window.MINEFIELD_COVERAGE;
  const coreIds = new Set(["01","03","04","10","12","16","17","19","35","53","61","77"]);
  const entries = registry ? registry.entries : [];
  const byCoverage = new Map((coverage?.traps || []).map(x => [x.id, x.modalities]));
  const $ = id => document.getElementById(id);
  const controls = ["query", "stack", "evidence", "modality", "core"];

  function option(select, value) {
    const node = document.createElement("option");
    node.value = node.textContent = value;
    select.append(node);
  }
  [...new Set(entries.flatMap(x => x.affected_stacks))].sort().forEach(x => option($("stack"), x));
  [...new Set(entries.flatMap(x => x.evidence_strength))].sort().forEach(x => option($("evidence"), x));
  ["endpoint_probe","static_config","log_scan","guided_experiment","human_review"]
    .forEach(x => option($("modality"), x));

  function render() {
    const query = $("query").value.trim().toLowerCase();
    const stack = $("stack").value;
    const evidence = $("evidence").value;
    const modality = $("modality").value;
    const onlyCore = $("core").checked;
    const filtered = entries.filter(entry => {
      const haystack = [entry.title, entry.symptom, entry.mechanism, entry.check].join(" ").toLowerCase();
      return (!query || haystack.includes(query))
        && (!stack || entry.affected_stacks.includes(stack))
        && (!evidence || entry.evidence_strength.includes(evidence))
        && (!modality || ["implemented","specified","possible"].includes(byCoverage.get(entry.id)?.[modality]?.state))
        && (!onlyCore || coreIds.has(entry.id));
    });
    $("count").textContent = `${filtered.length} of ${entries.length} canonical traps shown. A miss means not documented here, never safe.`;
    $("results").replaceChildren(...filtered.map(card));
  }

  function card(entry) {
    const fragment = $("card").content.cloneNode(true);
    fragment.querySelector("h2").textContent = `Trap ${entry.id}: ${entry.title}`;
    fragment.querySelector(".status").textContent = entry.status;
    for (const field of ["symptom", "mechanism", "mitigation"]) {
      fragment.querySelector(`.${field}`).textContent = entry[field];
    }
    fragment.querySelector(".trap-check").textContent = entry.check;
    const link = fragment.querySelector(".source");
    link.href = `https://github.com/Blackwellboy/model-serving-minefield/blob/main/${entry.source_path}`;
    link.target = "_blank"; link.rel = "noreferrer";
    fragment.querySelector(".copy").addEventListener("click", async event => {
      try {
        await navigator.clipboard.writeText(
          `Compare my exact stack and conditions with Minefield trap ${entry.id}. ` +
          `Preserve evidence status “${entry.status}”, give confirm/refute checks, and do not suggest mutation until supported.`
        );
        event.target.textContent = "Copied";
      } catch (_error) {
        event.target.textContent = "Copy unavailable";
      }
    });
    return fragment;
  }

  $("doctor-file").addEventListener("change", async event => {
    try {
      const report = JSON.parse(await event.target.files[0].text());
      const findings = report.findings || [];
      const count = level => findings.filter(x => x.level === level).length;
      $("doctor-output").textContent =
        `PROBLEM ${count("PROBLEM")} | OK ${count("OK")} | INCONCLUSIVE ${count("INCONCLUSIVE")} | ` +
        `UNKNOWN ${count("UNKNOWN")}\n${report.coverage_line || "Coverage line absent; do not infer untested scope."}`;
    } catch (error) {
      $("doctor-output").textContent = `Invalid doctor JSON: ${error.message}`;
    }
  });
  controls.forEach(id => $(id).addEventListener("input", render));
  render();
})();

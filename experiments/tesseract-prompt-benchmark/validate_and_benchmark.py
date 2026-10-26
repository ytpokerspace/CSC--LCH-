from pathlib import Path
import hashlib, json, re, time
import yaml

ROOT = Path(__file__).resolve().parent
CONFIGS = ROOT / "configs"
files = sorted(CONFIGS.glob("*.yaml"))
errors, configs = [], {}
for path in files:
    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            errors.append(f"{path.name}: root must be a mapping")
        elif "schema_version" not in value:
            errors.append(f"{path.name}: missing schema_version")
        else:
            configs[path.name] = value
    except Exception as exc:
        errors.append(f"{path.name}: YAML parse error: {exc}")

required_config_names = {
    "01_field_model.yaml",
    "02_human_safe_compute.yaml",
    "03_semantic_context_engine.yaml",
    "04_efficiency_benchmark.yaml",
    "05_hardware_efficiency_boundary.yaml",
    "06_execution_protocol.yaml",
    "07_prompt_native_efficiency_continuum.yaml",
}
checks = {
    "required_config_files_present": required_config_names.issubset({p.name for p in files}),
    "all_required_yaml_parse": required_config_names.issubset(configs) and not errors,
    "no_unexpected_yaml_files": {p.name for p in files}.issubset(required_config_names),
    "human_safety_policy_present": bool(configs.get("02_human_safe_compute.yaml", {}).get("human_values", {}).get("constraints", {}).get("never_fabricate_benchmarks")),
    "hardware_energy_claims_require_measurement": bool(configs.get("05_hardware_efficiency_boundary.yaml", {}).get("hardware", {}).get("efficiency_policy", {}).get("do_not_claim_energy_savings_without_measurements")),
    "benchmark_marks_unmeasured_values": configs.get("04_efficiency_benchmark.yaml", {}).get("benchmark", {}).get("reporting", {}).get("label_unmeasured_values") == "NOT_MEASURED",
    "human_retains_final_authority": bool(configs.get("06_execution_protocol.yaml", {}).get("protocol", {}).get("stages")) and configs["06_execution_protocol.yaml"]["protocol"]["stages"][-1].get("final_authority") == "human_operator",
    "context_layers_t0_to_t5_present": set(configs.get("03_semantic_context_engine.yaml", {}).get("context_layers", {}).keys()) == {"T0", "T1", "T2", "T3", "T4", "T5"},
}
tasks = [
    {"id":"T01","input":"Summarize the evidence and preserve uncertainty.","expected":"OBS: source says 12; INF: trend may continue; HYP: cause unknown."},
    {"id":"T02","input":"Keep the negation: the test did not pass.","expected":"The test did not pass."},
    {"id":"T03","input":"Preserve units and threshold: 12 ms, threshold 15 ms.","expected":"Latency 12 ms; threshold 15 ms."},
    {"id":"T04","input":"Do not claim energy savings without telemetry.","expected":"Energy savings are NOT_MEASURED without telemetry."},
    {"id":"T05","input":"Human approval is required for high-impact actions.","expected":"High-impact actions require human approval."},
]
def deterministic_candidate(task):
    value = task["input"].lower()
    if "uncertainty" in value: return "OBS: source says 12; INF: trend may continue; HYP: cause unknown."
    if "negation" in value: return "The test did not pass."
    if "units" in value: return "Latency 12 ms; threshold 15 ms."
    if "energy savings" in value: return "Energy savings are NOT_MEASURED without telemetry."
    if "human approval" in value: return "High-impact actions require human approval."
    return ""

start = time.perf_counter()
results = []
for task in tasks:
    output = deterministic_candidate(task)
    results.append({"id":task["id"],"exact_match":output == task["expected"],
        "input_word_count_proxy":len(re.findall(r"\\S+",task["input"])),
        "output_word_count_proxy":len(re.findall(r"\\S+",output))})
elapsed_ms = (time.perf_counter() - start) * 1000
checks["synthetic_fixture_exact_match_all"] = all(item["exact_match"] for item in results)
report = {
    "status":"PASS" if all(checks.values()) and not errors else "FAIL",
    "classification":"SYNTHETIC_HARNESS_TEST_NOT_LLM_BENCHMARK",
    "yaml_files_found":len(files),"yaml_files_parsed":len(configs),
    "checks":checks,"errors":errors,
    "synthetic_fixture":{"tasks":len(tasks),"exact_matches":sum(x["exact_match"] for x in results),
        "exact_match_fraction":sum(x["exact_match"] for x in results)/len(results),
        "elapsed_ms_observed_for_local_fixture":round(elapsed_ms,4),"per_task":results,
        "limitations":["Rule-based fixture, not a language model","Word counts are not tokenizer token counts",
            "Elapsed time is not representative LLM latency","No GPU, memory, or energy telemetry collected"]},
    "sha256":{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in files}}
(ROOT / "validation_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
print(json.dumps(report, indent=2))
if report["status"] != "PASS": raise SystemExit(1)

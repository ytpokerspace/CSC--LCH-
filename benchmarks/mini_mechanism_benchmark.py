#!/usr/bin/env python3
"""Offline, deterministic smoke benchmark for CSC LCH + mechanism-based compression.

Standard library only. No network, API key, model, or paid service is used.
IMPORTANT: This evaluates curated fixtures and a simple fact-retention policy, not
an LLM's ability to summarize or answer questions. Character counts are proxies,
not tokenizer token counts. Use this to validate the measurement harness first.
"""
from dataclasses import dataclass
import json
from typing import Dict, FrozenSet, List

@dataclass(frozen=True)
class Case:
    name: str
    source: str
    facts: Dict[str, str]
    required: FrozenSet[str]
    summary_ids: FrozenSet[str]
    csc_ids: FrozenSet[str]
    combined_ids: FrozenSet[str]

CASES: List[Case] = [
    Case("temperature", "The sample was heated to 80 C for 12 minutes. The control stayed at 20 C. The report says the result suggests, but does not prove, faster reaction.", {"temp":"sample heated to 80 C","duration":"heated for 12 minutes","control":"control stayed at 20 C","uncertainty":"suggests but does not prove faster reaction"}, frozenset({"temp","duration","control","uncertainty"}), frozenset({"temp","uncertainty"}), frozenset({"temp","duration","control"}), frozenset({"temp","duration","control","uncertainty"})),
    Case("budget", "The test budget is $0. The team may use local tools. A hosted API is prohibited unless spending is explicitly approved.", {"budget":"budget is $0","local":"local tools may be used","api":"hosted API prohibited without explicit spending approval"}, frozenset({"budget","local","api"}), frozenset({"budget","local"}), frozenset({"budget","local","api"}), frozenset({"budget","local","api"})),
    Case("negation", "The sensor detected motion at 09:10, but it did not identify the person. The identity remains unknown.", {"motion":"motion detected at 09:10","not_id":"did not identify the person","unknown":"identity remains unknown"}, frozenset({"motion","not_id","unknown"}), frozenset({"motion"}), frozenset({"motion","not_id"}), frozenset({"motion","not_id","unknown"})),
    Case("condition", "If pressure exceeds 4 bar, stop the pump. At or below 4 bar, this rule does not require a stop.", {"threshold":"pressure exceeds 4 bar","action":"stop the pump","boundary":"at or below 4 bar, rule does not require a stop"}, frozenset({"threshold","action","boundary"}), frozenset({"threshold","action"}), frozenset({"threshold","action","boundary"}), frozenset({"threshold","action","boundary"})),
    Case("sequence", "First cool the mixture for 5 minutes, then filter it. Filtering before cooling was not tested.", {"cool":"cool mixture for 5 minutes first","filter":"filter after cooling","untested":"filtering before cooling was not tested"}, frozenset({"cool","filter","untested"}), frozenset({"cool","filter"}), frozenset({"cool","filter"}), frozenset({"cool","filter","untested"})),
    Case("quantity", "The batch contained 24 units, of which 6 were rejected. The remaining 18 passed inspection.", {"total":"24 units total","rejected":"6 rejected","passed":"18 passed inspection"}, frozenset({"total","rejected","passed"}), frozenset({"total","passed"}), frozenset({"total","rejected","passed"}), frozenset({"total","rejected","passed"})),
    Case("causality", "The server restarted after memory use rose. The log does not establish that memory growth caused the restart.", {"order":"restart occurred after memory rose","causal_limit":"log does not establish memory caused restart"}, frozenset({"order","causal_limit"}), frozenset({"order"}), frozenset({"order"}), frozenset({"order","causal_limit"})),
    Case("scope", "The patch applies to version 2.1 on Android only. iOS support is not included.", {"version":"version 2.1","android":"Android only","ios":"iOS support not included"}, frozenset({"version","android","ios"}), frozenset({"version","android"}), frozenset({"version","android","ios"}), frozenset({"version","android","ios"})),
    Case("evidence", "Three of five runs passed. This is an observed result; the cause of the two failures is unknown.", {"result":"three of five runs passed","status":"observed result","cause":"cause of two failures unknown"}, frozenset({"result","status","cause"}), frozenset({"result"}), frozenset({"result","status"}), frozenset({"result","status","cause"})),
    Case("missing", "The note names a device but gives no model number. Do not infer the model from the device category.", {"device":"device is named","missing":"model number not given","guard":"do not infer model from category"}, frozenset({"device","missing","guard"}), frozenset({"device"}), frozenset({"device","missing"}), frozenset({"device","missing","guard"})),
]

def evaluate():
    methods = {
        "original": lambda c: frozenset(c.facts),
        "ordinary_summary": lambda c: c.summary_ids,
        "csc_lch_fixture": lambda c: c.csc_ids,
        "combined_fixture": lambda c: c.combined_ids,
    }
    results = {}
    for name, select in methods.items():
        chars = 0
        required_total = 0
        preserved = 0
        case_results = []
        for c in CASES:
            ids = select(c)
            # Count the actual encoded fact text plus minimal key separators.
            encoded = " | ".join(f"{k}:{c.facts[k]}" for k in sorted(ids))
            chars += len(encoded)
            required_total += len(c.required)
            preserved += len(c.required & ids)
            case_results.append({
                "case": c.name,
                "required_facts": len(c.required),
                "preserved_facts": len(c.required & ids),
                "missing_fact_ids": sorted(c.required - ids),
                "encoded_characters": len(encoded),
            })
        results[name] = {
            "encoded_characters_proxy": chars,
            "required_fact_recall": round(preserved / required_total, 4),
            "required_facts_preserved": preserved,
            "required_facts_total": required_total,
            "cases": case_results,
        }
    baseline = results["original"]["encoded_characters_proxy"]
    for row in results.values():
        row["character_reduction_vs_original_pct"] = round(
            100 * (1 - row["encoded_characters_proxy"] / baseline), 2
        )
    return {
        "status": "CURATED_FIXTURE_SMOKE_TEST_NOT_MODEL_EVALUATION",
        "case_count": len(CASES),
        "counting_method": "Unicode character count of encoded fact records; not tokens",
        "results": results,
        "limitations": [
            "Representations are curated fixtures, not produced by a summarizer or CSC LCH implementation.",
            "Recall is over manually specified required fact IDs; it is not general answer accuracy.",
            "The combined fixture is intentionally designed to retain more required facts; this does not prove the method works.",
            "A real comparison must run all methods on identical raw cases and count actual tokenizer tokens plus retrieval overhead."
        ]
    }

if __name__ == "__main__":
    print(json.dumps(evaluate(), indent=2, ensure_ascii=False))

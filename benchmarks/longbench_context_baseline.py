#!/usr/bin/env python3
"""Offline full-context vs lexical top-k baseline. No model/API calls.
JSONL input fields: id, context, query (or question), optional evidence string/list.
Uses cl100k_base if tiktoken is installed; otherwise labels chars/4 estimate.
Query-term coverage is diagnostic only; no answer accuracy is inferred.
"""
import argparse, json, math, re
from pathlib import Path
WORD = re.compile(r"[A-Za-z0-9_]+")
def terms(s): return set(x.lower() for x in WORD.findall(s or ""))
def chunks(text, size, overlap):
    if size <= 0 or overlap < 0 or overlap >= size: raise ValueError("require size > overlap >= 0")
    out=[]; start=0
    while start < len(text):
        end=min(len(text),start+size); out.append((start,text[start:end]))
        if end == len(text): break
        start=end-overlap
    return out or [(0,"")]
def tokenizer():
    try:
        import tiktoken
        enc=tiktoken.get_encoding("cl100k_base")
        return lambda s: len(enc.encode(s)), "tiktoken:cl100k_base"
    except Exception:
        return lambda s: math.ceil(len(s)/4), "estimate:ceil(chars/4); install tiktoken for cl100k_base"
def evidence_list(row):
    x=row.get("evidence",[])
    if isinstance(x,str): return [x] if x else []
    return [str(v) for v in x if v]
def run(path,k,size,overlap):
    count,tok_name=tokenizer()
    full_total=ret_total=coverage_sum=ev_hits=ev_total=rows_ev=0
    per=[]
    with open(path,encoding="utf-8") as f:
        for line_no,line in enumerate(f,1):
            if not line.strip(): continue
            row=json.loads(line); context=str(row["context"])
            query=str(row.get("query",row.get("question",""))); qt=terms(query)
            pieces=chunks(context,size,overlap); ranked=[]
            for idx,(offset,chunk) in enumerate(pieces):
                score=len(qt & terms(chunk))/max(1,len(qt))
                ranked.append((score,-idx,offset,chunk))
            chosen=sorted(ranked,reverse=True)[:k]
            selected="\n".join(x[3] for x in sorted(chosen,key=lambda x:x[2]))
            fn,sn=count(context),count(selected)
            cov=len(qt & terms(selected))/max(1,len(qt))
            ev=evidence_list(row); hits=sum(1 for e in ev if e in selected)
            full_total+=fn; ret_total+=sn; coverage_sum+=cov
            if ev: rows_ev+=1; ev_hits+=hits; ev_total+=len(ev)
            per.append({"id":row.get("id",line_no),"full_tokens":fn,"retrieved_tokens":sn,
                        "query_term_coverage_proxy":cov,"evidence_hits":hits if ev else None,
                        "evidence_total":len(ev) if ev else None})
    n=len(per)
    if not n: raise SystemExit("No JSONL examples found.")
    result={"benchmark":"LongBench-compatible JSONL","method":"full_context_vs_lexical_top_k",
      "examples":n,"top_k":k,"chunk_chars":size,"overlap_chars":overlap,"tokenizer":tok_name,
      "full_context_tokens":full_total,"retrieved_context_tokens":ret_total,
      "token_reduction_fraction":(full_total-ret_total)/full_total if full_total else 0,
      "mean_query_term_coverage_proxy":coverage_sum/n,
      "evidence_recall":ev_hits/ev_total if ev_total else None,"examples_with_evidence":rows_ev,
      "answer_accuracy":None,"answer_accuracy_note":"Not measured: this script does not run a model.",
      "per_example":per}
    print(json.dumps(result,indent=2)); return result
if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("jsonl"); p.add_argument("--top-k",type=int,default=5)
    p.add_argument("--chunk-chars",type=int,default=3000); p.add_argument("--overlap-chars",type=int,default=300)
    p.add_argument("--out",default="longbench_baseline_results.json"); a=p.parse_args()
    if a.top_k<1: p.error("--top-k must be >= 1")
    result=run(a.jsonl,a.top_k,a.chunk_chars,a.overlap_chars)
    Path(a.out).write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")

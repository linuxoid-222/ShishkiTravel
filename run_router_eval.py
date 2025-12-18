import os
from collections import Counter, defaultdict
from typing import Dict, Any, List, Set

from tqdm import tqdm

from eval_llm.utils import load_jsonl, norm_text, Timer

# IMPORTANT: run from project root, so imports resolve.
from app.agents.router_agent import RouterAgent

LABELS = ["tourism","legal","weather","route"]

def as_set(needs: List[str]) -> Set[str]:
    return set([n for n in (needs or []) if n in LABELS])

def main():
    cases = load_jsonl("eval_llm/dataset_router.jsonl")
    agent = RouterAgent()

    total=0
    parse_ok=0
    exact_match=0

    # per-label confusion
    tp=Counter(); fp=Counter(); fn=Counter()

    # entity accuracy
    city_ok=0; country_ok=0; start_ok=0; end_ok=0; city_total=0; country_total=0; start_total=0; end_total=0

    timings=[]

    for c in tqdm(cases, desc="router"):
        total += 1
        exp = c.get("expected", {})
        with Timer() as t:
            try:
                dec = agent.decide(c["text"], memory_hint="")
                parse_ok += 1
            except Exception as e:
                print(f"[{c['id']}] FAIL parse: {e}")
                continue
        timings.append(t.elapsed_s)

        got = as_set(getattr(dec, "needs", []))
        exp_set = as_set(exp.get("needs", []))

        if got == exp_set:
            exact_match += 1

        for lab in LABELS:
            if lab in got and lab in exp_set: tp[lab]+=1
            elif lab in got and lab not in exp_set: fp[lab]+=1
            elif lab not in got and lab in exp_set: fn[lab]+=1

        # slots
        if "city" in exp:
            city_total += 1
            if norm_text(getattr(dec,"city",None)) == norm_text(exp.get("city")):
                city_ok += 1
        if "country" in exp:
            country_total += 1
            if norm_text(getattr(dec,"country",None)) == norm_text(exp.get("country")):
                country_ok += 1
        if "start_location" in exp:
            start_total += 1
            if norm_text(getattr(dec,"start_location",None)) == norm_text(exp.get("start_location")):
                start_ok += 1
        if "end_location" in exp:
            end_total += 1
            if norm_text(getattr(dec,"end_location",None)) == norm_text(exp.get("end_location")):
                end_ok += 1

    def prf(lab):
        p = tp[lab] / (tp[lab]+fp[lab]) if (tp[lab]+fp[lab]) else 0.0
        r = tp[lab] / (tp[lab]+fn[lab]) if (tp[lab]+fn[lab]) else 0.0
        f = (2*p*r/(p+r)) if (p+r) else 0.0
        return p,r,f

    print("\n=== Router LLM metrics ===")
    print(f"cases: {total}")
    print(f"parse_success_rate: {parse_ok/total:.3f}")
    print(f"needs_exact_match: {exact_match/total:.3f}")

    for lab in LABELS:
        p,r,f = prf(lab)
        print(f"{lab:7s}  P={p:.2f} R={r:.2f} F1={f:.2f}  (tp={tp[lab]}, fp={fp[lab]}, fn={fn[lab]})")

    if city_total:
        print(f"city_accuracy: {city_ok/city_total:.3f}")
    if country_total:
        print(f"country_accuracy: {country_ok/country_total:.3f}")
    if start_total:
        print(f"start_accuracy: {start_ok/start_total:.3f}")
    if end_total:
        print(f"end_accuracy: {end_ok/end_total:.3f}")

    if timings:
        import statistics as st
        print(f"latency_mean_s: {st.mean(timings):.2f}  p90_s: {st.quantiles(timings, n=10)[8]:.2f}")

if __name__ == "__main__":
    main()

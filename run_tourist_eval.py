from typing import Any, Dict
from tqdm import tqdm

from eval_llm.utils import load_jsonl, contains_cyrillic_ratio, price_like, Timer

from app.agents.tourist_agent import TouristAgent

def main():
    cases = load_jsonl("eval_llm/dataset_tourist.jsonl")
    agent = TouristAgent()

    total=len(cases)
    ok_parse=0
    food_ok=0
    plan_ok=0
    highlights_ok=0
    ru_ok=0
    no_price_ok=0
    timings=[]

    for c in tqdm(cases, desc="tourist"):
        expect = c.get("expect", {})
        with Timer() as t:
            try:
                res = agent.run(
                    country=c.get("country"),
                    city=c.get("city"),
                    dates=c.get("dates"),
                    question=c.get("question",""),
                    summary=""
                )
                ok_parse += 1
            except Exception as e:
                print(f"[{c['id']}] FAIL parse: {e}")
                continue
        timings.append(t.elapsed_s)

        # checks
        if len(getattr(res, "highlights", []) or []) >= int(expect.get("highlights_min", 4)):
            highlights_ok += 1
        if bool(expect.get("food", False)) is False or len(getattr(res, "food_spots", []) or []) > 0:
            food_ok += 1
        if bool(expect.get("plan", False)) is False or len(getattr(res, "plan_1_day", []) or []) > 0:
            plan_ok += 1

        text = " ".join([getattr(res,"overview",""), getattr(res,"history","")]).strip()
        if expect.get("ru", True):
            if contains_cyrillic_ratio(text) >= 0.6:
                ru_ok += 1
        else:
            ru_ok += 1

        # heuristic: avoid exact prices
        full_text = str(res.model_dump()) if hasattr(res,"model_dump") else str(res)
        if not price_like(full_text):
            no_price_ok += 1

    import statistics as st
    print("\n=== Tourist LLM metrics ===")
    print(f"cases: {total}")
    print(f"schema_parse_success_rate: {ok_parse/total:.3f}")
    print(f"highlights_min_pass_rate: {highlights_ok/total:.3f}")
    print(f"food_inclusion_pass_rate: {food_ok/total:.3f}")
    print(f"plan_inclusion_pass_rate: {plan_ok/total:.3f}")
    print(f"russian_language_pass_rate: {ru_ok/total:.3f}")
    print(f'no_price_like_pass_rate: {no_price_ok/total:.3f}')
    if timings:
        print(f"latency_mean_s: {st.mean(timings):.2f}")

if __name__ == "__main__":
    main()

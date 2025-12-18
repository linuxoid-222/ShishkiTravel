import os
from typing import Dict, List
from tqdm import tqdm

from eval_llm.utils import load_jsonl, norm_text, Timer

from app.agents.legal_agent import LegalAgent
from app.config import settings

def parse_md_sections(md: str) -> Dict[str, List[str]]:
    import re
    sections={}
    cur="root"
    sections[cur]=[]
    for line in md.splitlines():
        line=line.rstrip()
        h=re.match(r"^\s{0,3}#{2,3}\s+(.+?)\s*$", line)
        if h:
            cur=h.group(1).strip()
            sections.setdefault(cur, [])
            continue
        b=re.match(r"^\s*[-•]\s+(.*)$", line)
        if b:
            item=b.group(1).strip()
            if item:
                sections.setdefault(cur, []).append(item)
    return sections

def pick(sections: Dict[str,List[str]], keywords: List[str]) -> List[str]:
    out=[]
    for title, items in sections.items():
        t=norm_text(title)
        if any(k in t for k in keywords):
            out.extend(items)
    return out

def main():
    # Requires: index built + GigaChat embeddings credentials valid
    cases = load_jsonl("eval_llm/dataset_legal.jsonl")
    agent = LegalAgent()

    total=len(cases)
    ok=0
    country_pure=0
    completeness_ok=0
    timings=[]

    for c in tqdm(cases, desc="legal"):
        country=c.get("country")
        city=c.get("city")
        q=c.get("question","")

        with Timer() as t:
            try:
                res = agent.run(country=country, city=city, question=q)
                ok += 1
            except Exception as e:
                print(f"[{c['id']}] FAIL: {e}")
                continue
        timings.append(t.elapsed_s)

        # purity: local source base name should correspond to the country's md (best-effort)
        # We only check that at least one local base appears and it is not obviously another country file.
        srcs = [s for s in (res.sources or []) if s and "http" not in s]
        if srcs:
            base=srcs[0]
            # if file exists - good
            if os.path.exists(os.path.join(settings.legal_kb_dir, base + ".md")):
                # ensure it matches requested country_ru header if present
                md=open(os.path.join(settings.legal_kb_dir, base + ".md"), "r", encoding="utf-8").read()
                header_country=None
                import re
                m=re.search(r"^\s*country_ru\s*:\s*(.+?)\s*$", md, flags=re.I|re.M)
                if m:
                    header_country=m.group(1).strip()
                if not header_country or norm_text(header_country)==norm_text(country):
                    country_pure += 1

                # completeness: if md contains bullets under entry/prohib sections, result should include them
                secs=parse_md_sections(md)
                exp_entry=pick(secs, ["въезд","документ","регистрац","услов"])
                exp_prohib=pick(secs, ["огранич","запрет","штраф","правил"])
                need_any = (len(exp_entry)+len(exp_prohib)) > 0
                got_any = bool(res.entry_and_registration) or bool(res.prohibitions_and_fines)
                if (not need_any) or got_any:
                    completeness_ok += 1

    import statistics as st
    print("\n=== Legal RAG metrics ===")
    print(f"cases: {total}")
    print(f"run_success_rate: {ok/total:.3f}")
    print(f"country_purity_pass_rate: {country_pure/total:.3f}")
    print(f"section_completeness_pass_rate: {completeness_ok/total:.3f}")
    if timings:
        print(f"latency_mean_s: {st.mean(timings):.2f}")

if __name__ == "__main__":
    main()

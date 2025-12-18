import json, time, re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

def load_jsonl(path: str) -> List[Dict[str, Any]]:
    out=[]
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line=line.strip()
            if not line: 
                continue
            out.append(json.loads(line))
    return out

def norm_text(s: Optional[str]) -> str:
    if not s:
        return ""
    s=s.strip().lower()
    s=re.sub(r"[\s\t\n]+", " ", s)
    s=re.sub(r"[^0-9a-zа-яё\- ]+", "", s, flags=re.I)
    return s.strip()

def contains_cyrillic_ratio(text: str) -> float:
    if not text:
        return 0.0
    letters=[ch for ch in text if ch.isalpha()]
    if not letters:
        return 0.0
    cyr=sum(1 for ch in letters if "а" <= ch.lower() <= "я" or ch.lower()=="ё")
    return cyr/len(letters)

def price_like(text: str) -> bool:
    if not text:
        return False
    # crude: any currency sign or common price patterns
    return bool(re.search(r"(€|\$|₽|руб\.?|usd|eur|\b\d{1,3}\s?(€|\$|₽)\b)", text, flags=re.I))

@dataclass
class Timing:
    elapsed_s: float

class Timer:
    def __enter__(self):
        self.t0=time.perf_counter()
        return self
    def __exit__(self, *exc):
        self.elapsed_s=time.perf_counter()-self.t0

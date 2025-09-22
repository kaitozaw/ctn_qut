from typing import List, Optional, Tuple

def safety_check(text: str, ng_words: List[str], soft_max_len: int, hard_max_len: int = 255) -> Tuple[bool, str, Optional[str]]:
    low = text.casefold()
    if any(w and w in low for w in ng_words):
        return False, "", "NG_WORD"
    text = shorten(text, min(max(1, hard_max_len), max(soft_max_len, 1)))
    return True, text, None

def shorten(s: str, n: int) -> str:
    return s if len(s) <= n else s[:n].rstrip()
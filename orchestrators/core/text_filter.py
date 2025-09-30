from typing import List, Optional, Tuple

def _shorten(s: str, n: int) -> str:
    return s if len(s) <= n else s[:n].rstrip()

def safety_check(text: str, ng_words: List[str], max_len: int = 255) -> Tuple[bool, str, Optional[str]]:
    low = text.casefold()
    if any(w and w in low for w in ng_words):
        return False, "", "NG_WORD"
    text = _shorten(text, max_len)
    return True, text, None
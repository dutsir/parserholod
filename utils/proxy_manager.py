import random
from typing import List, Optional

class ProxyManager:
    """Ротация и оценка прокси"""

    def __init__(self, proxies: List[str], rotation_enabled: bool = True):
        self.proxies = list(dict.fromkeys([p for p in proxies if p]))
        self.rotation_enabled = rotation_enabled
        self.bad_scores = {p: 0 for p in self.proxies}

    def get_proxy(self) -> Optional[str]:
        if not self.proxies:
            return None
        if not self.rotation_enabled:
            return self.proxies[0]
        weighted = []
        for p in self.proxies:
            weight = max(1, 5 - self.bad_scores.get(p, 0))
            weighted.extend([p] * weight)
        return random.choice(weighted) if weighted else random.choice(self.proxies)

    def mark_as_bad(self, proxy: str) -> None:
        if proxy in self.bad_scores:
            self.bad_scores[proxy] = min(5, self.bad_scores[proxy] + 1)

    def mark_as_good(self, proxy: str) -> None:
        if proxy in self.bad_scores and self.bad_scores[proxy] > 0:
            self.bad_scores[proxy] -= 1

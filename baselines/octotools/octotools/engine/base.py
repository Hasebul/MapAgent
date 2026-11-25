# Reference: https://github.com/zou-group/textgrad/blob/main/textgrad/engine/base.py

import hashlib
from abc import ABC, abstractmethod


class EngineLM(ABC):
    system_prompt: str = "You are a helpful, creative, and smart assistant."
    model_string: str

    @abstractmethod
    def generate(self, prompt, system_prompt=None, **kwargs):
        pass

    def __call__(self, *args, **kwargs):
        pass


class CachedEngine:
    def __init__(self, cache_path):
        import diskcache as dc  # optional dependency, only needed when caching is enabled

        super().__init__()
        self.cache_path = cache_path
        self.cache = dc.Cache(cache_path)

    def _hash_prompt(self, prompt: str):
        return hashlib.sha256(f"{prompt}".encode()).hexdigest()

    def _check_cache(self, prompt: str):
        return self.cache[prompt] if prompt in self.cache else None

    def _save_cache(self, prompt: str, response: str):
        self.cache[prompt] = response

    def __getstate__(self):
        state = self.__dict__.copy()
        state.pop("cache", None)
        return state

    def __setstate__(self, state):
        import diskcache as dc

        self.__dict__.update(state)
        self.cache = dc.Cache(self.cache_path)

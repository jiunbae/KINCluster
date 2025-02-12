import re
from typing import List, Union
from math import log10 as normalize
from collections import Counter
from itertools import chain
from functools import reduce


from KINCluster.core.item import Item
from KINCluster.lib.tokenizer import stemize, is_noun
from KINCluster.lib.stopwords import stopwords

import numpy as np

# type hinting
itemID = int # item id
dID = int # document id
wID = str # word id, it str cuz word counter, {word: count}


class extractable:
    """extractable is decorater for extractor, which extract something.

extractor.dump() return all result of extractable.
extractable function must have argument(iid: itemID)
    """
    s = {}
    def __init__(self, func):
        extractable.s[func.__name__] = func
        self.func = func

    def __get__(self, obj, klass=None):
        def _call_(*args, **kwargs):
            return self.func(obj, *args, **kwargs)
        return _call_

    @staticmethod
    def help():
        """print extractable function documents
        """
        print('extractable help')
        for f in extractable.s.values():
            print(f.__name__, f.__doc__)

class Extractor:
    """Extractor is extract feature from cluster

Usage:
    Extractor(cluster[, tokenizer])
    dump extract all of extractable feature as dict.

Default extractable:
    items       : items of clustered dump
    vectors     : vectors of clustered dump
    counter     : counter(split by tokenizer) of clustered dump
    center      : return center of vectors, (using np.mean)
    """
    def __init__(self, cluster, tokenizer=stemize, notword='[^a-zA-Z가-힣0-9]'):
        self.tokenizer = tokenizer
        self.not_word = re.compile(notword)
        self.__c = cluster

    @staticmethod
    def __find_center(vectors: np.ndarray) -> int:
        if isinstance(vectors, list):
            height = len(vectors)
            width = len(list(chain.from_iterable(vectors))) / height
        else:
            height, width = vectors.shape
        mean = np.mean(vectors)
        return mean, int(np.abs(vectors - mean).argmin() / width)

    def __get_word_count(self, items: List[Item]) -> Union[set, List[Counter]]:
        counter = Counter()
        for item in items:
            for word in self.tokenizer(repr(item)):
                if not word in stopwords and not self.not_word.search(word):
                    counter[word] += 1
        return counter

    def dump(self, iid: itemID) -> Item:
        items, vectors, counters = map(list, zip(*self.__c.dumps[iid]))
        return Item(**{e: f(self, items, vectors, counters) for e, f in extractable.s.items()})

    @extractable
    def items(self, items: List[Item], vectors: np.ndarray, counters: List[Counter]) -> List[Item]:
        return items

    @extractable
    def vectors(self, items: List[Item], vectors: np.ndarray, counters: List[Counter]) -> np.ndarray:
        return vectors

    @extractable
    def counter(self, items: List[Item], vectors: np.ndarray, counters: List[Counter]) -> Counter:
        return reduce(lambda x, y: x + y, counters)

    @extractable
    def center(self, items: List[Item], vectors: np.ndarray, counters: List[Counter]) -> int:
        """
        extract topic

        return Item that center of cluster
        """
        _, index = Extractor.__find_center(vectors)
        return index

    @extractable
    def keywords(self, items: List[Item], vectors: np.ndarray, counters: List[Counter], top: int = 32) -> List[str]:
        """
        extract keywords
        [optional argument top=32 for count of keywords]

        return keywords in cluster
        """
        counter = self.counter(items, vectors, counters)

        def _get_f(t: wID) -> float:
            return float(counter[t])
        def _get_tf(t: wID) -> float:
            max_f = max([_get_f(w) for w in counter.keys()])
            return .5 + (.5 * _get_f(t) / max_f)
        def _get_idf() -> float:
            return 0.01 + normalize(len(self.__c.items)/len(vectors))
        def _get_score(t: wID) -> float:
            return _get_tf(t) * _get_idf() + _get_f(t) * 0.001

        words = [(w, _get_score(w)) for w in filter(is_noun, counter.keys())]
        return sorted(words, key=lambda w: -float(w[1]))[:top]

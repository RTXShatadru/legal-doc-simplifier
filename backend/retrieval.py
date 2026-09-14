"""Document-scoped Unicode search with small English/Hindi topic expansions.
Does not change the stored embedding profile of existing libraries.
"""
import math
import re
from collections import Counter
from embeddings import STOP

TOPICS = [
    ('seller vendor विक्रेता विक्रय',),
    ('buyer purchaser क्रेता खरीदार',),
    ('area plot land property खसरा रकबा क्षेत्रफल भूमि जमीन',),
    ('amount consideration price value कीमत प्रतिफल मूल्य मालियत धनराशि',),
    ('registration registered registry stamp पंजीकरण पंजीकृत रजिस्ट्री स्टाम्प कोषागार',),
    ('rent rental किराया किरायेदार',),
    ('deposit security जमानत जमा',),
    ('interest ब्याज',),
    ('notice termination end समाप्त समाप्ति सूचना',),
    ('late overdue penalty penalties fee fees charges विलंब जुर्माना शुल्क',),
    ('duration term expiry expires months अवधि महीने',),
    ('renewal renew automatic renews नवीनीकरण',),
    ('method methods methodology approach model research findings results conclusion study',),
]
HINDI_STOP = set('का की के में से है हैं को और यह क्या कब कितना कितनी बारे मुझे बताओ'.split())


def tokens(value):
    return [w for w in re.findall(r'[a-z0-9]+|[\u0900-\u097f]+', value.lower())
            if len(w) > 1 and w not in STOP and w not in HINDI_STOP]


def rank(clauses, query, top_k=6):
    wanted = set(tokens(query))
    for (group,) in TOPICS:
        terms = set(group.split())
        if wanted & terms:
            wanted |= terms
    if not wanted:
        return []
    counts = [Counter(tokens(c['text'])) for c in clauses]
    frequency = Counter(word for words in counts for word in words)
    scores = []
    for clause, words in zip(clauses, counts):
        score = sum((1 + math.log(words[w])) * math.log(1 + len(clauses)/(1 + frequency[w]))
                    for w in wanted if words[w]) / (1 + sum(words.values()) / 250)
        if score > 0:
            scores.append((score, clause))
    scores.sort(key=lambda row: row[0], reverse=True)
    return [row[1] for row in scores[:top_k]]

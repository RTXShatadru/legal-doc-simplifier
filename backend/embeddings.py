"""Voyage semantic vectors or deterministic lexical vectors for the local demo."""
import hashlib
import math
import os
import re
import httpx
import config

STOP = set('a an the is are was be been this that it to for of on in at and or as by from with can could would should do does i my me what when how which about document contract says say please tell'.split())


def tokens(text):
    return [w for w in re.findall(r'[a-z0-9]+', text.lower()) if w not in STOP and len(w) > 1]


def local_vector(text):
    vector = [0.0] * config.EMBEDDING_DIM
    for word in tokens(text):
        index = int.from_bytes(hashlib.blake2b(word.encode(), digest_size=8).digest(), 'big') % len(vector)
        vector[index] += 1
    norm = math.sqrt(sum(v*v for v in vector)) or 1
    return [v/norm for v in vector]


def embed(texts: list[str], input_type='document') -> list[list[float]]:
    if config.EMBEDDING_PROVIDER == 'local':
        return [local_vector(t) for t in texts]
    vectors = []
    with httpx.Client(timeout=45) as client:
        for offset in range(0, len(texts), 32):
            batch = texts[offset:offset + 32]
            response = client.post('https://api.voyageai.com/v1/embeddings', headers={'Authorization': f"Bearer {os.environ['VOYAGE_API_KEY']}"}, json={'input': batch, 'model': os.getenv('VOYAGE_MODEL', 'voyage-3.5-lite'), 'input_type': input_type, 'output_dimension': 1024, 'truncation': False})
            response.raise_for_status()
            data = sorted(response.json()['data'], key=lambda row: row['index'])
            if len(data) != len(batch) or any(len(row['embedding']) != config.EMBEDDING_DIM for row in data):
                raise ValueError('Unexpected embedding response dimensions')
            vectors.extend(row['embedding'] for row in data)
    return vectors


def similarity(a, b):
    return sum(x*y for x, y in zip(a, b))

"""Similarité TF-IDF entre une offre et des CV : la baseline lexicale.

Implémentation directe, SANS scikit-learn, de la même formule que `TfidfVectorizer` avec ses
options `sublinear_tf=True`, `smooth_idf=True` (défaut) et `norm="l2"` (défaut) :

    tf'(t, d)  = 1 + ln(tf(t, d))                    (TF sous-linéaire)
    idf(t)     = ln((1 + n) / (1 + df(t))) + 1       (IDF lissé ; n = nombre de documents)
    poids      = tf' * idf, puis division par la norme L2 du vecteur du document
    similarité = produit scalaire des vecteurs normalisés = cosinus

Le test `test_tfidf_matches_scikit_learn` vérifie l'équivalence dès que scikit-learn est installé.

TF-IDF compare des MOTS, pas des sens : « apprentissage automatique » et « machine learning » ne
se ressemblent pas pour lui (les compétences normalisées compensent dans le score global). Les
embeddings (Phase 6) traiteront les synonymes.

Les valeurs dépendent du lot : l'IDF est calculé sur l'offre et les CV du lot. Elles sont
comparables à l'intérieur d'un classement, pas d'un classement à l'autre.
"""

import math
from collections import Counter

from app.modules.matching.text import analyzer


def _vectors(documents: list[Counter[str]]) -> list[dict[str, float]]:
    n = len(documents)
    document_frequency: Counter[str] = Counter(term for doc in documents for term in doc)
    idf = {term: math.log((1 + n) / (1 + df)) + 1 for term, df in document_frequency.items()}
    vectors = []
    for doc in documents:
        weights = {term: (1 + math.log(count)) * idf[term] for term, count in doc.items()}
        norm = math.sqrt(sum(w * w for w in weights.values()))
        vectors.append({term: w / norm for term, w in weights.items()} if norm else {})
    return vectors


def tfidf_similarities(job_text: str, cv_texts: list[str]) -> list[float]:
    """Similarité cosinus (0 à 1) entre l'offre et chacun des CV, dans l'ordre donné."""
    if not cv_texts:
        return []
    documents = [Counter(analyzer(text)) for text in (job_text, *cv_texts)]
    job_vector, *cv_vectors = _vectors(documents)
    similarities = []
    for vector in cv_vectors:
        small, large = (
            (vector, job_vector) if len(vector) <= len(job_vector) else (job_vector, vector)
        )
        similarities.append(sum(weight * large.get(term, 0.0) for term, weight in small.items()))
    return [min(1.0, max(0.0, value)) for value in similarities]

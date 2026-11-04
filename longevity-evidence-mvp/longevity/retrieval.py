from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from .db import list_papers

def retrieve(query, profile=None, k=8):
    papers = list_papers(limit=2000)
    if not papers:
        return []
    docs = [(p.get("title","") + "\n" + p.get("abstract","")).strip() for p in papers]
    vectorizer = TfidfVectorizer(stop_words="english", ngram_range=(1,2), max_features=50000)
    try:
        matrix = vectorizer.fit_transform(docs + [query])
        scores = cosine_similarity(matrix[-1], matrix[:-1]).ravel()
    except ValueError:
        return []
    ranked = sorted(zip(scores, papers), key=lambda x: x[0], reverse=True)
    results = []
    for score, paper in ranked[:k]:
        results.append({"score": float(score), "paper": paper})
    return results

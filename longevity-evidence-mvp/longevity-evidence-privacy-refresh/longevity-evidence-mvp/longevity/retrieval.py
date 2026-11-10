from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from .db import list_papers


def retrieve(query, profile=None, k=8):
    """Return local papers ranked by lexical relevance.

    Title matches receive more weight than abstract matches. The score is a
    retrieval signal only; it is not a measure of evidence quality.
    """
    query = (query or "").strip()
    if not query or k <= 0:
        return []

    papers = list_papers(limit=2000)
    if not papers:
        return []

    titles = [(p.get("title") or "").strip() for p in papers]
    abstracts = [(p.get("abstract") or "").strip() for p in papers]

    try:
        title_vectorizer = TfidfVectorizer(
            stop_words="english", ngram_range=(1, 2), max_features=30000,
            sublinear_tf=True,
        )
        abstract_vectorizer = TfidfVectorizer(
            stop_words="english", ngram_range=(1, 2), max_features=50000,
            sublinear_tf=True,
        )
        title_matrix = title_vectorizer.fit_transform(titles)
        abstract_matrix = abstract_vectorizer.fit_transform(abstracts)
        title_query = title_vectorizer.transform([query])
        abstract_query = abstract_vectorizer.transform([query])
        title_scores = cosine_similarity(title_query, title_matrix).ravel()
        abstract_scores = cosine_similarity(abstract_query, abstract_matrix).ravel()
    except ValueError:
        return []

    # A title match is a useful relevance signal, but abstract context remains
    # important. These weights are a simple baseline, not a learned ranker.
    scores = 0.40 * title_scores + 0.60 * abstract_scores
    ranked = sorted(
        zip(scores, papers),
        key=lambda item: (item[0], item[1].get("pub_date") or ""),
        reverse=True,
    )
    return [
        {"score": float(score), "paper": paper}
        for score, paper in ranked[:k]
        if score > 0
    ]

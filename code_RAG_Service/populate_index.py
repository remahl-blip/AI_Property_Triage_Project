"""Build and smoke-test the in-memory listing index."""

from rag_engine import ListingIndex, generate_insight


def main() -> None:
    index = ListingIndex()
    index.load()
    print(f"Loaded {len(index.listings)} listings into TF-IDF index.")
    sample = "דירת 3 חדרים למכירה בחיפה עם מרפסת"
    hits = index.search(sample)
    print(f"Sample query: {sample!r}")
    for hit in hits:
        print(f"  - {hit['id']}: {hit['title']} (score={hit['similarity_score']})")
    print("Insight:", generate_insight(sample, hits))


if __name__ == "__main__":
    main()

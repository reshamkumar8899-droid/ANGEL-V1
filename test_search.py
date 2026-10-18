from ddgs import DDGS

query = "latest GTA 6 news"
print(f"[TEST] Searching for: {query}")

with DDGS() as ddgs:
    results = list(ddgs.text(query, max_results=3))

if results:
    print(f"[TEST] Got {len(results)} results:")
    for i, r in enumerate(results, 1):
        title = r.get("title", "No title")
        body  = r.get("body",  "No body")[:120]
        print(f"  {i}. {title}")
        print(f"     {body}...")
    print()
    print("[TEST] Web search working correctly!")
else:
    print("[TEST] No results returned — might be rate limited.")

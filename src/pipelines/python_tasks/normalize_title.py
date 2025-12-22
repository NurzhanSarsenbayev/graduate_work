def transform(rows):
    out = []
    for r in rows:
        d = dict(r)
        if d.get("title"):
            d["title"] = "X_" + d["title"].strip()
        out.append(d)
    return out

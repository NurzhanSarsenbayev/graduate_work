def transform(rows):
    out = []
    for r in rows:
        d = dict(r)
        if d.get("title"):
            d["title"] = "TRANSFORMED_" + d["title"].strip()
        out.append(d)
    return out

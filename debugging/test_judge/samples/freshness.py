"""Rows whose volume the downloader filled in (CvdWindow freshness-probe shape)."""


def fresh_rows(rows):
    out = []
    for r in rows:
        if r["buy_volume"] is not None and r["buy_volume"] >= 0:
            out.append(r)
    return out

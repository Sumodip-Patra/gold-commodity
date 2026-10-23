def label(r, cfg):
    """Return (tags, why) for one row."""
    tags, why = [], []
    if r.basis_pct > cfg["rich_pct"]:
        tags.append("RICH")
        why.append(f"{r.basis_pct:+.2f}% vs fair")
    elif r.basis_pct < -cfg["cheap_pct"]:
        tags.append("CHEAP")
        why.append(f"{r.basis_pct:+.2f}% vs fair")
    if r.z_cross > cfg["z_limit"]:
        tags.append("WIDE")
        why.append(f"gap to GOLD z={r.z_cross:.1f}")
    elif r.z_cross < -cfg["z_limit"]:
        tags.append("TIGHT")
        why.append(f"gap to GOLD z={r.z_cross:.1f}")
    if r.cal_ann_pct == r.cal_ann_pct:  # not NaN
        tags.append("CONTANGO" if r.cal_ann_pct > 0 else "BACKWARDATION")
        why.append(f"carry {r.cal_ann_pct:+.1f}% a year")
    if r.days <= cfg["roll_days"]:
        tags.append("ROLL")
        why.append(f"{r.days} days left")
    if r.volume < cfg["min_volume"]:
        tags.append("THIN")
        why.append(f"volume {r.volume}")
    if not tags:
        return ["OK"], f"within {cfg['rich_pct']}% of fair"
    return tags, "; ".join(why)

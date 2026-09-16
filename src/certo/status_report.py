"""`certo status`: where a proof stands, not what one command said.

Twenty-three commands, twenty-eight certificate kinds, and until now no way to
look at a directory of them and see the state of the work. A research project
is not a sequence of runs; it is a set of claims -- some established, some
standing on an assumption, some still owed -- and that shape lived only in the
head of whoever ran the commands.

Three things this looks for, in the order they matter:

  WHAT IS STILL OWED.  Every bridge in every `compose` proof and every
  `induct` certificate is an assumption somebody has to discharge or defend.
  They are easy to forget precisely because the proof around them verifies.

  WHAT IS HOLLOW.  A vacuous proof, a sweep that certified less than it
  evaluated, a design that is feasible rather than optimal. All valid, all
  saying less than they look like they say.

  WHAT HAS ROTTED.  A certificate whose spec has changed since it was issued
  is not wrong -- it verifies on its own -- but it no longer describes the
  file sitting next to it, and six months later nobody remembers which.

It emits no certificate of its own, deliberately. `status` makes no claim; it
reads the claims other commands made. A report that certified itself would be
the one artefact here that nobody had checked.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .certificate import Certificate
from .i18n import t

#: Where each kind keeps the sub-certificates it is built from. A certificate
#: that embeds another is downstream of it, and that is the whole DAG.
#:
#: Deliberately absent: the per-item entries of a `sweep`. Those are witnesses
#: for one graph each, not results anybody cites, and a thousand of them would
#: bury the nine things a reader came to see.
CHILDREN = {
    "proof": lambda p: [l.get("cert") for l in p.get("lemmas", [])]
                       + [p.get("step")],
    "induction": lambda p: [b.get("cert") for b in p.get("base", [])]
                           + [p.get("step")],
    "gap": lambda p: [p.get("fractional"), p.get("integral")],
    "orbit_witnesses": lambda p: [p.get("sweep")]
                                 + [w.get("cert") for w in p.get("witnesses", [])],
    "branch_bound": lambda p: [p.get("incumbent_cert")]
                              + [n.get("cert") for n in p.get("nodes", [])],
    "mixed_design": lambda p: [p.get("residual"), p.get("relaxation")],
    "synth_proved": lambda p: [p.get("synth"), p.get("universal")],
    "sweep_range": lambda p: [e.get("cert") for e in p.get("entries", [])],
    "bisect": lambda p: [p.get("good_cert"), p.get("bad_cert")],
    "core_matrix": lambda p: list((p.get("cores") or {}).values()),
}


def _children(data: dict) -> list:
    fn = CHILDREN.get(data.get("kind"))
    if fn is None:
        return []
    return [c for c in fn(data.get("payload") or {})
            if isinstance(c, dict) and "kind" in c]


def _owed(data: dict) -> list:
    """The assumptions this certificate stands on, named.

    Not failures. A bridge is a legitimate and often unavoidable move; what
    is not legitimate is losing track of how many of them a result rests on.
    """
    p = data.get("payload") or {}
    kind = data.get("kind")
    out = []
    if kind == "proof":
        for lem in p.get("lemmas", []):
            if not lem.get("derived"):
                out.append({"sort": "bridge", "name": lem.get("name", "?"),
                            "why": lem.get("bridge") or ""})
    elif kind == "induction":
        out.append({"sort": "bridge", "name": t("status.owed.induction"),
                    "why": p.get("bridge") or ""})
    elif kind == "mixed_design" and p.get("level") != "global_optimum":
        out.append({"sort": "not_claimed", "name": t("status.owed.optimal"),
                    "why": t("status.owed.mixed", level=p.get("level", "?"))})
    elif kind == "gap" and p.get("level") != "global_optimum":
        out.append({"sort": "not_claimed", "name": t("status.owed.optimal"),
                    "why": t("status.owed.gap", level=p.get("level", "?"))})
    return out


def _hollow(data: dict) -> list:
    """Valid, and saying less than it looks like it says."""
    p = data.get("payload") or {}
    kind = data.get("kind")
    out = []
    if p.get("vacuous"):
        clash = ", ".join(p.get("clash") or [])
        out.append(t("status.hollow.vacuous_named", names=clash) if clash
                   else t("status.hollow.vacuous"))
    if kind in ("sweep", "domain_sweep") and not p.get("no_predicate"):
        ev, cert = p.get("evaluations") or 0, p.get("certified") or 0
        if ev and not cert:
            # Not a shortfall: a predicate returning `bool` cannot produce a
            # certificate, and that is the documented `reproducible` level.
            # Worth saying once per sweep, which is exactly what this is for.
            out.append(t("status.hollow.sweep_none", total=ev))
        elif ev and cert < ev:
            out.append(t("status.hollow.sweep", n=ev - cert, total=ev))
        seen = p.get("evaluated")
        # Inferring by symmetry is a real reduction, not a shortfall -- but a
        # reader deserves to know how much of the family was looked at.
        if p.get("by_orbit") and isinstance(seen, int) and ev and seen < ev:
            out.append(t("status.hollow.by_orbit", n=seen, total=ev))
    return out


def _stale(data: dict):
    """Has the spec moved since this was issued?"""
    prov = data.get("provenance") or {}
    src, want = prov.get("spec_path"), prov.get("spec_sha256")
    if not src or not want:
        return None
    p = Path(src)
    if not p.is_file():
        return "gone"
    return None if hashlib.sha256(p.read_bytes()).hexdigest() == want else "changed"


def _rel(f: Path, root: Path) -> str:
    """The path as the reader typed it: relative to what they asked about."""
    try:
        return str(f.relative_to(root)) if root.is_dir() else f.name
    except ValueError:                                 # not under root at all
        return str(f)


def _headline(data: dict) -> str:
    """One line for what this certificate is about, if it knows."""
    p = data.get("payload") or {}
    for key in ("title", "conclusion", "describe", "claim"):
        v = p.get(key)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return ""


def scan(where=".", verify_all=False, limits=None) -> dict:
    """Read every certificate under `where` and work out where things stand."""
    from .certificate import verify as verify_cert

    root = Path(where)
    if root.is_dir():
        files = sorted(root.rglob("*.json"))
    elif root.is_file():
        files = [root]
    else:
        raise FileNotFoundError(str(root))

    nodes, embedded, broken, skipped = {}, set(), [], 0
    for f in files:
        try:
            raw = json.loads(f.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError, OSError):
            skipped += 1
            continue
        data = Certificate.unwrap(raw) if isinstance(raw, dict) else None
        if not isinstance(data, dict) or "kind" not in data:
            skipped += 1     # a ledger, a config, somebody's notes: not ours
            continue
        try:
            cert = Certificate.from_dict(data)
        except (KeyError, TypeError):
            skipped += 1
            continue

        prov = data.get("provenance") or {}
        entry = {
            "path": str(f), "rel": _rel(f, root),
            "kind": data["kind"], "digest": cert.digest(),
            "headline": _headline(data),
            "solver_free": bool(data.get("solver_free")),
            "version": prov.get("certo_version"),
            "spec": prov.get("spec_path"),
            "stale": _stale(data),
            "owed": _owed(data), "hollow": _hollow(data),
            "children": [],
        }
        for child in _children(data):
            try:
                d = Certificate.from_dict(child).digest()
            except (KeyError, TypeError):
                continue
            entry["children"].append({"kind": child["kind"], "digest": d})
            embedded.add(d)
            # A BRIDGE three levels down is still owed by whatever sits on
            # top of it, and the whole reason to read a directory rather than
            # a file is to stop those from going quiet.
            #
            # An unclaimed optimality is not inherited. It describes what THAT
            # certificate establishes, and a parent may be citing it for
            # something else: a proof can cite a `gap` for the value 15/2
            # while proving the optimum separately by branch and bound. A
            # `branch_bound` certificate IS the proof its incumbent lacks, so
            # inheriting that particular debt would contradict the parent.
            entry["owed"].extend(o for o in _owed(child)
                                 if o["sort"] == "bridge")
            entry["hollow"].extend(_hollow(child))
        # A debt reached through two different children is still one debt,
        # and the FIRST framing wins: that is the parent's, which is the one
        # phrased in terms of the result a reader came here for.
        entry["owed"] = _dedup(entry["owed"], lambda o: (o["sort"], o["name"]))
        entry["hollow"] = _dedup(entry["hollow"], lambda h: h)
        if verify_all:
            rep = verify_cert(cert, limits)
            entry["verified"] = rep.ok
            if not rep.ok:
                # The FAILING CHECKS, not rep.detail: the detail describes
                # what the certificate claims about itself, and printing that
                # under a heading called BROKEN reads as an endorsement of
                # the thing that just failed.
                failed = ["{}{}".format(name, ": " + d if d else "")
                          for name, ok, d in rep.checks if not ok]
                broken.append({"path": str(f), "rel": entry["rel"],
                               "kind": entry["kind"], "failed": failed,
                               "detail": "; ".join(failed) or rep.detail,
                               "claims": rep.detail})
        nodes[entry["digest"]] = entry

    order = sorted(nodes.values(), key=lambda n: (n["kind"], n["path"]))
    return {
        "root": str(root),
        "certificates": len(nodes),
        "skipped": skipped,
        "verified": verify_all,
        "results": [n for n in order if n["digest"] not in embedded],
        "owed": [dict(o, path=n["path"], rel=n["rel"])
                 for n in order for o in n["owed"]],
        "hollow": [{"path": n["path"], "rel": n["rel"], "text": h}
                   for n in order for h in n["hollow"]],
        "stale": [{"path": n["path"], "rel": n["rel"], "spec": n["spec"],
                   "why": n["stale"]}
                  for n in order if n["stale"]],
        "broken": broken,
        "kinds": _count(n["kind"] for n in order),
        "versions": _count(n["version"] for n in order if n["version"]),
    }


def _dedup(items, key):
    seen, out = set(), []
    for x in items:
        k = key(x)
        if k not in seen:
            seen.add(k)
            out.append(x)
    return out


def _count(it) -> dict:
    out: dict = {}
    for x in it:
        out[x] = out.get(x, 0) + 1
    return dict(sorted(out.items(), key=lambda kv: (-kv[1], kv[0])))

"""Placement (docs/runtimes/multi-device.md#placement, #207): a pure function from a spawn request, the resolved
profile and live host facts to one host and engine, a queue with one reason per host, or a refusal. mdstack spawn
gathers the facts; this module reads nothing else, so the offline fixture tests cover every decision.
"""
import fnmatch

PLACED = ("builder", "reviewer")  # the coordinator, synthesizer and researcher always run on the primary (C7)


def setting(values, host, key, default=None):
    return values.get("hosts.%s.%s" % (host, key), default)


def inventory(values):
    return sorted({k.split(".")[1] for k in values if k.startswith("hosts.")})


def needs_of(values, request):
    """The needs of the first rule matching role, pass and, when the rule names paths, a changed path; else none."""
    for rule in values.get("placement.rules", []):
        if rule["role"] == request["role"] and rule.get("pass", request["pass"]) == request["pass"] and (
                "paths" not in rule or any(fnmatch.fnmatch(p, g) for p in request.get("paths", []) for g in rule["paths"])):
            return rule["needs"]
    return {}


def lacks(values, host, needs):
    """The first need host does not meet, or None."""
    for key in ("os", "arch"):
        if key in needs and setting(values, host, "capabilities." + key) != needs[key]:
            return "%s %s" % (key, needs[key])
    missing = [d for d in needs.get("devices", []) if d not in setting(values, host, "capabilities.devices", [])]
    return "device " + missing[0] if missing else None


def takes(values, host, role):
    forge = setting(values, host, "forge", True)
    return role in setting(values, host, "roles", list(PLACED) if forge else [])


def place(request, values, facts):
    """request: role, pass, paths (a PR's changed paths), order ([engine, model] pairs, skipped engines removed) and
    host (an override, or None). facts(host) -> {reachable, ready, load}. Returns a dict with result place (host,
    engine, model, placement, rejections), queue (reason) or refuse (reason)."""
    hosts = inventory(values)
    primary = next((h for h in hosts if setting(values, h, "primary", False)), None)
    if not hosts or request["role"] not in PLACED:
        if request.get("host") and request["host"] != primary:
            return dict(result="refuse", reason="no [hosts] inventory" if not hosts else
                        "%s runs on the primary only" % request["role"])
        if not request["order"]:
            return dict(result="refuse", reason="no engine left in the tier order")
        return dict(result="place", host=primary, engine=request["order"][0][0], model=request["order"][0][1],
                    placement="local", rejections=[])
    needs = needs_of(values, request)
    if request.get("host"):
        h = request["host"]
        problem = ("not in the inventory" if h not in hosts else "excludes role " + request["role"]
                   if not takes(values, h, request["role"]) else "lacks " + lacks(values, h, needs)
                   if lacks(values, h, needs) else None)
        if problem:
            return dict(result="refuse", reason="%s: %s" % (h, problem))
        candidates, kind = [h], "override"
    else:
        affinity = values.get("placement.hosts") or [primary]
        candidates = affinity if not needs else [h for h in affinity if h in hosts and not lacks(values, h, needs)] + [
            h for h in hosts if h not in affinity and not lacks(values, h, needs)]
        candidates = [h for h in candidates if takes(values, h, request["role"])]
        kind = "capability" if needs else "affinity"
    engine = next((e for e in request["order"] if any(e[0] in setting(values, h, "capabilities.engines", [])
                                                      for h in candidates)), None)
    if engine is None:
        return dict(result="refuse", reason="no candidate host (%s) lists an engine in the tier order" % (
            ", ".join(candidates) or "none"))
    rejections, eligible = [], []
    for h in candidates:
        f, cap = facts(h), setting(values, h, "max_runs")
        reason = ("lists no " + engine[0] if engine[0] not in setting(values, h, "capabilities.engines", []) else
                  "unreachable" if not f["reachable"] else "not ready" if not f["ready"] else
                  "at cap %s/%s" % (f["load"], cap) if f["load"] >= cap else None)
        if reason:
            rejections.append("%s: %s" % (h, reason))
        else:
            eligible.append((f["load"] / cap, len(eligible), h))
    if not eligible:
        return dict(result="refuse" if kind == "override" else "queue", reason="; ".join(rejections))
    return dict(result="place", host=min(eligible)[2], engine=engine[0], model=engine[1], placement=kind,
                rejections=rejections)

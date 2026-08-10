import logging
import yaml
import json
import random
from datetime import date, timedelta
from pathlib import Path

DOMAIN = "meal_solver_3000"
_LOGGER = logging.getLogger(__name__)

BASE = Path("/config/Matlistor")
DISHES_FILE  = BASE / "matratter.yaml"
RULES_FILE   = BASE / "regler.yaml"
HISTORY_FILE = BASE / "historik.json"
TAGS_FILE    = BASE / "taggar.json"

_DEFAULT_TAGS = ["köttfärs","nöt","fläsk","fågel","fisk","vegetarisk","korv","lamm",
                 "potatis","ris","pasta","nudlar"]

WEEKDAY_DAYS = ["måndag", "tisdag", "onsdag", "torsdag"]
WEEKEND_DAYS = ["fredag", "lördag", "söndag"]
ALL_DAYS     = WEEKDAY_DAYS + WEEKEND_DAYS

DAY_ENTITY = {
    "måndag":  ("input_text.mandag_middag",  "input_boolean.mandag_last"),
    "tisdag":  ("input_text.tisdag_middag",  "input_boolean.tisdag_last"),
    "onsdag":  ("input_text.onsdag_middag",  "input_boolean.onsdag_last"),
    "torsdag": ("input_text.torsdag_middag", "input_boolean.torsdag_last"),
    "fredag":  ("input_text.fredag_middag",  "input_boolean.fredag_last"),
    "lördag":  ("input_text.lordag_middag",  "input_boolean.lordag_last"),
    "söndag":  ("input_text.sondag_middag",  "input_boolean.sondag_last"),
}

_OPTION_DEFAULTS = {
    "max_rules":       "köttfärs:2, fisk:1",
    "min_rules":       "vegetarisk:1",
    "no_consecutive":  "potatis, ris, pasta, nudlar",
    "repeat_interval": 14,
}


# ── Dish file I/O ─────────────────────────────────────────────────────────────

def _load_dishes() -> dict:
    with open(DISHES_FILE, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}

def _save_dishes(dishes: dict):
    with open(DISHES_FILE, "w", encoding="utf-8") as f:
        yaml.dump(dishes, f, allow_unicode=True, default_flow_style=False, sort_keys=True)

def _load_tags() -> list:
    if not TAGS_FILE.exists():
        # Seed from default list + tags already present in dishes file
        try:
            m = _load_dishes()
            extra = {t for d in m.values() for t in d.get("taggar", [])}
        except Exception:
            extra = set()
        tags = sorted(set(_DEFAULT_TAGS) | extra)
        _save_tags(tags)
        return tags
    with open(TAGS_FILE, encoding="utf-8") as f:
        return json.load(f)

def _save_tags(tags: list):
    with open(TAGS_FILE, "w", encoding="utf-8") as f:
        json.dump(sorted(set(tags)), f, ensure_ascii=False, indent=2)

def _add_tags_to_registry(new_tags: list):
    existing = set(_load_tags())
    combined = existing | set(new_tags)
    if combined != existing:
        _save_tags(list(combined))

async def _refresh_sensor(hass):
    def _load():
        return _load_dishes(), _load_tags()
    dishes, known_tags = await hass.async_add_executor_job(_load)
    entries = hass.config_entries.async_entries(DOMAIN)
    language = entries[0].options.get("language", "sv") if entries else "sv"
    hass.states.async_set(
        "sensor.meal_solver_matlista",
        len(dishes),
        {"dishes": dishes, "known_tags": known_tags,
         "language": language,
         "friendly_name": "Meal Solver Dish List"},
    )


# ── Rule parser ───────────────────────────────────────────────────────────────

def _parse_tag_rules(text: str) -> dict:
    result = {}
    for part in text.split(","):
        part = part.strip()
        if not part:
            continue
        parts = part.split(":", 1)
        if len(parts) == 2:
            try:
                result[parts[0].strip()] = int(parts[1].strip())
            except ValueError:
                pass
    return result

def _parse_list(text: str) -> list:
    return [x.strip() for x in text.split(",") if x.strip()]

def _build_rules(opts: dict) -> dict:
    try:
        with open(RULES_FILE, encoding="utf-8") as f:
            yaml_rules = yaml.safe_load(f) or {}
    except Exception:
        yaml_rules = {}

    max_per_week = (_parse_tag_rules(opts["max_rules"]) if "max_rules" in opts
                    else yaml_rules.get("max_per_week",
                         _parse_tag_rules(_OPTION_DEFAULTS["max_rules"])))
    min_per_week = (_parse_tag_rules(opts["min_rules"]) if "min_rules" in opts
                    else yaml_rules.get("min_per_week",
                         _parse_tag_rules(_OPTION_DEFAULTS["min_rules"])))
    no_consecutive = (_parse_list(opts["no_consecutive"]) if "no_consecutive" in opts
                      else yaml_rules.get("no_consecutive",
                           _parse_list(_OPTION_DEFAULTS["no_consecutive"])))

    return {
        "max_per_week": max_per_week,
        "min_per_week": min_per_week,
        "no_consecutive": no_consecutive,
        "repeat_interval_days": opts.get("repeat_interval",
                                  yaml_rules.get("repeat_interval_days",
                                  _OPTION_DEFAULTS["repeat_interval"])),
        "max_attempts": yaml_rules.get("max_attempts", 1000),
    }


# ── Solver ────────────────────────────────────────────────────────────────────

def _load_history():
    if not HISTORY_FILE.exists():
        return []
    with open(HISTORY_FILE, encoding="utf-8") as f:
        return json.load(f)

def _this_week_saved():
    """Returns True if history already has an entry from the current ISO week."""
    history = _load_history()
    if not history:
        return False
    today = date.today()
    last = date.fromisoformat(history[-1]["date"])
    return last.isocalendar()[:2] == today.isocalendar()[:2]

def _save_history(plan):
    real_plan = {day: dish for day, dish in plan.items()
                 if dish and dish not in ("-", "unknown", "")}
    if len(real_plan) < 3:
        return
    history = _load_history()
    history.append({"date": date.today().isoformat(), "plan": real_plan})
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)

def _dishes_within_interval(history, interval_days):
    cutoff = date.today() - timedelta(days=interval_days)
    excluded = set()
    for week in history:
        if date.fromisoformat(week["date"]) >= cutoff:
            excluded.update(week["plan"].values())
    return excluded

def _candidates(dishes, day_type, excluded, locked_dishes):
    return [
        name for name, data in dishes.items()
        if data.get("dagar") in (day_type, "båda")
        and name not in excluded
        and name not in locked_dishes.values()
        and not data.get("låst_dag")
    ]

def _tag_counts(plan, dishes):
    counts = {}
    for dish in plan.values():
        for tag in dishes.get(dish, {}).get("taggar", []):
            counts[tag] = counts.get(tag, 0) + 1
    return counts

def _max_ok(plan, dishes, rules, new_dish):
    counts = _tag_counts(plan, dishes)
    for tag in dishes[new_dish].get("taggar", []):
        max_count = rules.get("max_per_week", {}).get(tag)
        if max_count is not None and counts.get(tag, 0) + 1 > max_count:
            return False
    return True

def _no_consecutive_ok(plan, dishes, rules, day, new_dish):
    no_consec = set(rules.get("no_consecutive", []))
    if not no_consec:
        return True
    idx = ALL_DAYS.index(day)
    if idx == 0:
        return True
    previous = plan.get(ALL_DAYS[idx - 1])
    if not previous or previous not in dishes:
        return True
    new_rel  = {t.lower() for t in dishes[new_dish].get("taggar", [])} & no_consec
    prev_rel = {t.lower() for t in dishes[previous].get("taggar", [])} & no_consec
    if not new_rel or not prev_rel:
        return True
    return not (new_rel == prev_rel and len(new_rel) == 1)

def _min_ok(plan, dishes, rules):
    counts = _tag_counts(plan, dishes)
    for tag, min_count in rules.get("min_per_week", {}).items():
        if counts.get(tag, 0) < min_count:
            return False
    return True

def _requirements_ok(plan, dishes):
    """Check that dishes with 'kräver' have their required dish in the plan."""
    plan_dishes = set(plan.values())
    for dish in plan_dishes:
        requires = dishes.get(dish, {}).get("kräver")
        if requires and requires not in plan_dishes:
            return False
    return True

def _solve(locked_dishes, rules):
    dishes       = _load_dishes()
    history      = _load_history()
    interval     = rules.get("repeat_interval_days", 14)
    max_attempts = rules.get("max_attempts", 1000)
    excluded     = _dishes_within_interval(history, interval)
    excluded    -= set(locked_dishes.values())

    yaml_locked = {
        data["låst_dag"]: name
        for name, data in dishes.items()
        if data.get("låst_dag") and data["låst_dag"] in ALL_DAYS
    }

    for _ in range(max_attempts):
        plan = {**yaml_locked, **locked_dishes}
        weekday_pool = _candidates(dishes, "vardag", excluded, locked_dishes)
        weekend_pool = _candidates(dishes, "helg",   excluded, locked_dishes)
        random.shuffle(weekday_pool)
        random.shuffle(weekend_pool)

        ok = True
        for day in ALL_DAYS:
            if day in plan:
                continue
            pool = weekend_pool if day in WEEKEND_DAYS else weekday_pool
            selected = next(
                (r for r in pool
                 if r not in plan.values()
                 and _max_ok(plan, dishes, rules, r)
                 and _no_consecutive_ok(plan, dishes, rules, day, r)),
                None,
            )
            if selected is None:
                ok = False
                break
            plan[day] = selected

        if ok and _min_ok(plan, dishes, rules) and _requirements_ok(plan, dishes):
            return plan

    return None


# ── HA integration ────────────────────────────────────────────────────────────

async def async_setup(hass, config):

    async def handle_generate_week(call):
        entries = hass.config_entries.async_entries(DOMAIN)
        opts    = entries[0].options if entries else {}
        rules   = await hass.async_add_executor_job(_build_rules, opts)

        locked_dishes = {}
        for day, (text_eid, bool_eid) in DAY_ENTITY.items():
            bs = hass.states.get(bool_eid)
            if bs and bs.state == "on":
                ts = hass.states.get(text_eid)
                if ts and ts.state not in ("", "unknown"):
                    locked_dishes[day] = ts.state

        # Save current week to history — only if not already saved this week
        already_saved = await hass.async_add_executor_job(_this_week_saved)
        if not already_saved:
            current_plan = {}
            for day, (text_eid, _) in DAY_ENTITY.items():
                ts = hass.states.get(text_eid)
                if ts and ts.state not in ("", "unknown"):
                    current_plan[day] = ts.state
            if current_plan:
                await hass.async_add_executor_job(_save_history, current_plan)

        plan = await hass.async_add_executor_job(_solve, locked_dishes, rules)
        if plan is None:
            _LOGGER.error("Meal Solver 3000: could not find a valid weekly plan")
            return

        for day, dish in plan.items():
            text_eid, _ = DAY_ENTITY[day]
            await hass.services.async_call(
                "input_text", "set_value",
                {"entity_id": text_eid, "value": dish},
                blocking=True,
            )
        await hass.async_add_executor_job(_save_history, plan)
        _LOGGER.info("Meal Solver 3000: new weekly plan — %s", date.today())

    # ── Dish services ──────────────────────────────────────────────

    async def handle_add_dish(call):
        name       = call.data.get("name", "").strip()
        days       = call.data.get("days", "vardag")
        tags       = call.data.get("tags", [])
        locked_day = call.data.get("locked_day", "")
        requires   = call.data.get("requires", "").strip()
        if not name:
            return
        def _w():
            m = _load_dishes()
            entry = {"dagar": days, "taggar": tags}
            if locked_day:
                entry["låst_dag"] = locked_day
            if requires:
                entry["kräver"] = requires
            m[name] = entry
            _save_dishes(m)
            _add_tags_to_registry(tags)
        await hass.async_add_executor_job(_w)
        await _refresh_sensor(hass)

    async def handle_update_dish(call):
        old_name   = call.data.get("old_name", "").strip()
        name       = call.data.get("name", "").strip()
        days       = call.data.get("days", "vardag")
        tags       = call.data.get("tags", [])
        locked_day = call.data.get("locked_day", "")
        requires   = call.data.get("requires", "").strip()
        if not name:
            return
        def _w():
            m = _load_dishes()
            if old_name and old_name in m:
                del m[old_name]
            entry = {"dagar": days, "taggar": tags}
            if locked_day:
                entry["låst_dag"] = locked_day
            if requires:
                entry["kräver"] = requires
            m[name] = entry
            _save_dishes(m)
            _add_tags_to_registry(tags)
        await hass.async_add_executor_job(_w)
        await _refresh_sensor(hass)

    async def handle_remove_dish(call):
        name = call.data.get("name", "").strip()
        if not name:
            return
        def _w():
            m = _load_dishes()
            m.pop(name, None)
            _save_dishes(m)
        await hass.async_add_executor_job(_w)
        await _refresh_sensor(hass)

    # ── Tag services ───────────────────────────────────────────────

    async def handle_create_tag(call):
        name = call.data.get("name", "").strip().lower()
        if not name:
            return
        await hass.async_add_executor_job(_add_tags_to_registry, [name])
        await _refresh_sensor(hass)
        _LOGGER.info("Meal Solver 3000: created tag '%s'", name)

    async def handle_rename_tag(call):
        old_name = call.data.get("old_name", "").strip()
        new_name = call.data.get("new_name", "").strip()
        if not old_name or not new_name or old_name == new_name:
            return
        def _w():
            m = _load_dishes()
            for data in m.values():
                data["taggar"] = [new_name if t == old_name else t for t in data.get("taggar", [])]
            _save_dishes(m)
            tl = _load_tags()
            _save_tags([new_name if t == old_name else t for t in tl])
        await hass.async_add_executor_job(_w)
        await _refresh_sensor(hass)
        _LOGGER.info("Meal Solver 3000: renamed tag '%s'→'%s'", old_name, new_name)

    async def handle_remove_tag(call):
        name = call.data.get("name", "").strip()
        if not name:
            return
        def _w():
            m = _load_dishes()
            for data in m.values():
                data["taggar"] = [t for t in data.get("taggar", []) if t != name]
            _save_dishes(m)
            _save_tags([t for t in _load_tags() if t != name])
        await hass.async_add_executor_job(_w)
        await _refresh_sensor(hass)
        _LOGGER.info("Meal Solver 3000: removed tag '%s'", name)

    # ── Register services ──────────────────────────────────────────

    hass.services.async_register(DOMAIN, "generate_week",  handle_generate_week)
    hass.services.async_register(DOMAIN, "add_dish",       handle_add_dish)
    hass.services.async_register(DOMAIN, "update_dish",    handle_update_dish)
    hass.services.async_register(DOMAIN, "remove_dish",    handle_remove_dish)
    hass.services.async_register(DOMAIN, "create_tag",     handle_create_tag)
    hass.services.async_register(DOMAIN, "rename_tag",     handle_rename_tag)
    hass.services.async_register(DOMAIN, "remove_tag",     handle_remove_tag)

    await _refresh_sensor(hass)
    _LOGGER.info("Meal Solver 3000: ready")
    return True


async def async_setup_entry(hass, entry):
    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))
    return True

async def async_unload_entry(hass, entry):
    return True

async def _async_reload_entry(hass, entry):
    await hass.config_entries.async_reload(entry.entry_id)

import logging
import yaml
import json
import random
from datetime import date, timedelta
from pathlib import Path
from homeassistant.helpers.event import async_track_time_change
from homeassistant.helpers.start import async_at_started

DOMAIN = "meal_solver_3000"
_LOGGER = logging.getLogger(__name__)

BASE = Path("/config/Matlistor")
DISHES_FILE  = BASE / "matratter.yaml"
RULES_FILE   = BASE / "regler.yaml"
HISTORY_FILE = BASE / "historik.json"
TAGS_FILE    = BASE / "taggar.json"

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

_DEFAULT_REPEAT_INTERVAL = 14

_WEEKDAY_TO_INT = {
    "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
    "friday": 4, "saturday": 5, "sunday": 6,
}


# ── Dish file I/O ─────────────────────────────────────────────────────────────

def _ensure_base_dir():
    BASE.mkdir(parents=True, exist_ok=True)
    if not DISHES_FILE.exists():
        DISHES_FILE.write_text("{}\n", encoding="utf-8")

def _load_dishes() -> dict:
    _ensure_base_dir()
    with open(DISHES_FILE, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}

def _save_dishes(dishes: dict):
    _ensure_base_dir()
    with open(DISHES_FILE, "w", encoding="utf-8") as f:
        yaml.dump(dishes, f, allow_unicode=True, default_flow_style=False, sort_keys=True)

def _load_tags() -> list:
    if not TAGS_FILE.exists():
        # Seed only from tags the dishes file already uses. A fresh install
        # starts empty — the user builds their own vocabulary.
        try:
            m = _load_dishes()
            tags = sorted({t for d in m.values() for t in d.get("taggar", [])})
        except Exception:
            tags = []
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
    opts = entries[0].options if entries else {}
    hass.states.async_set(
        "sensor.meal_solver_matlista",
        len(dishes),
        {
            "dishes":          dishes,
            "known_tags":      known_tags,
            "language":        opts.get("language", "sv"),
            "auto_shuffle":    opts.get("auto_shuffle", True),
            "shuffle_weekday": opts.get("shuffle_weekday", "sunday"),
            "shuffle_time":    opts.get("shuffle_time", "17:00"),
            "friendly_name":   "Meal Solver Dish List",
        },
    )


# ── Rule parser ───────────────────────────────────────────────────────────────

def _parse_tag_rules(text: str) -> dict:
    # Tags are stored lower-case, so rules are matched lower-case too —
    # otherwise a rule typed as "Potatis" would silently never apply.
    result = {}
    for part in text.split(","):
        part = part.strip()
        if not part:
            continue
        parts = part.split(":", 1)
        if len(parts) == 2:
            try:
                result[parts[0].strip().lower()] = int(parts[1].strip())
            except ValueError:
                pass
    return result

def _parse_list(text: str) -> list:
    return [x.strip().lower() for x in text.split(",") if x.strip()]

def _build_rules(opts: dict) -> dict:
    try:
        with open(RULES_FILE, encoding="utf-8") as f:
            yaml_rules = yaml.safe_load(f) or {}
    except Exception:
        yaml_rules = {}

    # Options win, then regler.yaml. An unset field means "no constraint" —
    # never a hidden built-in rule the user didn't ask for.
    # regler.yaml used Swedish keys before the codebase was translated. Reading
    # only the English ones made existing files silently do nothing, so accept
    # both and let the English spelling win where a file has each.
    for eng, swe in (("max_per_week", "max_per_vecka"),
                     ("min_per_week", "min_per_vecka"),
                     ("no_consecutive", "ej_konsekutiv"),
                     ("repeat_interval_days", "repeat_intervall_dagar"),
                     ("max_attempts", "max_forsok")):
        if eng not in yaml_rules and swe in yaml_rules:
            yaml_rules[eng] = yaml_rules[swe]

    def _lower_keys(d):
        return {str(k).lower(): v for k, v in (d or {}).items()}

    max_per_week = (_parse_tag_rules(opts["max_rules"]) if "max_rules" in opts
                    else _lower_keys(yaml_rules.get("max_per_week", {})))
    min_per_week = (_parse_tag_rules(opts["min_rules"]) if "min_rules" in opts
                    else _lower_keys(yaml_rules.get("min_per_week", {})))
    no_consecutive = (_parse_list(opts["no_consecutive"]) if "no_consecutive" in opts
                      else [str(t).lower() for t in yaml_rules.get("no_consecutive", [])])

    return {
        "max_per_week": max_per_week,
        "min_per_week": min_per_week,
        "no_consecutive": no_consecutive,
        "repeat_interval_days": opts.get("repeat_interval",
                                  yaml_rules.get("repeat_interval_days",
                                  _DEFAULT_REPEAT_INTERVAL)),
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
            t = tag.lower()
            counts[t] = counts.get(t, 0) + 1
    return counts

def _max_ok(plan, dishes, rules, new_dish):
    counts = _tag_counts(plan, dishes)
    for tag in dishes[new_dish].get("taggar", []):
        max_count = rules.get("max_per_week", {}).get(tag.lower())
        if max_count is not None and counts.get(tag.lower(), 0) + 1 > max_count:
            return False
    return True

def _no_consecutive_ok(plan, dishes, rules, day, new_dish):
    no_consec = {str(t).lower() for t in rules.get("no_consecutive", [])}
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

def _copy_card_to_www(config_dir: str) -> str:
    """Copy the card into www/ and return the integration version."""
    import shutil
    here = Path(__file__).parent
    version = json.loads((here / "manifest.json").read_text(encoding="utf-8"))["version"]
    www_dir = Path(config_dir) / "www"
    www_dir.mkdir(exist_ok=True)
    shutil.copy2(here / "meal_solver_card.js", www_dir / "meal_solver_card.js")
    return version


async def _async_register_card_resource(hass, version):
    """Point the Lovelace resource at ?v=<version>.

    /local/ is served with caching headers, so a fixed URL leaves browsers
    holding a stale card indefinitely after an update. Moving the version into
    the query string makes each release a distinct URL. Best-effort: Lovelace
    in YAML mode has no writable resource collection, and there the user keeps
    managing the resource by hand.
    """
    url = f"/local/meal_solver_card.js?v={version}"
    try:
        lovelace = hass.data.get("lovelace")
        resources = getattr(lovelace, "resources", None)
        if resources is None and isinstance(lovelace, dict):
            resources = lovelace.get("resources")
        if resources is None:
            _LOGGER.warning(
                "Meal Solver 3000: Lovelace resources unavailable (hass.data['lovelace']=%r); "
                "add %s manually under Settings → Dashboards → Resources", lovelace, url)
            return
        if not hasattr(resources, "async_create_item"):
            _LOGGER.warning(
                "Meal Solver 3000: Lovelace is in YAML mode, so its resource list is "
                "read-only. Add %s manually to your YAML resources.", url)
            return

        if not getattr(resources, "loaded", True):
            await resources.async_load()
            resources.loaded = True

        ours = [
            item for item in resources.async_items()
            if str(item.get("url", "")).split("?")[0].endswith("/meal_solver_card.js")
        ]
        if not ours:
            await resources.async_create_item({"res_type": "module", "url": url})
            _LOGGER.warning("Meal Solver 3000: registered Lovelace resource %s", url)
        elif ours[0].get("url") != url:
            old = ours[0].get("url")
            await resources.async_update_item(ours[0]["id"], {"url": url})
            _LOGGER.warning(
                "Meal Solver 3000: Lovelace resource updated %s → %s. "
                "Reload the page once to pick up the new card.", old, url)
        else:
            _LOGGER.debug("Meal Solver 3000: Lovelace resource already at %s", url)
    except Exception as err:  # noqa: BLE001 — never block startup over this
        _LOGGER.warning(
            "Meal Solver 3000: could not manage the Lovelace resource "
            "automatically (%s). Add %s manually under Settings → Dashboards → Resources.",
            err, url,
        )


async def async_setup(hass, config):
    version = await hass.async_add_executor_job(
        _copy_card_to_www, hass.config.config_dir)

    # Deferred until HA is fully started — the Lovelace resource collection
    # does not exist yet while integrations are still being set up.
    async def _on_started(_hass):
        await _async_register_card_resource(hass, version)

    async_at_started(hass, _on_started)

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

        # History records the week that was actually eaten, so it is written
        # only at the weekly rollover — the scheduled run, just before the new
        # plan replaces the old one. A manual reshuffle mid-week must not
        # archive anything: the plan on the board then is one the scheduled run
        # just produced and nobody has eaten yet, and every stray entry shrinks
        # the candidate pool via the repeat interval.
        #
        # With auto-shuffle off there is no scheduled run, so manual shuffles
        # take over the rollover role — otherwise history would never grow and
        # the repeat interval would never engage. The ISO-week guard keeps that
        # to one entry per week either way.
        scheduled = call.data.get("scheduled", False)
        archives = scheduled or not opts.get("auto_shuffle", True)
        already_saved = await hass.async_add_executor_job(_this_week_saved)
        if archives and not already_saved:
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


def _register_auto_shuffle(hass, entry):
    """Set up (or cancel) the scheduled auto-shuffle time listener."""
    store = hass.data.setdefault(DOMAIN, {})

    # Cancel previous listener for this entry if any
    if entry.entry_id in store:
        store.pop(entry.entry_id)()

    opts = entry.options
    if not opts.get("auto_shuffle", True):
        return

    shuffle_time    = opts.get("shuffle_time", "17:00")
    shuffle_weekday = opts.get("shuffle_weekday", "sunday")
    try:
        h, m = [int(x) for x in shuffle_time.split(":")]
    except Exception:
        h, m = 17, 0
    target_weekday = _WEEKDAY_TO_INT.get(shuffle_weekday, 6)

    async def _scheduled_shuffle(now):
        if now.weekday() != target_weekday:
            return
        _LOGGER.info("Meal Solver 3000: auto-shuffle triggered (%s %s)", shuffle_weekday, shuffle_time)
        await hass.services.async_call(DOMAIN, "generate_week", {"scheduled": True})

    store[entry.entry_id] = async_track_time_change(hass, _scheduled_shuffle, hour=h, minute=m, second=0)


async def async_setup_entry(hass, entry):
    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))
    _register_auto_shuffle(hass, entry)
    return True

async def async_unload_entry(hass, entry):
    store = hass.data.get(DOMAIN, {})
    if entry.entry_id in store:
        store.pop(entry.entry_id)()
    return True

async def _async_reload_entry(hass, entry):
    await hass.config_entries.async_reload(entry.entry_id)

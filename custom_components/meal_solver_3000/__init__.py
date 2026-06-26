import logging
import yaml
import json
import random
from datetime import date, timedelta
from pathlib import Path

DOMAIN = "meal_solver_3000"
_LOGGER = logging.getLogger(__name__)

BASE = Path("/config/Matlistor")
MATRATTER_FILE = BASE / "matratter.yaml"
REGLER_FILE    = BASE / "regler.yaml"
HISTORIK_FILE  = BASE / "historik.json"

VARDAG_DAGAR = ["måndag", "tisdag", "onsdag", "torsdag"]
HELG_DAGAR   = ["fredag", "lördag", "söndag"]
ALLA_DAGAR   = VARDAG_DAGAR + HELG_DAGAR

DAG_ENTITY = {
    "måndag":  ("input_text.mandag_middag",  "input_boolean.mandag_last"),
    "tisdag":  ("input_text.tisdag_middag",  "input_boolean.tisdag_last"),
    "onsdag":  ("input_text.onsdag_middag",  "input_boolean.onsdag_last"),
    "torsdag": ("input_text.torsdag_middag", "input_boolean.torsdag_last"),
    "fredag":  ("input_text.fredag_middag",  "input_boolean.fredag_last"),
    "lördag":  ("input_text.lordag_middag",  "input_boolean.lordag_last"),
    "söndag":  ("input_text.sondag_middag",  "input_boolean.sondag_last"),
}

_OPTION_DEFAULTS = {
    "max_regler":       "köttfärs:2, fisk:1",
    "min_regler":       "vegetarisk:1",
    "ej_konsekutiv":    "potatis, ris, pasta, nudlar",
    "repeat_intervall": 14,
}


# ── Matliste-I/O ──────────────────────────────────────────────────────────────

def _load_matratter() -> dict:
    with open(MATRATTER_FILE, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}

def _save_matratter(matratter: dict):
    with open(MATRATTER_FILE, "w", encoding="utf-8") as f:
        yaml.dump(matratter, f, allow_unicode=True, default_flow_style=False,
                  sort_keys=True)

async def _refresh_sensor(hass):
    matratter = await hass.async_add_executor_job(_load_matratter)
    hass.states.async_set(
        "sensor.meal_solver_matlista",
        len(matratter),
        {"matratter": matratter, "friendly_name": "Meal Solver Matlista"},
    )


# ── Regelparser ───────────────────────────────────────────────────────────────

def _parse_tagg_regler(text: str) -> dict:
    result = {}
    for del_ in text.split(","):
        del_ = del_.strip()
        if not del_:
            continue
        delar = del_.split(":", 1)
        if len(delar) == 2:
            try:
                result[delar[0].strip()] = int(delar[1].strip())
            except ValueError:
                pass
    return result

def _parse_lista(text: str) -> list:
    return [x.strip() for x in text.split(",") if x.strip()]

def _build_regler(opts: dict) -> dict:
    try:
        with open(REGLER_FILE, encoding="utf-8") as f:
            yaml_regler = yaml.safe_load(f) or {}
    except Exception:
        yaml_regler = {}

    if "max_regler" in opts:
        max_per_vecka = _parse_tagg_regler(opts["max_regler"])
    else:
        max_per_vecka = yaml_regler.get("max_per_vecka",
                        _parse_tagg_regler(_OPTION_DEFAULTS["max_regler"]))

    if "min_regler" in opts:
        min_per_vecka = _parse_tagg_regler(opts["min_regler"])
    else:
        min_per_vecka = yaml_regler.get("min_per_vecka",
                        _parse_tagg_regler(_OPTION_DEFAULTS["min_regler"]))

    if "ej_konsekutiv" in opts:
        ej_konsekutiv = _parse_lista(opts["ej_konsekutiv"])
    else:
        ej_konsekutiv = yaml_regler.get("ej_konsekutiv",
                        _parse_lista(_OPTION_DEFAULTS["ej_konsekutiv"]))

    return {
        "max_per_vecka": max_per_vecka,
        "min_per_vecka": min_per_vecka,
        "ej_konsekutiv": ej_konsekutiv,
        "repeat_intervall_dagar": opts.get("repeat_intervall",
                                    yaml_regler.get("repeat_intervall_dagar",
                                    _OPTION_DEFAULTS["repeat_intervall"])),
        "max_forsok": yaml_regler.get("max_forsok", 1000),
    }


# ── Solver ────────────────────────────────────────────────────────────────────

def _load_historik():
    if not HISTORIK_FILE.exists():
        return []
    with open(HISTORIK_FILE, encoding="utf-8") as f:
        return json.load(f)

def _save_historik(plan):
    historik = _load_historik()
    historik.append({"datum": date.today().isoformat(), "plan": plan})
    with open(HISTORIK_FILE, "w", encoding="utf-8") as f:
        json.dump(historik, f, ensure_ascii=False, indent=2)

def _ratterna_inom_intervall(historik, intervall_dagar):
    cutoff = date.today() - timedelta(days=intervall_dagar)
    uteslut = set()
    for vecka in historik:
        if date.fromisoformat(vecka["datum"]) >= cutoff:
            uteslut.update(vecka["plan"].values())
    return uteslut

def _kandidater(matratter, dag_typ, uteslut, lasta_rattter):
    pool = [
        namn for namn, data in matratter.items()
        if data.get("dagar") in (dag_typ, "båda")
        and namn not in uteslut
        and namn not in lasta_rattter.values()
        and not data.get("låst_dag")
    ]
    random.shuffle(pool)
    return pool

def _tag_counts(plan, matratter):
    counts = {}
    for ratt in plan.values():
        for tagg in matratter.get(ratt, {}).get("taggar", []):
            counts[tagg] = counts.get(tagg, 0) + 1
    return counts

def _max_ok(plan, matratter, regler, ny_ratt):
    counts = _tag_counts(plan, matratter)
    for tagg in matratter[ny_ratt].get("taggar", []):
        max_antal = regler.get("max_per_vecka", {}).get(tagg)
        if max_antal is not None and counts.get(tagg, 0) + 1 > max_antal:
            return False
    return True

def _konsekutiv_ok(plan, matratter, regler, dag, ny_ratt):
    ej_konk = set(regler.get("ej_konsekutiv", []))
    if not ej_konk:
        return True
    idx = ALLA_DAGAR.index(dag)
    if idx == 0:
        return True
    foregaende = plan.get(ALLA_DAGAR[idx - 1])
    if not foregaende or foregaende not in matratter:
        return True
    ny_rel   = {t.lower() for t in matratter[ny_ratt].get("taggar", [])} & ej_konk
    fore_rel = {t.lower() for t in matratter[foregaende].get("taggar", [])} & ej_konk
    if not ny_rel or not fore_rel:
        return True
    return not (ny_rel == fore_rel and len(ny_rel) == 1)

def _min_ok(plan, matratter, regler):
    counts = _tag_counts(plan, matratter)
    for tagg, min_antal in regler.get("min_per_vecka", {}).items():
        if counts.get(tagg, 0) < min_antal:
            return False
    return True

def _solve(lasta_rattter, regler):
    matratter = _load_matratter()
    historik   = _load_historik()
    intervall  = regler.get("repeat_intervall_dagar", 14)
    max_forsok = regler.get("max_forsok", 1000)
    uteslut    = _ratterna_inom_intervall(historik, intervall)
    uteslut   -= set(lasta_rattter.values())

    yaml_lasta = {
        data["låst_dag"]: namn
        for namn, data in matratter.items()
        if data.get("låst_dag") and data["låst_dag"] in ALLA_DAGAR
    }

    for _ in range(max_forsok):
        plan = {**yaml_lasta, **lasta_rattter}
        vardag_pool = _kandidater(matratter, "vardag", uteslut, lasta_rattter)
        helg_pool   = _kandidater(matratter, "helg",   uteslut, lasta_rattter)

        ok = True
        for dag in ALLA_DAGAR:
            if dag in plan:
                continue
            pool = helg_pool if dag in HELG_DAGAR else vardag_pool
            vald = next(
                (r for r in pool
                 if r not in plan.values()
                 and _max_ok(plan, matratter, regler, r)
                 and _konsekutiv_ok(plan, matratter, regler, dag, r)),
                None
            )
            if vald is None:
                ok = False
                break
            plan[dag] = vald

        if ok and _min_ok(plan, matratter, regler):
            return plan

    return None


# ── HA-integration ────────────────────────────────────────────────────────────

async def async_setup(hass, config):

    # ── Vecka-tjänst ──────────────────────────────────────────────

    async def handle_generera_vecka(call):
        entries = hass.config_entries.async_entries(DOMAIN)
        opts = entries[0].options if entries else {}
        regler = await hass.async_add_executor_job(_build_regler, opts)

        lasta_rattter = {}
        for dag, (text_eid, bool_eid) in DAG_ENTITY.items():
            bool_state = hass.states.get(bool_eid)
            if bool_state and bool_state.state == "on":
                text_state = hass.states.get(text_eid)
                if text_state and text_state.state not in ("", "unknown"):
                    lasta_rattter[dag] = text_state.state

        plan = await hass.async_add_executor_job(_solve, lasta_rattter, regler)

        if plan is None:
            _LOGGER.error("Meal Solver 3000: kunde inte hitta giltig veckoplan")
            return

        for dag, ratt in plan.items():
            text_eid, _ = DAG_ENTITY[dag]
            await hass.services.async_call(
                "input_text", "set_value",
                {"entity_id": text_eid, "value": ratt},
                blocking=True,
            )

        await hass.async_add_executor_job(_save_historik, plan)
        _LOGGER.info("Meal Solver 3000: ny veckoplan — %s", date.today())

    # ── Matliste-tjänster ─────────────────────────────────────────

    async def handle_lagg_till_ratt(call):
        namn   = call.data.get("namn", "").strip()
        dagar  = call.data.get("dagar", "vardag")
        taggar = call.data.get("taggar", [])
        last_dag = call.data.get("låst_dag", "")

        if not namn:
            _LOGGER.warning("lagg_till_ratt: namn saknas")
            return

        def _write():
            m = _load_matratter()
            entry = {"dagar": dagar, "taggar": taggar}
            if last_dag:
                entry["låst_dag"] = last_dag
            m[namn] = entry
            _save_matratter(m)

        await hass.async_add_executor_job(_write)
        await _refresh_sensor(hass)
        _LOGGER.info("Meal Solver 3000: lade till '%s'", namn)

    async def handle_uppdatera_ratt(call):
        gammalt_namn = call.data.get("gammalt_namn", "").strip()
        nytt_namn    = call.data.get("namn", "").strip()
        dagar        = call.data.get("dagar", "vardag")
        taggar       = call.data.get("taggar", [])
        last_dag     = call.data.get("låst_dag", "")

        if not nytt_namn:
            _LOGGER.warning("uppdatera_ratt: namn saknas")
            return

        def _write():
            m = _load_matratter()
            if gammalt_namn and gammalt_namn in m:
                del m[gammalt_namn]
            entry = {"dagar": dagar, "taggar": taggar}
            if last_dag:
                entry["låst_dag"] = last_dag
            m[nytt_namn] = entry
            _save_matratter(m)

        await hass.async_add_executor_job(_write)
        await _refresh_sensor(hass)
        _LOGGER.info("Meal Solver 3000: uppdaterade '%s'→'%s'", gammalt_namn, nytt_namn)

    async def handle_ta_bort_ratt(call):
        namn = call.data.get("namn", "").strip()
        if not namn:
            return

        def _write():
            m = _load_matratter()
            m.pop(namn, None)
            _save_matratter(m)

        await hass.async_add_executor_job(_write)
        await _refresh_sensor(hass)
        _LOGGER.info("Meal Solver 3000: tog bort '%s'", namn)

    # ── Registrera ────────────────────────────────────────────────

    hass.services.async_register(DOMAIN, "generera_vecka",  handle_generera_vecka)
    hass.services.async_register(DOMAIN, "lagg_till_ratt",  handle_lagg_till_ratt)
    hass.services.async_register(DOMAIN, "uppdatera_ratt",  handle_uppdatera_ratt)
    hass.services.async_register(DOMAIN, "ta_bort_ratt",    handle_ta_bort_ratt)

    await _refresh_sensor(hass)
    _LOGGER.info("Meal Solver 3000: redo")
    return True


async def async_setup_entry(hass, entry):
    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))
    return True

async def async_unload_entry(hass, entry):
    return True

async def _async_reload_entry(hass, entry):
    await hass.config_entries.async_reload(entry.entry_id)

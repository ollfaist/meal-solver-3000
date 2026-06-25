#!/usr/bin/env python3
"""
Meal Solver 3000
Väljer veckans middagar baserat på matratter.yaml och regler.yaml.
Respekterar tagg-begränsningar, låsta dagar, repeat-intervall och konsekutiva tillbehör.
"""

import yaml
import json
import random
from datetime import date, timedelta
from pathlib import Path

BASE = Path(__file__).parent
MATRATTER_FILE = BASE / "matratter.yaml"
REGLER_FILE    = BASE / "regler.yaml"
HISTORIK_FILE  = BASE / "historik.json"

VECKODAGAR   = ["måndag", "tisdag", "onsdag", "torsdag", "fredag", "lördag", "söndag"]
VARDAG_DAGAR = ["måndag", "tisdag", "onsdag", "torsdag"]
HELG_DAGAR   = ["fredag", "lördag", "söndag"]
ALLA_DAGAR   = VARDAG_DAGAR + HELG_DAGAR


def load_yaml(path):
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_historik():
    if not HISTORIK_FILE.exists():
        return []
    with open(HISTORIK_FILE, encoding="utf-8") as f:
        return json.load(f)


def save_historik(historik):
    with open(HISTORIK_FILE, "w", encoding="utf-8") as f:
        json.dump(historik, f, ensure_ascii=False, indent=2)


def ratterna_inom_intervall(historik, intervall_dagar):
    """Returnerar set med rätter serverade inom repeat-intervallet."""
    cutoff = date.today() - timedelta(days=intervall_dagar)
    uteslut = set()
    for vecka in historik:
        vecko_datum = date.fromisoformat(vecka["datum"])
        if vecko_datum >= cutoff:
            uteslut.update(vecka["plan"].values())
    return uteslut


def kandidater(matratter, dag_typ, uteslut):
    """Returnerar shufflade kandidater för given dagtyp."""
    pool = [
        namn for namn, data in matratter.items()
        if data.get("dagar") in (dag_typ, "båda")
        and namn not in uteslut
        and not data.get("låst_dag")
    ]
    random.shuffle(pool)
    return pool


def tag_counts(plan, matratter):
    """Räknar tagg-förekomster i nuvarande plan."""
    counts = {}
    for ratt in plan.values():
        for tagg in matratter[ratt].get("taggar", []):
            counts[tagg] = counts.get(tagg, 0) + 1
    return counts


def max_ok(plan, matratter, regler, ny_ratt):
    """Kontrollerar att en ny rätt inte bryter max-per-vecka-regler."""
    counts = tag_counts(plan, matratter)
    for tagg in matratter[ny_ratt].get("taggar", []):
        max_antal = regler.get("max_per_vecka", {}).get(tagg)
        if max_antal is not None and counts.get(tagg, 0) + 1 > max_antal:
            return False
    return True


def konsekutiv_ok(plan, matratter, regler, dag, ny_ratt):
    """Kontrollerar att ny rätt inte delar ej_konsekutiv-tagg med föregående dag."""
    ej_konk = set(regler.get("ej_konsekutiv", []))
    if not ej_konk:
        return True

    dag_index = ALLA_DAGAR.index(dag)
    if dag_index == 0:
        return True

    foregaende_dag = ALLA_DAGAR[dag_index - 1]
    foregaende_ratt = plan.get(foregaende_dag)
    if not foregaende_ratt:
        return True

    ny_relevant   = {t.lower() for t in matratter[ny_ratt].get("taggar", [])} & ej_konk
    fore_relevant = {t.lower() for t in matratter[foregaende_ratt].get("taggar", [])} & ej_konk

    if not ny_relevant or not fore_relevant:
        return True

    # Konflikt bara om båda har exakt samma enda alternativ — annars finns alltid ett escape
    return not (ny_relevant == fore_relevant and len(ny_relevant) == 1)


def min_ok(plan, matratter, regler):
    """Kontrollerar att min-per-vecka uppfylls när planen är komplett."""
    counts = tag_counts(plan, matratter)
    for tagg, min_antal in regler.get("min_per_vecka", {}).items():
        if counts.get(tagg, 0) < min_antal:
            return False
    return True


def solve(matratter, regler, historik):
    intervall  = regler.get("repeat_intervall_dagar", 14)
    max_forsok = regler.get("max_forsok", 1000)
    uteslut    = ratterna_inom_intervall(historik, intervall)

    # Hitta låsta dagar
    lasta = {}
    for namn, data in matratter.items():
        if data.get("låst_dag"):
            dag = data["låst_dag"]
            if dag in ALLA_DAGAR:
                lasta[dag] = namn

    for _ in range(max_forsok):
        plan = dict(lasta)

        vardag_pool = kandidater(matratter, "vardag", uteslut)
        helg_pool   = kandidater(matratter, "helg",   uteslut)

        ok = True
        for dag in ALLA_DAGAR:
            if dag in plan:
                continue

            pool = helg_pool if dag in HELG_DAGAR else vardag_pool

            vald = None
            for ratt in pool:
                if (ratt not in plan.values()
                        and max_ok(plan, matratter, regler, ratt)
                        and konsekutiv_ok(plan, matratter, regler, dag, ratt)):
                    vald = ratt
                    break

            if vald is None:
                ok = False
                break

            plan[dag] = vald

        if ok and min_ok(plan, matratter, regler):
            return plan

    raise RuntimeError(
        f"Meal Solver 3000: kunde inte hitta giltig veckoplan efter {max_forsok} försök. "
        "Kontrollera att reglerna inte är för restriktiva eller att listorna har tillräckligt många rätter."
    )


def main():
    matratter = load_yaml(MATRATTER_FILE)
    regler    = load_yaml(REGLER_FILE)
    historik  = load_historik()

    plan = solve(matratter, regler, historik)

    print("\n=== Meal Solver 3000 — Veckans middagar ===")
    for dag in VECKODAGAR:
        ratt = plan.get(dag, "—")
        print(f"  {dag.capitalize():<10} {ratt}")
    print()

    historik.append({
        "datum": date.today().isoformat(),
        "plan": plan
    })
    save_historik(historik)
    print(f"Historik sparad ({len(historik)} veckor).")

    return plan


if __name__ == "__main__":
    main()

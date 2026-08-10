# Meal Solver 3000

Smart weekly dinner planner for Home Assistant. Randomizes 7 dinners per week using rule-based constraints, a tag system, and a history log that prevents repeats.

## Features

- Randomizes Mon–Sun with separate dish pools for weekdays and weekends
- **Tag rules** — configurable max/min per tag per week (e.g. max 2 minced meat, min 1 vegetarian)
- **No consecutive side dish** — potato/rice/pasta/noodles won't appear two days in a row
- **Repeat interval** — a dish can't reappear until after X days (default 14)
- **Locked days** — lock any day so it's skipped when reshuffling
- **Permanent day lock** — a dish can be pinned to a specific weekday via `locked_day` in the YAML (e.g. Tacos always on Friday)
- **Dish dependency** — a dish can require another dish to be in the same week (`requires` field)
- **History** — current week is saved once (on Sunday) before generating the new plan, so the repeat interval works correctly across weeks
- **Tag registry** — manage tags independently of dishes; unused tags shown at reduced opacity
- **Statistics** — dish count per category (weekday / weekend / both) shown in the dish list

## Lovelace card

Three tabs:

| Tab | Description |
|-----|-------------|
| **Veckoplan** | Shows Mon–Sun with lock toggle, inline edit, and shuffle button |
| **Matlistan** | Full dish list filtered by category; add, edit, remove dishes |
| **Taggar** | Tag registry; add new tags, remove unused ones |

## HA Services

| Service | Description |
|---------|-------------|
| `meal_solver_3000.generate_week` | Generate a new weekly plan (respects locks) |
| `meal_solver_3000.add_dish` | Add a new dish to the list |
| `meal_solver_3000.update_dish` | Update an existing dish |
| `meal_solver_3000.remove_dish` | Remove a dish |
| `meal_solver_3000.create_tag` | Add a new tag to the registry |
| `meal_solver_3000.rename_tag` | Rename a tag (updates all dishes using it) |
| `meal_solver_3000.remove_tag` | Remove a tag from the registry |

## Configuration (Integrations UI)

Go to **Settings → Devices & Services → Meal Solver 3000 → Configure**:

| Option | Default | Description |
|--------|---------|-------------|
| Max rules | `köttfärs:2, fisk:1` | Max occurrences per tag per week |
| Min rules | `vegetarisk:1` | Min occurrences per tag per week |
| No consecutive | `potatis, ris, pasta, nudlar` | Tags that can't appear two days in a row |
| Repeat interval | `14` | Days before the same dish can reappear |

## matratter.yaml format

```yaml
Köttbullar med potatis:
  dagar: vardag          # vardag / helg / båda
  taggar: [köttfärs, potatis]

Tacos:
  dagar: helg
  taggar: [köttfärs]
  locked_day: fredag     # always placed on Friday, regardless of locks

Lasagne:
  dagar: vardag
  taggar: [köttfärs, pasta]
  requires: Spagetti & Köttfärssås  # only planned if this dish is also in the week
```

## Installation

1. Copy `custom_components/meal_solver_3000/` to `/config/custom_components/`
2. Copy `Matlistor/` to `/config/Matlistor/`
3. Copy `www/meal_solver_card.js` to `/config/www/`
4. Create required entities (see below)
5. Restart HA
6. Go to **Settings → Devices & Services → + Add integration** → search "Meal Solver 3000"
7. Add the Lovelace card resource: `/local/meal_solver_card.js?v=9`

### Required entities

```yaml
input_text:
  mandag_middag:
  tisdag_middag:
  onsdag_middag:
  torsdag_middag:
  fredag_middag:
  lordag_middag:
  sondag_middag:

input_boolean:
  mandag_last:
  tisdag_last:
  onsdag_last:
  torsdag_last:
  fredag_last:
  lordag_last:
  sondag_last:
```

## File structure

```
custom_components/meal_solver_3000/
  __init__.py       — solver + HA services
  config_flow.py    — settings UI (Integrations page)
  manifest.json
  services.yaml
  strings.json

Matlistor/
  matratter.yaml    — all dishes with metadata
  regler.yaml       — default rules (overridden by config flow)
  historik.json     — weekly history (auto-generated)
  taggar.json       — tag registry (auto-generated)

www/
  meal_solver_card.js — Lovelace custom card
```

## Roadmap

- [ ] **Ingredients per dish** — store and edit ingredient lists per dish
- [ ] **Weekly shopping list** — aggregate ingredients for the current week's plan
- [ ] **Recipe search** — link a dish to an online recipe
- [ ] **AI recipe generation** — generate a recipe from available ingredients

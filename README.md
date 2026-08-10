# Meal Solver 3000

Smart weekly dinner planner for Home Assistant. Randomizes 7 dinners per week using rule-based constraints, a tag system, and a history log that prevents repeats.

## Features

- Randomizes Mon–Sun with separate dish pools for weekdays and weekends
- **Tag rules** — optional max/min per tag per week (e.g. max 2 minced meat, min 1 vegetarian)
- **No consecutive side dish** — optionally stop tags like potato/rice/pasta from landing two days in a row
- **Repeat interval** — a dish can't reappear until after X days (default 14, set 0 to disable)
- **Auto-shuffle** — generates a new plan on a configurable weekday and time, or turn it off for manual-only
- **Locked days** — lock any day so it's skipped when reshuffling
- **Permanent day lock** — a dish can be pinned to a specific weekday via `låst_dag` in the YAML (e.g. Tacos always on Friday)
- **Dish dependency** — a dish can require another dish to be in the same week (`kräver` field)
- **History** — the current plan is saved at most once per ISO week before a new one is generated, so the repeat interval works across weeks no matter how often you reshuffle
- **Tag registry** — manage tags independently of dishes; unused tags shown at reduced opacity
- **Statistics** — dish count per category (weekday / weekend / both) shown in the dish list
- **Bilingual** — card UI in Swedish or English

A fresh install starts completely empty: no dishes, no tags, and no rules. You build your own.

## Lovelace card

Three tabs:

| Tab (sv / en) | Description |
|---------------|-------------|
| **Veckoplan** / Week plan | Mon–Sun with lock toggle, inline edit with autocomplete, and shuffle button. Footer shows the next scheduled shuffle |
| **Matlistan** / Dish list | Full dish list filtered by category; add, edit, remove dishes |
| **Taggar** / Tags | Tag registry; add, rename and remove tags. Click a tag's dish count to expand the dishes using it |

The card reads its language from the integration's **Card language** option.

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
| Max per week | *empty* | Max occurrences per tag per week. Format `tag:count`, e.g. `köttfärs:2, fisk:1`. Empty = no upper limit |
| Min per week | *empty* | Min occurrences per tag per week. Format `tag:count`, e.g. `vegetarisk:1`. Empty = no requirement |
| No consecutive | *empty* | Comma-separated tags that can't appear two days in a row, e.g. `potatis, ris, pasta`. Empty = allow anything |
| Repeat interval | `14` | Days before the same dish can reappear. `0` disables it |
| Card language | `sv` | Language for the Lovelace card — `sv` or `en` |
| Auto-shuffle | `on` | Whether to generate a new plan automatically. Turn off for manual-only |
| Shuffle day | `sunday` | Weekday the automatic shuffle runs |
| Shuffle time | `17:00` | Time of day for the automatic shuffle, `HH:MM` |

The three rule fields are empty by default and render empty in the UI — the values shown above are examples, not preset rules. Leaving a field blank disables that rule entirely. Tag names in rules are matched case-insensitively.

## matratter.yaml format

All keys are Swedish, including in an English-language setup — they are the
on-disk storage format, not UI labels.

```yaml
Köttbullar med potatis:
  dagar: vardag          # vardag / helg / båda
  taggar: [köttfärs, potatis]

Tacos:
  dagar: helg
  taggar: [köttfärs]
  låst_dag: fredag       # always placed on Friday, regardless of locks

Lasagne:
  dagar: vardag
  taggar: [köttfärs, pasta]
  kräver: Spagetti & Köttfärssås  # only planned if this dish is also in the week
```

| Key | Values | Meaning |
|-----|--------|---------|
| `dagar` | `vardag` / `helg` / `båda` | Which pool the dish belongs to. `vardag` = Mon–Thu, `helg` = Fri–Sun |
| `taggar` | list of strings | Tags used by the max/min and no-consecutive rules |
| `låst_dag` | weekday in Swedish | Pins the dish to that weekday every week |
| `kräver` | dish name | Only planned if the named dish is also in the week |

Tags used here are added to the registry automatically when a dish is saved
through the card.

## Installation via HACS (recommended)

1. In HACS → three-dot menu → **Custom repositories**
2. Add `https://github.com/ollfaist/meal-solver-3000` with category **Integration**
3. Install **Meal Solver 3000** and restart HA
4. Go to **Settings → Devices & Services → + Add integration** → search "Meal Solver 3000"
5. Create required entities (see below)
6. Add the Lovelace card resource: **Settings → Dashboards → three-dot menu → Resources**
   - URL: `/local/meal_solver_card.js`
   - Type: JavaScript module

## Manual installation

1. Copy `custom_components/meal_solver_3000/` to `/config/custom_components/`
2. Restart HA
3. Go to **Settings → Devices & Services → + Add integration** → search "Meal Solver 3000"
4. Create required entities (see below)
5. Add the Lovelace card resource: **Settings → Dashboards → three-dot menu → Resources**
   - URL: `/local/meal_solver_card.js`
   - Type: JavaScript module

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
  __init__.py           — solver + HA services
  config_flow.py        — settings UI (Integrations page)
  meal_solver_card.js   — Lovelace card, copied to /config/www/ on startup
  manifest.json
  services.yaml
  strings.json
  translations/
    sv.json, en.json    — config UI labels and field descriptions

Matlistor/                (created under /config/ on first run)
  matratter.yaml        — all dishes with metadata
  regler.yaml           — optional rule file, overridden by the config flow
  historik.json         — weekly history (auto-generated)
  taggar.json           — tag registry (auto-generated)
```

The card is shipped inside the integration and copied to `/config/www/` each
time HA starts, which is why the Lovelace resource URL is `/local/meal_solver_card.js`.
You never need to copy it by hand.

## Roadmap

- [ ] **Ingredients per dish** — store and edit ingredient lists per dish
- [ ] **Weekly shopping list** — aggregate ingredients for the current week's plan
- [ ] **Recipe search** — link a dish to an online recipe
- [ ] **AI recipe generation** — generate a recipe from available ingredients

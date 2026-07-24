# Meal Solver 3000

Smart weekly menu generator for Home Assistant. Randomizes the week's dinners with rule-based constraints and lockable days.

## Features

- Randomizes 7 dinners (Mon–Sun) with separate pools for weekdays and weekends
- Rule-driven constraints: max minced meat/week, max fish, min vegetarian
- No repeated side dish (potato/rice/pasta/noodles) on consecutive days
- Repeat interval — the same dish cannot appear again until after X days
- Lock optional days (e.g. Taco Friday) — the rest are reshuffled
- Configurable rules via HA's Integrations UI (config flow)
- Lovelace card with lock/edit/shuffle

## Structure

```
custom_components/meal_solver_3000/   # HA custom component
  __init__.py       – solver + HA integration
  config_flow.py    – settings via Integrations UI
  manifest.json
  services.yaml
  strings.json

Matlistor/
  matratter.yaml    – all dishes with metadata (dagar, taggar, låst_dag)
  regler.yaml       – default rules (overrideable via config flow)
  meal_solver_3000.py – standalone solver (runs without HA)

www/
  meal_solver_card.js – Lovelace custom card
```

## Installation

1. Copy `custom_components/meal_solver_3000/` to `/config/custom_components/`
2. Copy `Matlistor/` to `/config/Matlistor/`
3. Copy `www/meal_solver_card.js` to `/config/www/`
4. Add to `configuration.yaml`:
   ```yaml
   meal_solver_3000:
   ```
5. Create `input_text` and `input_boolean` entities for each day (see below)
6. Restart HA
7. Go to **Settings → Devices & Services → + Add integration** and search for "Meal Solver 3000"
8. Add the Lovelace card via Resources: `/local/meal_solver_card.js`

### Required entities

```yaml
# input_text (one per day, e.g. in configuration.yaml or input_text.yaml)
input_text:
  mandag_middag:
  tisdag_middag:
  onsdag_middag:
  torsdag_middag:
  fredag_middag:
  lordag_middag:
  sondag_middag:

# input_boolean (lock per day)
input_boolean:
  mandag_last:
  tisdag_last:
  onsdag_last:
  torsdag_last:
  fredag_last:
  lordag_last:
  sondag_last:
```

## Roadmap

Ideas and planned features:

- [ ] **Ingredients per dish** — store ingredient lists in `matratter.yaml` and edit them via the Lovelace card
- [ ] **Weekly shopping list** — new tab that aggregates ingredients for all 7 dishes in the current week's plan
- [ ] **Recipe search** — search for recipes online linked to a dish
- [ ] **AI recipe generation** — generate recipes via AI based on available ingredients at home

## matratter.yaml format

```yaml
Köttbullar med potatis:
  dagar: vardag          # vardag / helg / båda
  taggar: [köttfärs, potatis]

Tacos:
  dagar: helg
  taggar: [köttfärs]
  låst_dag: fredag       # always locked to Friday
```

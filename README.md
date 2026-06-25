# Meal Solver 3000

Smart veckomenygenerator för Home Assistant. Slumpar veckans middagar med regelbaserade begränsningar och låsbara dagar.

## Funktioner

- Slumpar 7 middagar (mån–sön) med separata pooler för vardag och helg
- Regelstyrda begränsningar: max köttfärs/vecka, max fisk, min vegetarisk
- Ingen samma sidorätt (potatis/ris/pasta/nudlar) två dagar i rad
- Repeat-intervall — samma rätt kan inte dyka upp igen förrän efter X dagar
- Lås valfria dagar (t.ex. Taco fredag) — övriga slumpas om
- Konfigurerbara regler via HA:s Integrations-UI (config flow)
- Lovelace-kort med lock/edit/slumpa-om

## Struktur

```
custom_components/meal_solver_3000/   # HA custom component
  __init__.py       – solver + HA-integration
  config_flow.py    – inställningar via Integrations-UI
  manifest.json
  services.yaml
  strings.json

Matlistor/
  matratter.yaml    – alla rätter med metadata (dagar, taggar, låst_dag)
  regler.yaml       – standardregler (override:as via config flow)
  meal_solver_3000.py – fristående solver (kör utan HA)

www/
  meal_solver_card.js – Lovelace custom card
```

## Installation

1. Kopiera `custom_components/meal_solver_3000/` till `/config/custom_components/`
2. Kopiera `Matlistor/` till `/config/Matlistor/`
3. Kopiera `www/meal_solver_card.js` till `/config/www/`
4. Lägg till i `configuration.yaml`:
   ```yaml
   meal_solver_3000:
   ```
5. Skapa `input_text` och `input_boolean` entiteter för varje dag (se nedan)
6. Starta om HA
7. Gå till **Inställningar → Enheter och tjänster → + Lägg till integration** och sök "Meal Solver 3000"
8. Lägg till Lovelace-kortet via Resurser: `/local/meal_solver_card.js`

### Entiteter som krävs

```yaml
# input_text (en per dag, t.ex. configuration.yaml eller input_text.yaml)
input_text:
  mandag_middag:
  tisdag_middag:
  onsdag_middag:
  torsdag_middag:
  fredag_middag:
  lordag_middag:
  sondag_middag:

# input_boolean (lås per dag)
input_boolean:
  mandag_last:
  tisdag_last:
  onsdag_last:
  torsdag_last:
  fredag_last:
  lordag_last:
  sondag_last:
```

## matratter.yaml-format

```yaml
Köttbullar med potatis:
  dagar: vardag          # vardag / helg / båda
  taggar: [köttfärs, potatis]

Tacos:
  dagar: helg
  taggar: [köttfärs]
  låst_dag: fredag       # låses alltid till fredag
```

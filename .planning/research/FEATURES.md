# Feature Landscape

**Domain:** ML model serving web UI (local Flask prediction tool)
**Researched:** 2026-03-08

---

## Context

This is a **local single-user prediction tool**, not a production SaaS application. The constraint set is narrow:
- Flask + HTML, no JS framework
- 142 binary amenity toggles (SYSTEM_* columns) + 4 numeric inputs
- Pre-trained XGBoost model loaded at server start, no retraining UI
- Localhost only; no auth, no deployment concerns

The UX challenge is almost entirely the 142-checkbox problem. Everything else is commodity Flask form work.

---

## Table Stakes

| Feature | Why Expected | Complexity |
|---------|--------------|------------|
| Form with all 142 amenity checkboxes | Core input — missing any amenity means silently wrong predictions | Low-Med |
| Numeric inputs for 4 fields | capacity, bedrooms, beds, bathrooms are required model features | Low |
| Server-side input validation | Model.predict() will crash on None/empty string | Low |
| Feature vector assembly in exact column order | XGBoost model expects features in training order | Low |
| Prediction result display on same page | User must see predicted ADR after submitting | Low |
| Model load at server start (not per-request) | Loading per-request adds avoidable latency | Low |
| Error display when prediction fails | Model errors should surface as readable messages, not 500 pages | Low |
| Form state preserved on result display | User should see which boxes they checked after submit | Low-Med |
| Dollar formatting on prediction output | Raw float (127.42983) is unreadable; display as $127.43 | Low |

---

## Differentiators

| Feature | Value Proposition | Complexity |
|---------|-------------------|------------|
| Amenity grouping / categorized sections | 142 flat checkboxes is overwhelming; grouping (Bathroom, Kitchen, Safety, etc.) makes form scannable | Low-Med |
| Feature importance display | Show which amenities model weighted most (XGBoost feature_importances_) | Med |
| Market context in result | Show mean/median ADR from training set alongside prediction | Low |
| Input range hints | Show "typical range: 1-20 guests" near capacity field | Low |
| Toggle all amenities off | Fast reset to baseline for A/B scenario testing | Low |

---

## Anti-Features

| Anti-Feature | Why Avoid |
|--------------|-----------|
| Retraining via UI | Out of scope; adds auth, file upload, job queue complexity |
| User accounts / sessions | Single-user local tool; adds nothing |
| Database persistence | Append to CSV if logging needed |
| JavaScript framework | PROJECT.md specifies Flask + HTML only |
| REST API / JSON endpoints | No external consumers; HTML form POST is sufficient |
| Real-time AJAX prediction | POST submit is sufficient for local tool |

---

## UX Notes on 142 Checkboxes

The 142 SYSTEM_* columns divide naturally into these categories:

- **Bathroom:** BATHTUB, HAIRDRYER, SHAMPOO, SOAP, HOT_WATER, TOILETRIES
- **Bedroom/Sleep:** BLANKETS, PILLOW, BLACKOUT_SHADES, IRON, WARDROBE, BED_KING
- **Kitchen:** COOKING_BASICS, REFRIGERATOR, MICROWAVE, DISHWASHER, STOVE, OVEN, etc.
- **Safety:** DETECTOR_SMOKE, DETECTOR_CO, FIRE_EXTINGUISHER, FIRST_AID_KIT
- **Laundry:** WASHER, DRYER
- **Children/Baby:** CRIB, PACK_N_PLAY, OUTLET_COVER, CORNER_GUARD, BABY_MONITOR, BABY_BATH
- **Tech/Work:** WI_FI, WORKSPACE, LAPTOP, TV, PORTABLE_WI_FI
- **Recreation:** PING_PONG, ARCADE_MACHINE, CHESS, PIANO, KAYAK, MOVIE, POOL, JACUZZI, GYM
- **Outdoor:** PATIO_BALCONY, GRILL, FIREPIT, HAMMOCK, POOL, PARKING, EV_CHARGER
- **Other:** SMOKING_ALLOWED, ELEVATOR, PETS, BREAKFAST, SAUNA, etc.

Human-readable labels: strip `SYSTEM_` prefix, replace underscores with spaces, title-case. `SYSTEM_PING_PONG` → "Ping Pong". Single Python function applied in Jinja2 template context.

---

## MVP Build Order

1. Model training script (XGBoost, 5-fold CV, save to disk)
2. Flask app with model load at start
3. Form with all 142 checkboxes + 4 numeric inputs, grouped in HTML fieldsets by category
4. Server-side validation
5. Feature vector assembly with correct column order
6. Prediction result display with dollar formatting
7. Form state preserved after POST

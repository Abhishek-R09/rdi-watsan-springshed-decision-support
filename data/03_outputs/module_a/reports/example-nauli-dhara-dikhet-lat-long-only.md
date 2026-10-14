# Spring vulnerability: Example - Nauli Dhara, Dikhet (lat-long only)

29.91903, 78.55647 · 1481 m · scored 2026-10-14 · Module A draft weights v1

## Score: 33 / 100, Low (confidence: Low)

**This is an exposure score, not a decline finding.** Nobody has said yet whether the flow has fallen. The score shows how exposed the spring's setting is compared with the other springs in the dataset. Ask the users about flow now vs 10-20 years ago (field form section 2) to turn it into a vulnerability score.

Indicators with data carry 34% of the full weight.

## Main reasons

- **Rain / evaporation demand (aridity index)** (66/100, 7.8 points): Yearly rain is 1.36 times the evaporation demand; 66% of the input springs are wetter. Less water left over for recharge after evaporation.
- **Land rising above the spring within 1 km** (63/100, 3.7 points): The land rises 274 m above the spring within 1 km; 63% of the input springs have more land above them. A spring close to a ridge top has little land above it to collect recharge.

Holding the score down:

- **Building growth within 1 km, 2016-2023** (5/100): Buildings within 1 km changed by -5% from 2016 to 2023; 5% of the input springs saw less growth.
- **Rainfall trend 2001-2025** (23/100): Yearly rain changed by -0.5% per decade over 2001-2025 (IMD); 23% of the input springs are drying more slowly or getting wetter.

## All indicators

| Group | Indicator | Value | Score (0-100) | Weight used | Points |
|---|---|---|---|---|---|
| Stressor (location) | Dry-season rain (Nov-Apr) | 211 mm | 37 | 21% | 7.5 |
| Stressor (location) | Rainfall trend 2001-2025 | -0.5% per decade | 23 | 15% | 3.4 |
| Stressor (location) | Building growth within 1 km, 2016-2023 | -5% | 5 | 15% | 0.7 |
| Stressor (location) | Rain / evaporation demand (aridity index) | 1.36 | 66 | 12% | 7.8 |
| Stressor (location) | Year-to-year rain variability | 18% | 11 | 9% | 0.9 |
| Stressor (location) | Built-up, cropland and bare land within 500 m | 2% | 38 | 9% | 3.4 |
| Stressor (location) | Buildings within 1 km (2023) | 352 | 47 | 9% | 4.1 |
| Stressor (location) | Mean slope within 500 m | 19 degrees | 16 | 6% | 1.0 |
| Stressor (location) | Land rising above the spring within 1 km | 274 m | 63 | 6% | 3.7 |
| | **Total** | | | 100% | **33** |

Location scores are percentiles among the input springs at 700 m or higher (higher = more exposed). Field scores use the field form bands: low 0, moderate 50, high 100.

## What would make this more reliable

- Flow now vs 10-20 years ago (weight 20): field (people's recall)
- Households per L/min of lean flow (weight 9): field (households + lean flow)
- Lean-season flow (May-June) (weight 6): field (bucket test or fill time)
- Monsoon flow / lean flow (weight 5): field (two readings)
- Months with low or no flow (weight 5): field (month calendar)
- Users now vs 10-20 years ago (weight 4): field (people's recall)
- Disturbance uphill (roads, fire, grazing, landslides) (weight 4): field
- Pollution sources within 30 m (weight 3): field
- Outlet protection and user committee (weight 3): field
- Recharge works uphill (weight 3): field
- Water quality (weight 2): field
- Seasonality label (weight 2): field or dataset label

## Context (not scored)

- Rock (GSI state map): Mixed (Carbonate, Phyllite, Shale): PHYLLITE, QTZ, SHALE,DOLOMITE, TUFF WITH DOLERITE (JAUNSAR)
- Nearest mapped fault: 2.7 km (Fault Observed)
- Soil 0-30 cm (SoilGrids): clay 27%, sand 33%
- Yearly rain (CHIRPS 2018-2025): 1775 mm (IMD 2001-2025: 1102 mm)
- Tree cover within 500 m: 69%
- Surface catchment above the spring (DEM): 8.3 ha. This is not the recharge area; Module B will estimate that.
- Nearest spring in the dataset: Nauli Dhara (ATL-SPR-0663, 0 m away, input data)

---
Draft: weights and cut-offs are Claude's proposal for WATSAN to review (config/module_a_indicators_v1.csv). Location values come from public maps at the coordinate given, not field measurement. Not yet checked against springs known to have declined; the held-out test springs will be used for that once, at the end.

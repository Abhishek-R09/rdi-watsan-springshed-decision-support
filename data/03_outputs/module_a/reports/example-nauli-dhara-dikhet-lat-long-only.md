# Spring vulnerability: Example - Nauli Dhara, Dikhet (lat-long only)

29.91903, 78.55647 · 1481 m · scored 2026-10-14 · Module A draft weights v1

## Score: 45 / 100, Medium (confidence: Low)

**This is an exposure score, not a decline finding.** Nobody has said yet whether the flow has fallen. The score shows how exposed the spring's setting is compared with the other springs in the dataset. Ask the users about flow now vs 10-20 years ago (field form section 2) to turn it into a vulnerability score.

Indicators with data carry 24% of the full weight.

## Main reasons

- **Rain / evaporation demand (aridity index)** (66/100, 11.0 points): Yearly rain is 1.36 times the evaporation demand; 66% of the input springs are wetter. Less water left over for recharge after evaporation.
- **Land rising above the spring within 1 km** (63/100, 7.9 points): The land rises 274 m above the spring within 1 km; 63% of the input springs have more land above them. A spring close to a ridge top has little land above it to collect recharge.
- **Year-to-year rain variability** (56/100, 6.9 points): Yearly rain varies by 13% from year to year; 56% of the input springs vary less. Dry years hit harder where rain swings a lot. Only 8 years of data, so a weak signal.

Holding the score down:

- **Mean slope within 500 m** (16/100): Mean slope within 500 m is 19 degrees; 16% of the input springs sit on gentler ground.
- **Dry-season rain (Nov-Apr)** (37/100): 211 mm falls in November-April on average; 37% of the input springs get more.

## All indicators

| Group | Indicator | Value | Score (0-100) | Weight used | Points |
|---|---|---|---|---|---|
| Stressor (location) | Dry-season rain (Nov-Apr) | 211 mm | 37 | 25% | 9.2 |
| Stressor (location) | Built-up, cropland and bare land within 500 m | 2% | 38 | 21% | 7.9 |
| Stressor (location) | Rain / evaporation demand (aridity index) | 1.36 | 66 | 17% | 11.0 |
| Stressor (location) | Year-to-year rain variability | 13% | 56 | 12% | 6.9 |
| Stressor (location) | Mean slope within 500 m | 19 degrees | 16 | 12% | 2.0 |
| Stressor (location) | Land rising above the spring within 1 km | 274 m | 63 | 12% | 7.9 |
| | **Total** | | | 100% | **45** |

Location scores are percentiles among the input springs at 700 m or higher (higher = more exposed). Field scores use the field form bands: low 0, moderate 50, high 100.

## What would make this more reliable

- Flow now vs 10-20 years ago (weight 30): field (people's recall)
- Households per L/min of lean flow (weight 10): field (households + lean flow)
- Lean-season flow (May-June) (weight 7): field (bucket test or fill time)
- Monsoon flow / lean flow (weight 6): field (two readings)
- Months with low or no flow (weight 5): field (month calendar)
- Disturbance uphill (roads, fire, grazing, landslides) (weight 5): field
- Pollution sources within 30 m (weight 3): field
- Outlet protection and user committee (weight 3): field
- Recharge works uphill (weight 3): field
- Water quality (weight 2): field
- Seasonality label (weight 2): field or dataset label

## Context (not scored)

- Rock (GSI state map): Mixed (Carbonate, Phyllite, Shale): PHYLLITE, QTZ, SHALE,DOLOMITE, TUFF WITH DOLERITE (JAUNSAR)
- Nearest mapped fault: 2.7 km (Fault Observed)
- Soil 0-30 cm (SoilGrids): clay 27%, sand 33%
- Yearly rain (CHIRPS 2018-2025): 1775 mm (IMD 2021-2025: 1103 mm)
- Tree cover within 500 m: 69%
- Surface catchment above the spring (DEM): 8.3 ha. This is not the recharge area; Module B will estimate that.
- Nearest spring in the dataset: Nauli Dhara (ATL-SPR-0663, 0 m away, input data)

---
Draft: weights and cut-offs are Claude's proposal for WATSAN to review (config/module_a_indicators_v1.csv). Location values come from public maps at the coordinate given, not field measurement. Not yet checked against springs known to have declined; the held-out test springs will be used for that once, at the end.

# Spring Health & Recharge Planner: user guide (v1 draft, 15 October 2026)

One spring goes in. Three results come out, on a map:

1. **Vulnerability assessment** (Module A). Is the spring at risk of declining? This gives a 0-100 score, a Low, Medium or High class, and the reasons.
2. **Springshed and recharge zone** (Module B). Where does the spring's water soak in? This gives the surface catchment, three nested recharge zones (small, likely, large), a recharge-potential map, and the best spots for recharge works.
3. **Potential impact of DI recharging** (Module C). What could rooftop water injected into defunct handpumps add to the spring? This gives the water injected, the added lean-season flow, the water-level rise, a travel time and a monitoring plan.

Everything runs on your laptop. The tool calls no paid service and uses no AI model. Each method is plain arithmetic on map layers and field answers, and every number comes with its reason.

## 1. Start it

**Windows (Rajat's laptop):** double-click **`start_tool.bat`** in the `Tool` folder.

- A black window opens and the page opens in your browser at http://127.0.0.1:8765.
- Keep the black window open while you use the tool. Close it to stop.

The start file looks for its map folders next to the `Tool` folder:

| Folder | What it holds |
|---|---|
| `DOCC\MapCache` | Map tiles |
| `DOCC\Data` | IMD, SoilGrids and CartoDEM files |

If your folders are elsewhere, set `SPRING_LAYER_CACHE` and `SPRING_LOCAL_LAYERS` before starting (see [run-module-a-locally.md](run-module-a-locally.md)).

**Any computer with Python set up:** run `python scripts/spring_tool_server.py --open`.

**Run times:**

| Run | Time |
|---|---|
| First run after starting | Up to a minute (it opens the maps) |
| Later runs | A few seconds |

Every run is saved in `data/03_outputs/tool_runs/<date-time>-<spring>/`:

- `request.json`: what was entered
- `result.json`: everything the page shows
- `report.md`: the three reports

## 2. Use it

1. **Spring.** Pick the spring in one of three ways:
   - Search the 1,643 springs in the dataset by name, village or district.
   - Click the map.
   - Type the latitude and longitude.

   The GPS elevation is optional. If you leave it blank, the tool uses the map elevation.
2. **Field observations** (optional). Every answer improves the result:
   - Flow now vs 10-20 years ago matters most for vulnerability. It is the only direct sign of decline.
   - Monsoon flow sizes the recharge zone.
   - The rock tilt (dip direction and angle) lets the zone extend beyond the ridge when the rock layers slope down towards the spring.
3. **DI plan** (optional). Click **Add DI site**, click the map where the handpump is, and enter the roof area. You can open **Assumptions** to change:
   - the rainfall;
   - the share of roof rain collected;
   - the length of the lean season.
4. Click **Assess this spring**. The three results appear as tabs. The map shows the layers for the tab you are on.
5. **Print report** prints the three sections.

## 3. What each section does

### Vulnerability (Module A)

The method is unchanged from [module-a-vulnerability.md](module-a-vulnerability.md):

- There are 20 indicators in four groups (state, impact, stressor, response) with WATSAN-draft weights.
- Map indicators are scored as percentiles among the input springs.
- With location only, the result is an **exposure score**: it shows how exposed the setting is, not whether the spring is declining.

### Springshed and recharge zone (Module B)

`scripts/module_b_springshed.py`, with weights in `config/module_b_recharge_factors_v1.csv`.

1. **Surface catchment.** This is the land that drains to the spring, taken from the 30 m Copernicus elevation map. The tool allows 30 m for GPS and map error.
2. **Search area.** The tool searches uphill of the spring:
   - from the spring's level up to 400 m above it (delineated Garhwal springsheds span 80-360 m of relief; the Chamba springs span 160-490 m);
   - within 2 km of the spring;
   - beyond the ridge only when the rock tilt says so.
3. **Recharge potential.** Each 30 m cell gets a score from 0 to 1:

   | Factor | Weight | What scores high |
   |---|---|---|
   | Slope | 30% | Gentle ground |
   | Land cover | 25% | Forest; built-up land scores low |
   | Rock type (GSI map) | 25% | Fractured or porous rock such as carbonate and quartzite; shale and phyllite score low |
   | Distance to a fault or lineament | 20% | Within 100 m |

4. **Size.** The target size comes from the monsoon flow, using the area-flow relation of 35 delineated springsheds (Rathi 2021): area ≈ 0.20 × flow^0.68 ha. With no flow reading, the typical 1.5 / 3 / 8 ha of hill springsheds is used.
5. **Zone.** The zone is grown uphill from the spring, best cells first. It never crosses a stream channel. The small and likely zones also never cross a mapped fault.

   When the rock tilt is entered, cells up-dip of the spring come first. The springshed can then lie mostly or wholly outside the surface catchment. The tab shows what share of the springshed lies outside the catchment.

The map shows the **surface catchment** (dashed blue: where rain runs off towards the spring) and the **springshed** (green: where rain soaks in and feeds it) as separate layers, because the two are not the same area.

**Confidence** is Low by default. It is Medium when both the monsoon flow and the rock tilt are given and the GSI geology covers the spring.

**Limits:**

- The GSI geology covers Uttarakhand only.
- The zones have not yet been checked against field-delineated springsheds. The 10 Spring Atlas profile springs are kept aside for that one-time check.
- Walk the zone with a geologist before spending money on works.

### Potential impact of DI recharging (Module C)

`scripts/module_c_di_impact.py`.

**Water injected** = roof area × yearly rain × 0.8 collected × 0.85 kept after the first flush. All of these can be changed under Assumptions.

**Rain source:**

- The IMD gauge mean is used when the IMD files are present.
- Otherwise the CHIRPS satellite estimate is used. It reads about 45% above IMD in these hills.
- You can type in a local value instead.

**Share reaching the spring** depends on where the handpump sits. These shares are judgement and should be replaced by monitoring.

| Where the handpump is | Share reaching the spring (low, mid, best) |
|---|---|
| Inside the likely zone | 30%, 60%, 100% |
| Inside the large zone only | 10%, 30%, 60% |
| Elsewhere in the catchment | 5%, 15%, 30% |
| Outside the catchment | 0%, 2%, 10% |
| Below the spring | None |

**Added flow** is shown two ways:

- spread over the year;
- best case, all of it coming out in the lean season (5 months by default).

When the lean flow is known, the tool also shows the added flow as a % of today's lean flow and the number of 100 m² roofs needed for +10%.

**Water-level rise** is the temporary mound after the wettest month: volume ÷ (circle of 50 m radius × specific yield). Specific yield is 0.5-3% for hard rock and 8-16% for alluvium or debris.

**Travel time** is distance ÷ (permeability × slope of the water table ÷ porosity), using wide hard-rock ranges. Treat it as an order of magnitude only.

The section also lists water-safety flags (no first-flush diverter, no filter), benchmarks (ICIMOD: +23% and +48% after full springshed treatment) and a monitoring plan. The monitoring plan is how these estimates will be replaced by real numbers.

## 4. Working offline with an approved map set

Without an approved map set, the tool downloads missing map tiles as needed. That needs internet the first time for a new area.

To make results repeatable and offline, prepare and approve a map set once:

```
python scripts\module_a_snapshot.py prepare --by "Rajat"
python scripts\module_a_snapshot.py approve <name it prints> --by "Rajat"
```

After that, the tool reads only those files. The header shows the map set name, and every saved run records it.

- After adding new data (another IMD year, say), run `prepare --rebuild-reference` and approve the new set.
- For a new area, add `--bbox WEST SOUTH EAST NORTH`.

## 5. Change the page

The built page is in `app/dist/` and is committed, so the laptop needs no Node.js. To change the page, edit `app/src/` and rebuild with Node.js (`npm ci`, then `npm run build` in `app/`). The data passed between the page and the modules is defined once, in `app/src/api.ts`.

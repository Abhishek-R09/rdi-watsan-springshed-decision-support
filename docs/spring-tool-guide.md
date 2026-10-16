# Spring Health & Recharge Planner: user guide (v1.1 draft, 16 October 2026)

One spring goes in. Three results come out, on a map:

1. **Vulnerability assessment** (Module A). Is the spring at risk of declining? This gives a 0-100 score, a Low, Medium or High class, and the reasons.
2. **Springshed and recharge zone** (Module B). Where does the spring's water soak in? This gives the surface catchment, the top three recharge zones (R1-R3) wherever they lie, on the spring's own slope or beyond the ridge, and a recharge-potential map.
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

SoilGrids files can sit either as `SoilGrids\clay_0-5cm_mean.tif` or in depth folders such as `SoilGrids\0-5 soilgrids\clay.tif` (the laptop's layout). Both are read.

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
   - The rock tilt (dip direction and angle) lets the tool look for recharge ground up-dip of the spring, even beyond the ridge.
3. **DI plan** (optional). Click **Add DI site**, click the map where the handpump is, and enter the roof area. You can open **Assumptions** to change:
   - the rainfall;
   - the share of roof rain collected;
   - the length of the lean season.
4. Click **Assess this spring**. The three results appear as tabs. The map shows only the layers for the tab you are on:

   | Tab | What the map shows |
   |---|---|
   | Vulnerability | The 500 m and 1 km circles the map indicators are measured in, land cover inside 1 km (disturbed land drawn strong), and nearby dataset springs |
   | Springshed | Surface catchment, the top recharge zones R1-R3 and the fault or crack that links each one to the spring, faults, lineaments, streams, and the heat map switch |
   | DI impact | DI sites coloured by where they sit, with the recharge zones and catchment drawn faintly for context |

   The map is 3D by default: right-drag (or Ctrl + drag) to tilt and turn it. Heights are drawn 1.5 times. The **2D** button flattens it, and the background can be satellite, a topo map or streets. The 3D hills come from the tool's own elevation tiles, so they show even when the background cannot download.
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
2. **Search area.** The tool looks for recharge ground in one search, on the spring's own slope and beyond it:
   - up to 4 km from the spring;
   - every cell must be linked to the spring in one of four ways (see step 5);
   - cells linked only by a fault, a crack or rock tilt must be at least 20 m above the spring.
3. **Recharge potential.** Each 30 m cell gets a score from 0 to 1:

   | Factor | Weight | What scores high |
   |---|---|---|
   | Slope | 25% | Gentle ground |
   | Land cover | 20% | Forest; built-up land scores low |
   | Rock type (GSI map) | 20% | Fractured or porous rock such as carbonate and quartzite; shale and phyllite score low |
   | Distance to a fault or lineament | 20% | Within 100 m |
   | Soil, top 30 cm (SoilGrids) | 15% | Sandy and sandy-loam soil; clay scores low; stony soil gets a small bonus |

   Without SoilGrids files the soil factor is left out and the other weights are scaled up.

4. **Recharge area needed.** This comes from the monsoon flow, using the area-flow relation of 35 delineated springsheds (Rathi 2021): area ≈ 0.20 × flow^0.68 ha. With no flow reading, the typical 1.5 / 3 / 8 ha of hill springsheds is used. Each zone is grown to about the middle value (at least 1 ha).
5. **Link to the spring.** A cell can only feed the spring if water has a way to get there:

   | Link | Strength | Which cells |
   |---|---|---|
   | Spring slope | 1.0 | Inside the surface catchment (plus a 60 m ridge margin), not below the spring |
   | GSI fault | 0.9 | Within 250 m of a mapped fault that passes within 200 m of the spring |
   | Rock tilt (up-dip) | 0.9 | Up-dip of the spring (±40°) in the same rock unit, when the dip is entered |
   | DEM lineament (crack) | 0.7 | Within 250 m of a lineament that passes within 200 m of the spring |

   When the dip is entered, slope cells that are not up-dip count a little less (×0.6).
6. **Top three zones.** Each cell gets: recharge potential × link strength × closeness (falls off over about 4 km). The tool then:
   - starts a zone at the best cell and grows it through neighbouring cells with the same link, best first, up to the size needed;
   - for zones linked by a fault, crack or tilt, checks the ground in between: if it dips more than 30 m below the spring, a stream there may catch the water first, so the zone is ranked lower; more than 100 m rules it out;
   - keeps a 90 m gap and repeats, then keeps the best three as **R1, R2, R3**.

   Only ground with a recharge potential of 0.5 or more is used (0.35 with a warning if there is none).

   There is no rule that a zone must be near the spring or far from it. For a spring with good ground on its own slope, all three can be on the slope. For a spring with poor ground above it but a fault to a better slope, R1 can be in the next valley. Each zone card says what links it, how far and how high it is, its land cover, soil and rock, and why it ranked where it did.

   Zones beyond the surface catchment are hypotheses, not findings. The tab lists field checks: walk the fault or crack line for seeps, track water temperature and EC monthly, note how slowly the spring rises after rain, and (with budget) an oxygen-18 test of the recharge height.

The map shows the **surface catchment** (dashed blue: where rain runs off towards the spring) and the **recharge zones** R1-R3 (green, darkest is best: where rain soaks in and feeds it) as separate layers, because the two are not the same area.

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
| Inside a recharge zone on the spring slope | 30%, 60%, 100% |
| Inside a recharge zone linked by a fault or rock tilt | 10%, 30%, 60% |
| Inside a recharge zone linked by a crack (lineament) | 5%, 20%, 50% |
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

# Running Module A on your own computer (Windows)

Module A runs fully on your computer, with no paid service and no account.

It needs internet in two cases:

- **The first run:** Module A downloads the maps it needs and stores them.
- **A spring in a new area:** it downloads the map tiles for that area.

After that it also works offline. Only building growth is still read online; without internet it is left out of the score.

The steps below use Rajat's folders. Change the paths if yours differ.

## 1. One-time setup (about 20 minutes)

1. **Install Python.**
   - Download Python 3.12 from python.org and run the installer.
   - On the first screen, tick **"Add python.exe to PATH"**.
2. **Get the code.**
   - On the GitHub page of this repository, click **Code → Download ZIP**.
   - Unzip it to `C:\Users\rajat\Downloads\DOCC\Tool`.
   - If you use git, clone the repository there instead.
3. **Open Command Prompt in that folder.** Press the Windows key, type `cmd` and press Enter. Then run:

   ```
   cd C:\Users\rajat\Downloads\DOCC\Tool\rdi-watsan-springshed-decision-support-main
   ```

4. **Install the packages.** Run these three commands:

   ```
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   ```

   After `activate`, the prompt starts with `(.venv)`. Run the `activate` line again each time you open a new Command Prompt.
5. **Tell Module A where your folders are.** Run these two commands once per Command Prompt window:

   ```
   set SPRING_LAYER_CACHE=C:\Users\rajat\Downloads\DOCC\MapCache
   set SPRING_LOCAL_LAYERS=C:\Users\rajat\Downloads\DOCC\Data
   ```

   - `MapCache` is a new, empty folder for the maps Module A downloads. For springs anywhere in Uttarakhand and Himachal it reaches about 1.3 GB.
   - `DOCC\Data` must hold the `IMD`, `SoilGrids` and `Bhoonidhi` folders you already downloaded.
6. **Check the setup:**

   ```
   python scripts\module_a_vulnerability.py --check-setup
   ```

   Every line should say `ok`. A line saying `MISSING` comes with what to do about it.

## 2. Score one spring

```
python scripts\module_a_vulnerability.py --lat 29.91903 --lon 78.55647 --elevation 1481 --name "Nauli Dhara" --flow-vs-past a_bit_less --lean-flow-lpm 2.5 --households 35
```

- **Required:** `--lat`, `--lon` and `--elevation`.
- **Optional:** every other field answer. Run `python scripts\module_a_vulnerability.py --help` to see the list and the allowed answers.
- **Timing:** the very first run downloads maps and takes a few minutes. After that, a run takes about 10 seconds to start and a few seconds per spring.

The score prints on screen. The one-page report, plus a JSON file for the future web page, goes to `data\03_outputs\module_a\reports\`.

## 3. Score many springs

1. Open `config\module_a_input_template.csv` in Excel. Fill in one spring per row; blank cells are fine.
2. Save it as CSV, for example as `my_springs.csv` in the same folder.
3. Run:

   ```
   python scripts\module_a_vulnerability.py --batch config\my_springs.csv
   ```

4. Read the scores in `data\03_outputs\module_a\batch_scores.csv`. Each spring also gets its own report.

## 4. After the field visit: check Module A once

1. Fill `config\module_a_validation_template.csv` with each visited spring. Give its location and whether people say it is declining or steady.
2. Run:

   ```
   python scripts\module_a_checks.py --validate config\my_validation.csv
   ```

3. Read the result in `data\03_outputs\module_a\`. Run it once: every run is logged, and a second look at the same springs shows up.

## If something goes wrong

- **`python` is not recognised:** reinstall Python and tick "Add python.exe to PATH".
- **`pip install` fails on rasterio:** run `python -m pip install --upgrade pip`, then install again.
- **The IMD files do not open:** run `pip install --force-reinstall rasterio`.
- **It is slow the first time:** this is expected while maps download. Later runs reuse `MapCache`.
- **No internet:** springs in areas already in `MapCache` still score. Building growth is left out, and the report shows this as lower coverage. A spring in a new area needs internet once, to download its map tiles.

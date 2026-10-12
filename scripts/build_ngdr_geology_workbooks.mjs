import { execFile } from "node:child_process";
import { promisify } from "node:util";
import fs from "node:fs/promises";
import path from "node:path";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const execFileAsync = promisify(execFile);
const appRoot = path.resolve(import.meta.dirname, "..");
const runtimePython = "C:/Users/abhis/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe";
const stagedDir = path.join(appRoot, "data", "01_staged", "ngdr_geology");

await execFileAsync(runtimePython, [path.join(appRoot, "scripts", "stage_ngdr_geology.py")], { cwd: appRoot, maxBuffer: 2 * 1024 * 1024 });
const metadata = JSON.parse(await fs.readFile(path.join(stagedDir, "metadata", "ngdr_uttarakhand_geology_v1_metadata.json"), "utf8"));

const selectedSource = process.env.GEOLOGY_SOURCE || "";
const selectedSources = selectedSource ? metadata.sources.filter((source) => source.key === selectedSource) : metadata.sources;
if (selectedSources.length === 0) throw new Error(`No NGDR source matches GEOLOGY_SOURCE=${selectedSource}`);

for (const source of selectedSources) {
  const csvText = await fs.readFile(path.join(appRoot, source.staged_csv), "utf8");
  const workbook = await Workbook.fromCSV(csvText, { sheetName: "Features" });
  const features = workbook.worksheets.getItem("Features");
  const used = features.getUsedRange();
  features.showGridLines = false;
  features.freezePanes.freezeRows(1);
  used.format.font = { name: "Arial", size: 10 };
  features.getRangeByIndexes(0, 0, 1, used.columnCount).format = {
    fill: "#1F4E78", font: { name: "Arial", bold: true, color: "#FFFFFF", size: 10 },
    horizontalAlignment: "center", verticalAlignment: "center", wrapText: true,
  };
  features.getRangeByIndexes(0, 0, 1, used.columnCount).format.rowHeight = 32;
  for (let column = 0; column < used.columnCount; column += 1) {
    const width = column === 6 || column === 7 ? 60 : column < 6 ? 25 : 18;
    features.getRangeByIndexes(0, column, used.rowCount, 1).format.columnWidth = width;
  }

  const provenance = workbook.worksheets.add("Provenance");
  const noteBySource = {
    "SRC-013": "Feature attributes and map geometry are staged separately. Fault proximity is not evidence of a hydraulic connection to a spring.",
    "SRC-014": "Feature attributes and map geometry are staged separately. Any spring-polygon assignment is a map inference and requires field confirmation, particularly near contacts.",
    "SRC-015": "Feature attributes and map geometry are staged separately. Fold proximity is not evidence of a hydraulic connection to a spring.",
  };
  const note = noteBySource[source.source_id];
  const rows = [
    [`${source.dataset} feature staging extract`],
    ["Field", "Value"],
    ["Source ID", source.source_id],
    ["Source GeoJSON", source.raw_path],
    ["Features", source.feature_count],
    ["Geometry types", source.geometry_types.join(", ")],
    ["Coordinate reference system", JSON.stringify(source.crs)],
    ["Staging rule", "Source properties are represented as text. Geometry is retained unchanged only in the immutable raw GeoJSON, referenced by feature locator."],
    ["Use limitation", note],
    ["Not done", "No spatial join to springs, geometry edit, simplification, coordinate correction, deduplication, or geological interpretation."],
  ];
  provenance.getRangeByIndexes(0, 0, rows.length, 2).values = rows;
  provenance.mergeCells("A1:B1");
  provenance.getRange("A1").format = { fill: "#1F4E78", font: { name: "Arial", bold: true, color: "#FFFFFF", size: 14 } };
  provenance.getRange("A2:B2").format = { fill: "#D9EAF7", font: { name: "Arial", bold: true, size: 10 } };
  provenance.getRange(`A1:B${rows.length}`).format = { font: { name: "Arial", size: 10 }, wrapText: true, verticalAlignment: "top" };
  provenance.getRange("A:A").format.columnWidth = 27;
  provenance.getRange("B:B").format.columnWidth = 100;
  provenance.getRange(`A1:B${rows.length}`).format.autofitRows();
  provenance.showGridLines = false;
  provenance.freezePanes.freezeRows(2);

  workbook.recalculate();
  const outputPath = path.join(path.dirname(path.join(appRoot, source.staged_csv)), "..", "xlsx", path.basename(source.staged_csv, ".csv") + ".xlsx");
  await fs.mkdir(path.dirname(outputPath), { recursive: true });
  const output = await SpreadsheetFile.exportXlsx(workbook);
  await output.save(outputPath);
  console.log(JSON.stringify({ source: source.dataset, outputPath }));
}

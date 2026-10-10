import { execFile } from "node:child_process";
import { promisify } from "node:util";
import fs from "node:fs/promises";
import path from "node:path";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const execFileAsync = promisify(execFile);
const appRoot = path.resolve(import.meta.dirname, "..");
const runtimePython = "C:/Users/abhis/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe";
const extractor = path.join(appRoot, "scripts", "stage_watsan_and_spring_atlas.py");
const stagedDir = path.join(appRoot, "data", "01_staged");
const commonDir = path.join(stagedDir, "common");

await execFileAsync(runtimePython, [extractor], { cwd: appRoot, maxBuffer: 2 * 1024 * 1024 });
const metadata = JSON.parse(await fs.readFile(path.join(commonDir, "metadata", "spring_records_common_v1_metadata.json"), "utf8"));

const workbookPlans = [
  {
    source: "WATSAN",
    count: metadata.watsan_common_records,
    csv: path.join(stagedDir, "watsan", "csv", "watsan_spring_records_common_v1.csv"),
    output: path.join(stagedDir, "watsan", "xlsx", "watsan_spring_records_common_v1.xlsx"),
    note: "SRC-001 | Discharge_Spring_Data.xlsx | All_Parameter sheet. Not validated ground truth; retain Verify status until the dataset audit is complete.",
  },
  {
    source: "Spring Atlas",
    count: metadata.spring_atlas_common_records,
    csv: path.join(stagedDir, "spring_atlas", "csv", "spring_atlas_inventory_common_v1.csv"),
    output: path.join(stagedDir, "spring_atlas", "xlsx", "spring_atlas_inventory_common_v1.xlsx"),
    note: "SRC-008 | Spring ATLAS of Uttarakhand.pdf | Annexure inventory pages 57-82. PDF extraction; check records against their cited page.",
  },
  {
    source: "Himmotthan",
    count: metadata.himmotthan_common_records,
    csv: path.join(stagedDir, "himmotthan", "csv", "himmotthan_spring_records_common_v1.csv"),
    output: path.join(stagedDir, "himmotthan", "xlsx", "himmotthan_spring_records_common_v1.xlsx"),
    note: "SRC-007 | Himmotthan Geo-Locator KML | Springs.xlsx layer. Confirm provenance, measurement conditions, and field relevance before analysis.",
  },
  {
    source: "Combined master",
    count: metadata.combined_common_records,
    csv: path.join(commonDir, "csv", "spring_records_common_v1.csv"),
    output: path.join(commonDir, "xlsx", "spring_records_common_v1.xlsx"),
    note: "Common source-traceable master. No cross-source deduplication, coordinate correction, imputation, or inferred matching has been applied.",
    includeMapping: true,
  },
];

const mappingRows = [
  ["Common field", "WATSAN source", "Spring Atlas source", "Himmotthan source", "Rule"],
  ["source_area_name", "Area_name", "", "", "Retained as an area label; never assumed to be a spring name."],
  ["spring_name", "", "Spring Name", "Placemark name", "Blank where a source does not explicitly provide a spring name."],
  ["latitude_source_value", "Latitude", "Latitude", "Point coordinate", "Source text retained."],
  ["longitude_source_value", "Longitude", "Longitude", "Point coordinate", "Source text retained."],
  ["elevation_m_source_value", "elevation", "Altitude (m)", "Altitude", "Source text retained."],
  ["land_use_source_value", "lulc", "", "Land_use", "Blank where source does not supply it."],
  ["slope_aspect_source_value", "aspect", "", "Slope_Aspect", "Blank where source does not supply it."],
  ["slope_degrees_source_value", "slope_deg", "", "Slope", "Blank where source does not supply it."],
  ["lithology_source_value", "", "", "Lithology", "Blank where source does not supply it."],
  ["spring_type_source_value", "spring_typology", "", "Spring_Type", "Blank where source does not supply it."],
  ["discharge_lpm_source_value", "discharge_lpm", "", "Discharge (LPM)", "Source text retained; values may be ranges or other non-numeric entries."],
];

async function buildWorkbook(plan) {
  const csvText = await fs.readFile(plan.csv, "utf8");
  const workbook = await Workbook.fromCSV(csvText, { sheetName: "Spring records" });
  const records = workbook.worksheets.getItem("Spring records");
  records.showGridLines = false;
  records.freezePanes.freezeRows(1);
  records.getRange("A1:AE1").format = { fill: "#1F4E78", font: { name: "Arial", bold: true, color: "#FFFFFF", size: 10 }, horizontalAlignment: "center", verticalAlignment: "center", wrapText: true };
  records.getRange("A1:AE1").format.rowHeight = 32;
  records.getRange(`A1:AE${plan.count + 1}`).format.font = { name: "Arial", size: 10 };
  records.getRange("A:A").format.columnWidth = 16;
  records.getRange("B:D").format.columnWidth = 26;
  records.getRange("E:J").format.columnWidth = 20;
  records.getRange("K:AB").format.columnWidth = 18;
  records.getRange("AC:AE").format.columnWidth = 42;

  const provenance = workbook.worksheets.add("Provenance");
  const values = [
    [`${plan.source} common spring-record staging extract`],
    ["Field", "Value"],
    ["Records", plan.count],
    ["Coordinate reference system", "WGS 84 longitude/latitude as supplied by the source or standard KML/PDF convention."],
    ["Source and limitation", plan.note],
    ["Format rule", "All source values remain text so the source representation is not silently changed."],
    ["Not done", "No deduplication, imputation, coordinate correction, or interpretation of source fields."],
  ];
  provenance.getRangeByIndexes(0, 0, values.length, 2).values = values;
  provenance.getRange("A1:B1").merge();
  provenance.getRange("A1").format = { fill: "#1F4E78", font: { name: "Arial", bold: true, color: "#FFFFFF", size: 14 } };
  provenance.getRange("A2:B2").format = { fill: "#D9EAF7", font: { name: "Arial", bold: true, size: 10 } };
  provenance.getRange("A1:B7").format = { font: { name: "Arial", size: 10 }, wrapText: true, verticalAlignment: "top" };
  provenance.getRange("A:A").format.columnWidth = 27;
  provenance.getRange("B:B").format.columnWidth = 100;
  provenance.getRange("A1:B7").format.autofitRows();
  provenance.showGridLines = false;
  provenance.freezePanes.freezeRows(2);

  if (plan.includeMapping) {
    const mapping = workbook.worksheets.add("Field mapping");
    mapping.getRangeByIndexes(0, 0, mappingRows.length, 5).values = mappingRows;
    mapping.getRange("A1:E1").format = { fill: "#1F4E78", font: { name: "Arial", bold: true, color: "#FFFFFF", size: 10 }, horizontalAlignment: "center", wrapText: true };
    mapping.getRange(`A1:E${mappingRows.length}`).format = { font: { name: "Arial", size: 10 }, wrapText: true, verticalAlignment: "top" };
    mapping.getRange("A:E").format.autofitColumns();
    mapping.getRange("A:A").format.columnWidth = 31;
    mapping.getRange("B:D").format.columnWidth = 28;
    mapping.getRange("E:E").format.columnWidth = 55;
    mapping.getRange(`A1:E${mappingRows.length}`).format.autofitRows();
    mapping.showGridLines = false;
    mapping.freezePanes.freezeRows(1);
  }
  workbook.recalculate();
  const output = await SpreadsheetFile.exportXlsx(workbook);
  await fs.mkdir(path.dirname(plan.output), { recursive: true });
  await output.save(plan.output);
}

const selectedSource = process.env.STAGED_SOURCE || "";
const selectedPlans = selectedSource ? workbookPlans.filter((plan) => plan.source === selectedSource) : workbookPlans;
if (selectedPlans.length === 0) throw new Error(`No workbook plan matches STAGED_SOURCE=${selectedSource}`);
for (const plan of selectedPlans) await buildWorkbook(plan);
console.log(JSON.stringify({ ...metadata, workbooks: selectedPlans.map(({ source, output }) => ({ source, output })) }, null, 2));

import fs from "node:fs/promises";
import path from "node:path";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const workspaceRoot = path.resolve(import.meta.dirname, "..", "..");
const sourcePath = path.join(workspaceRoot, "Resources", "Himmotthan Geo-Locator (1).kml");
const stagedDir = path.join(workspaceRoot, "Application", "data", "01_staged");
const csvPath = path.join(stagedDir, "himmotthan_springs_extract_v1.csv");
const xlsxPath = path.join(stagedDir, "himmotthan_springs_extract_v1.xlsx");

const columns = [
  "record_id",
  "source_kml_feature_index",
  "source_kml_file",
  "spring_name",
  "district",
  "block",
  "village_name",
  "latitude",
  "longitude",
  "altitude_m",
  "land_use",
  "slope_aspect",
  "slope_degrees",
  "lithology",
  "spring_type",
  "tds_source_value",
  "ph_source_value",
  "discharge_lpm_source_value",
  "geometry_wkt",
];

const xmlDecode = (value = "") => value
  .replace(/<!\[CDATA\[([\s\S]*?)\]\]>/g, "$1")
  .replace(/&amp;/g, "&")
  .replace(/&lt;/g, "<")
  .replace(/&gt;/g, ">")
  .replace(/&quot;/g, '"')
  .replace(/&#39;/g, "'")
  .trim();

const field = (placemark, name) => {
  const escaped = name.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const match = placemark.match(new RegExp(`<Data\\s+name="${escaped}"[^>]*>[\\s\\S]*?<value>([\\s\\S]*?)<\\/value>[\\s\\S]*?<\\/Data>`, "i"));
  return match ? xmlDecode(match[1]) : "";
};

const csvCell = (value) => `"${String(value ?? "").replace(/"/g, '""')}"`;

const rawKml = await fs.readFile(sourcePath, "utf8");
const placemarks = [...rawKml.matchAll(/<Placemark>([\s\S]*?)<\/Placemark>/g)].map((match) => match[1]);
const sourceFile = path.basename(sourcePath);
const rows = [];

placemarks.forEach((placemark, index) => {
  // Village_Name uniquely identifies the supplied Springs.xlsx KML layer.
  if (!/<Data\s+name="Village_Name"/i.test(placemark)) return;
  const point = placemark.match(/<Point>[\s\S]*?<coordinates>\s*([^<\s]+)[\s\S]*?<\/coordinates>[\s\S]*?<\/Point>/i);
  if (!point) return;
  const [longitude = "", latitude = ""] = point[1].split(",");
  const name = placemark.match(/<name>([\s\S]*?)<\/name>/i);
  const row = {
    record_id: `HIM-SPR-${String(rows.length + 1).padStart(4, "0")}`,
    source_kml_feature_index: index + 1,
    source_kml_file: sourceFile,
    spring_name: name ? xmlDecode(name[1]) : "",
    district: field(placemark, "District"),
    block: field(placemark, "Block"),
    village_name: field(placemark, "Village_Name"),
    latitude: latitude.trim(),
    longitude: longitude.trim(),
    altitude_m: field(placemark, "Altitude"),
    land_use: field(placemark, "Land_use"),
    slope_aspect: field(placemark, "Slope_Aspect"),
    slope_degrees: field(placemark, "Slope"),
    lithology: field(placemark, "Lithology"),
    spring_type: field(placemark, "Spring_Type"),
    tds_source_value: field(placemark, "TDS"),
    ph_source_value: field(placemark, "pH"),
    discharge_lpm_source_value: field(placemark, "Discharge (LPM)"),
    geometry_wkt: `POINT (${longitude.trim()} ${latitude.trim()})`,
  };
  rows.push(row);
});

if (rows.length === 0) throw new Error("No spring records were extracted from the KML.");

await fs.mkdir(stagedDir, { recursive: true });
const csvText = [columns.join(","), ...rows.map((row) => columns.map((column) => csvCell(row[column])).join(","))].join("\r\n") + "\r\n";
await fs.writeFile(csvPath, csvText, "utf8");

const workbook = Workbook.create();
const dataSheet = workbook.worksheets.add("Springs");
dataSheet.getRangeByIndexes(0, 0, rows.length + 1, columns.length).values = [
  columns,
  ...rows.map((row) => columns.map((column) => row[column])),
];
dataSheet.getRange(`A1:S1`).format = {
  fill: "#1F4E78",
  font: { bold: true, color: "#FFFFFF" },
  horizontalAlignment: "center",
  verticalAlignment: "center",
  wrapText: true,
};
dataSheet.getRange(`A1:S${rows.length + 1}`).format.autofitColumns();
dataSheet.getRange(`A1:S${rows.length + 1}`).format.autofitRows();
dataSheet.freezePanes.freezeRows(1);

const provenance = workbook.worksheets.add("Provenance");
const provenanceRows = [
  ["Himmotthan Springs Extract — provenance"],
  ["Field", "Value"],
  ["Source file", `Resources/${sourceFile}`],
  ["Source layer", "Springs.xlsx"],
  ["Extraction date", new Date().toISOString().slice(0, 10)],
  ["Records extracted", rows.length],
  ["Coordinate reference system", "WGS 84 longitude/latitude (KML standard)"],
  ["Extraction rule", "KML Placemarks with source attribute Village_Name; Point geometry required"],
  ["Transformation", "Format conversion only. Source attribute values are retained as text; no cleaning, imputation, deduplication, or validation applied."],
  ["Important limitation", "This is a staged extract, not field-verified ground truth. Confirm provenance, dates, measurement conditions, and site relevance before analysis."],
];
provenance.getRangeByIndexes(0, 0, provenanceRows.length, 2).values = provenanceRows;
provenance.getRange("A1:B1").merge();
provenance.getRange("A1").format = { fill: "#1F4E78", font: { bold: true, color: "#FFFFFF", size: 14 } };
provenance.getRange("A2:B2").format = { fill: "#D9EAF7", font: { bold: true } };
provenance.getRange("A1:B10").format.wrapText = true;
provenance.getRange("A1:B10").format.autofitColumns();
provenance.getRange("A1:B10").format.autofitRows();
provenance.getRange("A:A").format.columnWidth = 28;
provenance.getRange("B:B").format.columnWidth = 95;
provenance.freezePanes.freezeRows(2);

workbook.recalculate();
const xlsx = await SpreadsheetFile.exportXlsx(workbook);
await xlsx.save(xlsxPath);

console.log(JSON.stringify({ csvPath, xlsxPath, extractedRecords: rows.length, columns }, null, 2));

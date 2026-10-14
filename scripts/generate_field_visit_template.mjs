import fs from 'node:fs';
import { createRequire } from 'node:module';
const require = createRequire(import.meta.url);
const docx = require('docx');
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  WidthType, AlignmentType, HeadingLevel, PageBreak, BorderStyle,
  ShadingType, VerticalAlign
} = docx;

const OUT = 'Application/field/forms/WATSAN_Field_Visit_Data_Collection_Template_v0.1.docx';
const BLUE = '17365D';
const PALE = 'DCE6F1';
const GREY = 'F3F5F7';
const page = { top: 720, right: 720, bottom: 720, left: 720 };
const border = { style: BorderStyle.SINGLE, size: 4, color: 'AAB7C4' };

function p(text = '', opts = {}) {
  return new Paragraph({
    text,
    spacing: { after: opts.after ?? 90, before: opts.before ?? 0, line: opts.line ?? 250 },
    alignment: opts.align,
    heading: opts.heading,
    border: opts.border,
    children: opts.children,
  });
}
function run(text, opts = {}) { return new TextRun({ text, bold: opts.bold, italics: opts.italics, color: opts.color, size: opts.size }); }
function heading(text, level = HeadingLevel.HEADING_1) { return p(text, { heading: level, before: 100, after: 120 }); }
function note(text) { return p('', { after: 130, children: [run(text, { italics: true, color: '51606F', size: 18 })] }); }
function cell(text, opts = {}) {
  return new TableCell({
    width: opts.width ? { size: opts.width, type: WidthType.DXA } : undefined,
    verticalAlign: VerticalAlign.CENTER,
    shading: opts.header ? { type: ShadingType.CLEAR, color: opts.color || PALE } : undefined,
    borders: { top: border, bottom: border, left: border, right: border },
    margins: { top: 70, bottom: 70, left: 85, right: 85 },
    children: [p('', { after: 0, children: [run(text, { bold: opts.header, size: opts.size || 18 })] })]
  });
}
function table(headers, rows, widths) {
  return new Table({
    width: { size: 10000, type: WidthType.DXA },
    columnWidths: widths,
    rows: [
      new TableRow({ tableHeader: true, children: headers.map((x, i) => cell(x, { header: true, width: widths[i] })) }),
      ...rows.map(row => new TableRow({ children: row.map((x, i) => cell(x, { width: widths[i] })) }))
    ]
  });
}
function blankRows(n, cols, label = '') { return Array.from({ length: n }, (_, i) => Array.from({ length: cols }, (_, j) => (j === 0 && label ? `${label} ${i + 1}` : ''))); }
function breakPage() { return new Paragraph({ children: [new PageBreak()] }); }

const children = [
  p('', { align: AlignmentType.CENTER, after: 80, children: [run('SRHU / HIHT RDI — WATSAN', { bold: true, color: BLUE, size: 26 })] }),
  p('', { align: AlignmentType.CENTER, after: 90, children: [run('Field Visit Data Collection Template', { bold: true, size: 40, color: BLUE })] }),
  p('', { align: AlignmentType.CENTER, after: 240, children: [run('Initial draft for WATSAN team review | Project 1: spring vulnerability, springshed recharge and Direct Injection (DI)', { size: 20 })] }),
  table(['Purpose', 'How this template will be used'], [[
    'Create one shared, practical record of what is observed, measured, explained and recalled at each spring, springshed and DI site.',
    'Complete one Site Record per spring / DI location. Add a Community Conversation record where possible. Keep original photos and device exports unchanged.'
  ]], [5000, 5000]),
  p('Core principles', { heading: HeadingLevel.HEADING_2 }),
  p('[ ] Ask before recording names, photographs or quotations. Participation is voluntary; do not promise an intervention or benefit.\n[ ] Record the source of every statement: Observed / Measurement / Community recall / Staff explanation / Project inference.\n[ ] Do not call recalled changes “measured impact.”\n[ ] If a site-specific answer is unknown, write “Not available” — do not guess.\n[ ] Treat candidate recharge boundaries and DI estimates as provisional until verified through hydrogeology, field checks and monitoring.'),
  p('WATSAN review request', { heading: HeadingLevel.HEADING_2 }),
  table(['Please confirm before field use', 'Decision / edits from WATSAN'], [
    ['Priority indicators and local terms', ''],
    ['Sites, people to speak with and safe access arrangements', ''],
    ['Available equipment and water-test protocol', ''],
    ['Consent, photo and data-sharing expectations', ''],
    ['Which questions should be removed / added?', ''],
  ], [4400, 5600]),
  p('Reviewed by: ____________________  Role: ____________________  Date: ____________________  Version approved for field use: ____________________', { before: 160 }),
  breakPage(),

  heading('1. Visit cover sheet'),
  note('Complete once per day / village. Use the site records later in this field book for each spring or DI location.'),
  table(['Field', 'Record'], [
    ['Visit ID', ''], ['Date | start–end time', ''], ['Village / Gram Panchayat | Block | District', ''], ['Site(s) visited', ''], ['Team members / WATSAN guide', ''], ['Weather; rainfall in last 24–72 hours; any heavy rain?', ''], ['Access / safety constraints', ''], ['Equipment carried and working (GPS / phone / buckets / stopwatch / tape / compass / pH etc.)', ''], ['Original photo / audio / GPS file folder or IDs', ''], ['Who agreed to be photographed or quoted? Any restrictions?', ''],
  ], [3700, 6300]),
  heading('Daily debrief — complete before leaving the area', HeadingLevel.HEADING_2),
  table(['Prompt', 'Notes'], [
    ['What did we learn about water, the intervention and daily life?', ''],
    ['What surprised us or conflicts with an earlier assumption?', ''],
    ['Critical missing data / follow-up owner and due date', ''],
    ['Potential story, quote or photo (only with permission)', ''],
  ], [3700, 6300]),
  breakPage(),

  heading('2. Spring site record'),
  note('One form per spring. For any observation, tick or write its evidence type: Observed / Measurement / Community recall / Staff explanation / Project inference.'),
  table(['Field', 'Record'], [
    ['Site ID | local spring name', ''], ['Location (GPS latitude, longitude, elevation; device / accuracy)', ''], ['Date / time; observer(s)', ''], ['Spring type / outlet description (seep, pipe, tank, other)', ''], ['Water use today (drinking, domestic, livestock, irrigation, other)', ''], ['Photographs: close outlet, intake/tank, upstream view, wider landscape (file IDs)', ''], ['Weather and recent rainfall; could it distort discharge?', ''], ['Evidence type(s)', ''],
  ], [3700, 6300]),
  p('Discharge measurement — minimum three bucket-and-stopwatch readings', { heading: HeadingLevel.HEADING_2 }),
  table(['Reading', 'Bucket volume (L)', 'Elapsed time (s)', 'Flow (L/min)', 'Conditions / issues'], [
    ['1', '', '', '', ''], ['2', '', '', '', ''], ['3', '', '', '', ''], ['Average', '', '', '', 'Flow = bucket volume × 60 ÷ time']
  ], [1100, 1900, 1900, 1700, 3400]),
  table(['Current condition / risk check', 'Record (include evidence type)'], [
    ['Flow condition / clarity / odour / visible debris', ''], ['Intake, storage and pipe condition; leakage / overflow', ''], ['Nearby pollution risks (latrine, wastewater, grazing, waste, agrochemicals)', ''], ['Seasonal-flow recall: lowest-flow months; ever dry? last remembered year?', ''], ['Dependent households / users and alternative water sources', ''], ['Water testing available today: test, result, unit, kit / lab reference', ''],
  ], [4300, 5700]),
  breakPage(),

  heading('3. Springshed walk and basic geology record'),
  note('This is a first field check, not a final hydrogeological delineation. Record what is seen and who explained it. A surface micro-catchment is not automatically the hydrogeological recharge area.'),
  table(['Field', 'Record'], [
    ['Linked Spring Site ID', ''], ['Walk route / waypoint IDs / start–end time', ''], ['Slope and terrain above spring (gentle / moderate / steep; describe)', ''], ['Visible drainage lines, ridges, gullies or barriers', ''], ['Land cover / land use uphill (forest, agriculture, settlement, road, grazing etc.)', ''], ['Potential recharge features (permeable soil, fractures, ponds, trenches, vegetation)', ''], ['Potential threats uphill (construction, waste, sanitation, erosion, land disturbance)', ''], ['Rock / soil observed — only if confidently identified; photo / sample reference', ''], ['Fractures / bedding / rock tilt: direction and dip if measured; method / device', ''], ['Staff / community explanation of where water comes from and why', ''], ['Candidate recharge direction / area: [ ] staff delineation [ ] field inference [ ] unknown', ''], ['What must be verified before drawing or treating a recharge zone?', ''],
  ], [4300, 5700]),
  p('Quick sketch / map reference', { heading: HeadingLevel.HEADING_2 }),
  p('Draw the spring, route, ridge / drainage features, land use, known recharge works, likely water movement and uncertain areas. Attach a photo of the sketch or record the linked map file ID.', { after: 80 }),
  table(['Sketch / map file ID', 'Notes / interpretation clearly labelled'], [['', '']], [3000, 7000]),
  breakPage(),

  heading('4. Direct Injection (DI) site record'),
  note('Use for every DI / revived-handpump site. Do not infer impact from a single visit. Community accounts are valuable evidence of experience, but remain recall until supported by monitoring.'),
  table(['Field', 'Record'], [
    ['DI Site ID | linked Spring Site ID (if known)', ''], ['Location / date / observer(s)', ''], ['Installation year; implementer; known design / modification', ''], ['Handpump status today (working / not working / intermittent); user / caretaker', ''], ['Connected roof / catchment: building, measured or estimated area (m²), method', ''], ['Roof material / gutter and pipe condition', ''], ['First-flush device: present / working / last cleaned / unknown', ''], ['Filter: type / layers; condition; last cleaned or replaced; blockage / bypass', ''], ['Overflow / drainage: where does it go? Any backing up / leakage?', ''], ['Injection route / casing details if known; do not open or alter equipment', ''], ['Distance and elevation difference to spring, if known; method / source', ''], ['Handpump yield: 3 readings if measured, otherwise state source', ''], ['Water level: depth-to-water / datum / device / time; or Not available', ''], ['Water quality: test and result / date / lab or kit / Not available', ''], ['Photographs: roof, gutter, first flush, filter, handpump, overflow (file IDs)', ''],
  ], [4300, 5700]),
  p('Safety flags requiring WATSAN follow-up', { heading: HeadingLevel.HEADING_2 }),
  table(['Check', 'Status / action'], [
    ['[ ] First flush missing / not functioning', ''], ['[ ] Filter needs cleaning / replacement / maintenance record absent', ''], ['[ ] Clogging, overflow or contaminated inflow suspected', ''], ['[ ] Water quality concern or no recent test', ''], ['[ ] Physical hazard / unsafe access', ''], ['Responsible person and follow-up date', ''],
  ], [4300, 5700]),
  breakPage(),

  heading('5. Community conversation guide'),
  note('Suggested 15–25 minute conversation. Use it with individual users and, where appropriate, a water committee / women’s group. Start with what people want to discuss; do not treat this as a survey with a required answer to every question.'),
  p('Opening', { heading: HeadingLevel.HEADING_2 }),
  p('“We are learning from the community and WATSAN about this water source and any recharge work. We will record notes to improve our understanding. You may skip any question. This visit does not guarantee any new work or benefit. Is it alright to continue and take notes? Is it alright to take photographs or use a quote?”'),
  table(['Conversation details', 'Record'], [
    ['Site ID | date | facilitator / note-taker', ''], ['Conversation type: individual / group / committee; number of people', ''], ['Participation consent to notes: yes / no | photo: yes / no | quote: yes / no', ''], ['Participant description only if they wish (role / water use; avoid unnecessary personal data)', ''], ['Evidence label: Community recall / Staff explanation / Observation', ''],
  ], [4300, 5700]),
  table(['Open question', 'Key points — who said it / evidence label'], [
    ['1. What role does this source play in daily life? Who relies on it and for what?', ''],
    ['2. How does water availability and quality change across seasons? What happens in the hardest period?', ''],
    ['3. Before the intervention / changes, what problems did people face? (time, distance, cost, health concerns, work, school, farming, livestock, conflict)', ''],
    ['4. What has changed, if anything, since the intervention? What makes you think so?', ''],
    ['5. Who has benefited most / least? Are there differences for women, older people, children, lower-income households or distant hamlets?', ''],
    ['6. What time, money or effort is still required to secure water?', ''],
    ['7. Who maintains the spring / DI system? What makes maintenance difficult?', ''],
    ['8. What would community members want checked, repaired or improved first?', ''],
    ['9. Is there a safe follow-up contact / committee? Any restrictions on sharing this story?', ''],
  ], [4200, 5800]),
  breakPage(),

  heading('6. Rapid vulnerability and response screen'),
  note('Initial shared field judgement only — not a final score. Mark 1 = lower concern, 2 = moderate / uncertain, 3 = higher concern, then explain the evidence. Review indicator definitions and weights with WATSAN before use in the tool.'),
  table(['Group', 'Draft prompt', '1 / 2 / 3', 'Evidence / explanation'], [
    ['Stressor', 'Pressure around source / uphill: land disturbance, pollution, erosion, demand', '', ''],
    ['State', 'Current source condition: flow condition, water quality concern, system condition', '', ''],
    ['Impact', 'Reported reliability / access effect: seasonal scarcity, time and burden on users', '', ''],
    ['Response', 'Protection and maintenance: functioning committee, repair, monitoring, safeguards', '', ''],
    ['Overall', 'Main drivers (top three) and uncertainty', '', ''],
  ], [1500, 3400, 1200, 3900]),
  heading('7. Monitoring handover — baseline / follow-up'),
  table(['What to track', 'Minimum record'], [
    ['Rainfall', 'Date, gauge / source, amount, location'],
    ['Spring discharge', 'At least 3 bucket-and-stopwatch readings; date/time; rainfall conditions; average L/min'],
    ['Handpump / groundwater level', 'Depth to water, fixed measurement point / datum, device, date/time'],
    ['DI performance', 'First flush and filter condition, maintenance, overflow / clogging, roof connection status'],
    ['Water quality', 'Test parameter, result / unit, method / lab, sampling date'],
    ['Community experience', 'Short dated note on access, time burden, reliability and maintenance — clearly labelled recall'],
  ], [3200, 6800]),
  p('Recommended rhythm: record baseline now; then repeat at a WATSAN-agreed frequency across wet and lean seasons. A possible spring-flow response must not be attributed to DI without a defensible monitoring comparison.', { before: 130 }),
  breakPage(),

  heading('8. Evidence and file log'),
  note('Keep original files unchanged. Suggested folder: Application/data/00_raw/field/YYYY-MM-DD_<site>/. The spreadsheet / staged record should retain the source ID and this form’s visit and site IDs.'),
  table(['Item', 'ID / file name / storage path', 'What it shows / restrictions'], [
    ['GPS export', '', ''], ['Photos', '', ''], ['Audio / consent note', '', ''], ['Water-test sheet / laboratory report', '', ''], ['Sketch / paper form scan', '', ''], ['Staff document / prior monitoring record', '', ''], ['Other', '', ''],
  ], [2000, 4000, 4000]),
  heading('9. Post-visit team check'),
  table(['Check', 'Completed / notes'], [
    ['[ ] All spring / DI forms have IDs and dates', ''],
    ['[ ] Units and calculations checked; discharge readings retained, not averaged away', ''],
    ['[ ] Evidence types applied; recalled DI changes not labelled measured impact', ''],
    ['[ ] Photos / device exports copied unchanged into raw-data folder', ''],
    ['[ ] Any new observation added to the dated field-insights log with source and conditions', ''],
    ['[ ] Conflicts, safety concerns and unresolved questions logged for WATSAN', ''],
    ['[ ] Data needed for the tool staged with source / form / photo locators', ''],
  ], [6100, 3900]),
  p('', { align: AlignmentType.CENTER, before: 180, children: [run('Prepared by: Abhishek Ramasubramanian and Rajat Panda | Draft v0.1 | 12 October 2026', { size: 16, color: '51606F' })] })
];

const doc = new Document({
  sections: [{ properties: { page: { margin: page } }, children }],
  styles: { default: { document: { run: { font: 'Aptos', size: 20 } } } }
});
fs.mkdirSync('Application/field/forms', { recursive: true });
Packer.toBuffer(doc).then(buffer => fs.writeFileSync(OUT, buffer));

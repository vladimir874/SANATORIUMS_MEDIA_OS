/**
 * SAN Media Content System V2
 * Basic Apps Script: menu, update timestamp, missing Drive links check, weekly report.
 */

const CONFIG = {
  sheets: {
    production: '2_ТРЕКЕР_ПРОДАКШНА',
    plan: '0_ПЛАН',
    audit: '3_АУДИТ_САЙТА',
    dashboard: '0_DASHBOARD_V2'
  },
  productionColumns: {
    addedAt: 1,
    hotel: 2,
    operator: 3,
    type: 4,
    shootDate: 5,
    status: 6,
    drive: 7,
    comment: 8,
    siteUrl: 9,
    updatedAt: 10
  }
};

function onOpen() {
  SpreadsheetApp.getUi()
    .createMenu('SAN Media')
    .addItem('Обновить дату в активной строке', 'updateActiveRowTimestamp')
    .addItem('Проверить пустые Drive-ссылки', 'checkMissingDriveLinks')
    .addItem('Создать недельный отчет', 'createWeeklyReport')
    .addToUi();
}

function onEdit(e) {
  if (!e || !e.range) return;
  const sheet = e.range.getSheet();
  if (sheet.getName() !== CONFIG.sheets.production) return;
  const row = e.range.getRow();
  const col = e.range.getColumn();
  if (row < 2) return;
  const watched = [CONFIG.productionColumns.status, CONFIG.productionColumns.drive, CONFIG.productionColumns.comment];
  if (watched.includes(col)) sheet.getRange(row, CONFIG.productionColumns.updatedAt).setValue(new Date());
}

function updateActiveRowTimestamp() {
  const sheet = SpreadsheetApp.getActiveSheet();
  if (sheet.getName() !== CONFIG.sheets.production) {
    SpreadsheetApp.getUi().alert('Открой лист ' + CONFIG.sheets.production);
    return;
  }
  const row = sheet.getActiveCell().getRow();
  if (row < 2) return;
  sheet.getRange(row, CONFIG.productionColumns.updatedAt).setValue(new Date());
}

function checkMissingDriveLinks() {
  const ss = SpreadsheetApp.getActive();
  const sheet = ss.getSheetByName(CONFIG.sheets.production);
  const lastRow = sheet.getLastRow();
  if (lastRow < 2) {
    SpreadsheetApp.getUi().alert('Нет данных для проверки.');
    return;
  }
  const data = sheet.getRange(2, 1, lastRow - 1, CONFIG.productionColumns.updatedAt).getValues();
  let missing = [];
  data.forEach((row, index) => {
    const hotel = row[CONFIG.productionColumns.hotel - 1];
    const drive = row[CONFIG.productionColumns.drive - 1];
    if (hotel && !drive) missing.push(index + 2);
  });
  SpreadsheetApp.getUi().alert(missing.length ? 'Строки без Drive-ссылки: ' + missing.join(', ') : 'Пустых Drive-ссылок не найдено.');
}

function createWeeklyReport() {
  const ss = SpreadsheetApp.getActive();
  const prod = ss.getSheetByName(CONFIG.sheets.production);
  const reportName = 'REPORT_' + Utilities.formatDate(new Date(), ss.getSpreadsheetTimeZone(), 'yyyy-MM-dd');
  let report = ss.getSheetByName(reportName);
  if (!report) report = ss.insertSheet(reportName);
  report.clear();
  const values = prod.getDataRange().getValues();
  const headers = values[0];
  const rows = values.slice(1).filter(r => r[CONFIG.productionColumns.hotel - 1]);
  const statusCol = CONFIG.productionColumns.status - 1;
  const counts = {};
  rows.forEach(r => {
    const status = r[statusCol] || 'Без статуса';
    counts[status] = (counts[status] || 0) + 1;
  });
  report.getRange(1, 1).setValue('Недельный отчет SAN Media');
  report.getRange(2, 1).setValue('Дата создания');
  report.getRange(2, 2).setValue(new Date());
  report.getRange(4, 1, 1, 2).setValues([['Статус', 'Количество']]);
  const out = Object.entries(counts);
  if (out.length) report.getRange(5, 1, out.length, 2).setValues(out);
  report.getRange(4, 4, 1, headers.length).setValues([headers]);
  if (rows.length) report.getRange(5, 4, rows.length, headers.length).setValues(rows);
  report.autoResizeColumns(1, Math.min(headers.length + 3, 12));
}

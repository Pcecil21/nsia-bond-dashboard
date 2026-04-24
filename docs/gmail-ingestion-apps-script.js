/**
 * NSIA Inbox Router — Google Apps Script (no-filter mode + .eml unpack)
 *
 * Install in the nsia.inbox@gmail.com Google Apps Script project at
 * https://script.google.com. Do NOT install in your personal Gmail — this
 * script has full Gmail read access to whatever account owns it.
 *
 * What it does:
 *   1. Walks every unprocessed inbox thread.
 *   2. For each attachment:
 *      - If it's a regular file (pdf, docx, xlsx, png, ...): save to Drive
 *        prefixed with message date.
 *      - If it's a .eml (forwarded-as-attachment bundle): parse the MIME,
 *        pull out the nested attachments from the wrapped email, save those.
 *   3. Label the thread so we don't double-process next run.
 *
 * Schedule:
 *   Apps Script -> Triggers -> Add Trigger
 *   Function: saveIngestAttachments
 *   Event:    Time-driven, Minutes timer, Every 5 minutes
 *
 * Folder ID is the Unsorted subfolder under "NSIA Ingestion" on the
 * nsia.inbox@gmail.com Drive.
 */

const UNSORTED_FOLDER_ID = '1ILXbXhYAvuK9bKX17n_2-_NnmvlKM-YV';
const PROCESSED_LABEL = 'NSIA/Saved';
const BATCH_SIZE = 50;

// Skip auto-named email signature logos (image001.png, image002.jpg etc.) under 50KB.
// Real photo attachments come through with meaningful filenames and are untouched.
const SIG_IMAGE_RE = /^image\d+\.(png|jpe?g|gif|bmp)$/i;
const SIG_IMAGE_SIZE_MAX = 50 * 1024;  // 50 KB

function isSignatureImage(att) {
  const name = att.getName() || '';
  if (!SIG_IMAGE_RE.test(name)) return false;
  return att.getSize() <= SIG_IMAGE_SIZE_MAX;
}

function saveIngestAttachments() {
  const folder = DriveApp.getFolderById(UNSORTED_FOLDER_ID);
  const savedLabel = GmailApp.getUserLabelByName(PROCESSED_LABEL)
    || GmailApp.createLabel(PROCESSED_LABEL);

  const query = `in:inbox -label:${PROCESSED_LABEL} has:attachment`;
  const threads = GmailApp.search(query, 0, BATCH_SIZE);

  let savedCount = 0;
  for (const thread of threads) {
    for (const msg of thread.getMessages()) {
      const dateStr = Utilities.formatDate(msg.getDate(), 'America/Chicago', 'yyyy-MM-dd');

      for (const att of msg.getAttachments()) {
        if (att.getSize() === 0) continue;  // skip empty/inline signatures
        if (isSignatureImage(att)) continue;  // skip auto-named logo images
        try {
          if (isEmlAttachment(att)) {
            // Forwarded-as-attachment bundle — unpack it
            savedCount += unpackEmlToDrive(att, folder, dateStr);
          } else {
            // Regular attachment — save as-is
            folder.createFile(att.copyBlob()).setName(dateStr + '__' + att.getName());
            savedCount++;
          }
        } catch (err) {
          // One bad attachment shouldn't take down the whole run.
          // Save the raw blob so we don't lose it and log the error.
          Logger.log(`Failed on attachment '${att.getName()}': ${err}. Saving raw.`);
          try {
            folder.createFile(att.copyBlob()).setName(dateStr + '__ERRORED__' + att.getName());
          } catch (_) {}
        }
      }
    }
    thread.addLabel(savedLabel);
  }
  Logger.log(`Processed ${threads.length} thread(s), saved ${savedCount} attachment(s).`);
}

/**
 * Is this attachment a forwarded-email bundle?
 * Gmail's "Forward as attachment" produces attachments with Content-Type
 * message/rfc822, usually with a .eml extension.
 */
function isEmlAttachment(att) {
  const name = (att.getName() || '').toLowerCase();
  const type = (att.getContentType() || '').toLowerCase();
  return name.endsWith('.eml') || type.indexOf('message/rfc822') >= 0;
}

/**
 * Parse a .eml blob and save every nested attachment to Drive.
 * Returns the count of files saved.
 */
function unpackEmlToDrive(emlBlob, folder, dateStr) {
  const raw = emlBlob.getDataAsString();
  const attachments = extractMimeAttachments(raw);

  if (attachments.length === 0) {
    // No inner attachments — just save the raw .eml so we don't silently drop mail
    folder.createFile(emlBlob.copyBlob()).setName(dateStr + '__' + emlBlob.getName());
    return 1;
  }

  let count = 0;
  for (const a of attachments) {
    const fileName = dateStr + '__' + a.filename;
    const blob = Utilities.newBlob(a.bytes, a.contentType, fileName);
    folder.createFile(blob);
    count++;
  }
  return count;
}

/**
 * Walk a raw MIME message and return every part that has a filename
 * (i.e. every attachment). Recurses into nested multipart/* sections.
 */
function extractMimeAttachments(raw) {
  const results = [];
  const topBoundary = getMultipartBoundary(raw);
  if (!topBoundary) return results;

  walkMimeParts(raw, topBoundary, results);
  return results;
}

function getMultipartBoundary(headerBlock) {
  // Content-Type: multipart/mixed; boundary="----=_Part_xxx"
  const m = headerBlock.match(
    /Content-Type:\s*multipart\/[\w.-]+\s*;[\s\S]*?boundary\s*=\s*"?([^";\r\n]+)"?/i
  );
  return m ? m[1] : null;
}

function walkMimeParts(block, boundary, results) {
  const delimiter = '--' + boundary;
  const pieces = block.split(delimiter);
  // pieces[0] is the preamble before the first boundary; skip it.
  // The final piece starts with '--' (end boundary); skip it too.
  for (let i = 1; i < pieces.length; i++) {
    const p = pieces[i];
    if (p.indexOf('--') === 0) break;  // end boundary "--boundary--"
    processMimePart(p, results);
  }
}

function processMimePart(part, results) {
  // Split headers from body at the first blank line
  const sep = part.search(/\r?\n\r?\n/);
  if (sep < 0) return;
  const headers = part.substring(0, sep);
  const body = part.substring(sep).replace(/^\r?\n\r?\n/, '');

  const contentType = matchHeader(headers, 'Content-Type') || 'application/octet-stream';
  const cleanType = contentType.split(';')[0].trim().toLowerCase();

  // Recurse into nested multipart
  if (cleanType.indexOf('multipart/') === 0) {
    const sub = getMultipartBoundary(headers);
    if (sub) walkMimeParts(part, sub, results);
    return;
  }

  // Pull filename from Content-Disposition OR Content-Type
  let filename =
    matchFilename(headers, 'Content-Disposition') ||
    matchFilename(headers, 'Content-Type');

  // No filename = not an attachment (body text, alternative, etc.)
  if (!filename) return;

  const encoding = (matchHeader(headers, 'Content-Transfer-Encoding') || '')
    .trim()
    .toLowerCase();

  let bytes;
  if (encoding === 'base64') {
    // Strip whitespace/newlines before decoding
    const clean = body.replace(/\s+/g, '');
    bytes = Utilities.base64Decode(clean);
  } else if (encoding === 'quoted-printable') {
    bytes = decodeQuotedPrintable(body);
  } else {
    // 7bit, 8bit, binary, or unset
    bytes = Utilities.newBlob(body).getBytes();
  }

  results.push({ filename: filename, contentType: cleanType, bytes: bytes });
}

function matchHeader(headers, name) {
  const re = new RegExp('^' + name + ':\\s*([^\\r\\n]+(?:\\r?\\n[ \\t][^\\r\\n]+)*)', 'mi');
  const m = headers.match(re);
  // Unfold continuation lines (CRLF + whitespace = one logical line)
  return m ? m[1].replace(/\r?\n[ \t]+/g, ' ').trim() : null;
}

function matchFilename(headers, headerName) {
  const line = matchHeader(headers, headerName);
  if (!line) return null;
  // filename="foo.pdf" OR filename=foo.pdf
  const m1 = line.match(/filename\s*=\s*"([^"]+)"/i);
  if (m1) return m1[1];
  const m2 = line.match(/filename\s*=\s*([^\s;]+)/i);
  if (m2) return m2[1];
  // RFC 2231: filename*=UTF-8''encoded
  const m3 = line.match(/filename\*\s*=\s*(?:[\w-]+'[^']*')?([^;\s]+)/i);
  if (m3) {
    try { return decodeURIComponent(m3[1]); } catch (_) { return m3[1]; }
  }
  // Fallback: name="foo.pdf" on the Content-Type header
  const m4 = line.match(/name\s*=\s*"([^"]+)"/i);
  if (m4) return m4[1];
  return null;
}

function decodeQuotedPrintable(s) {
  const joined = s.replace(/=\r?\n/g, '');
  const decoded = joined.replace(/=([0-9A-F]{2})/gi, function (_, hex) {
    return String.fromCharCode(parseInt(hex, 16));
  });
  return Utilities.newBlob(decoded).getBytes();
}

/**
 * Manual test harness. Run from the Apps Script editor (Run menu) to see
 * what's waiting without saving anything.
 */
function testCountPending() {
  const query = `in:inbox -label:${PROCESSED_LABEL} has:attachment`;
  const threads = GmailApp.search(query, 0, BATCH_SIZE);
  Logger.log(`Pending threads with attachments: ${threads.length}`);
  for (const thread of threads.slice(0, 10)) {
    const msg = thread.getMessages()[0];
    const attNames = msg.getAttachments().map(function (a) {
      return a.getName() + (isEmlAttachment(a) ? ' [.eml bundle]' : '');
    }).join(', ');
    Logger.log(`  - ${msg.getFrom()}: ${thread.getFirstMessageSubject()} [${attNames}]`);
  }
}

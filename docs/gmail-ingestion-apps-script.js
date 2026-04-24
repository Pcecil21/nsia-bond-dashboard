/**
 * NSIA Inbox Router — Google Apps Script (no-filter mode)
 *
 * Install in the nsia.inbox@gmail.com Google Apps Script project at
 * https://script.google.com. Do NOT install in your personal Gmail — this
 * script has full Gmail read access to whatever account owns it.
 *
 * What it does:
 *   Walks every thread in the inbox that hasn't been processed yet, saves
 *   every attachment into NSIA Ingestion/Unsorted/ on Drive (prefixed with
 *   the message date), and tags the thread with "NSIA/Saved" so we don't
 *   double-save on the next run.
 *
 * The Python router (scripts/route_inbox.py) does the actual classification
 * locally — this script is intentionally dumb. If something shouldn't have
 * been saved (newsletter, vacation photo), delete it from the dashboard
 * Inbox page.
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

// How many inbox threads to scan per run. 50 is plenty at 5-min cadence.
const BATCH_SIZE = 50;

function saveIngestAttachments() {
  const folder = DriveApp.getFolderById(UNSORTED_FOLDER_ID);
  const savedLabel = GmailApp.getUserLabelByName(PROCESSED_LABEL)
    || GmailApp.createLabel(PROCESSED_LABEL);

  // Pull recent inbox threads that haven't been marked saved yet.
  // search() supports the same query syntax as Gmail's search box.
  const query = `in:inbox -label:${PROCESSED_LABEL} has:attachment`;
  const threads = GmailApp.search(query, 0, BATCH_SIZE);

  let savedCount = 0;
  for (const thread of threads) {
    for (const msg of thread.getMessages()) {
      for (const att of msg.getAttachments()) {
        if (att.getSize() === 0) continue;  // skip empty/inline signatures
        const dateStr = Utilities.formatDate(
          msg.getDate(), 'America/Chicago', 'yyyy-MM-dd'
        );
        const fileName = dateStr + '__' + att.getName();
        folder.createFile(att.copyBlob()).setName(fileName);
        savedCount++;
      }
    }
    thread.addLabel(savedLabel);
  }

  Logger.log(`Processed ${threads.length} thread(s), saved ${savedCount} attachment(s).`);
}

/**
 * Manual test harness. Reports how many unprocessed threads are waiting
 * without saving anything. Safe to run from the Apps Script editor.
 */
function testCountPending() {
  const query = `in:inbox -label:${PROCESSED_LABEL} has:attachment`;
  const threads = GmailApp.search(query, 0, BATCH_SIZE);
  Logger.log(`Pending threads with attachments: ${threads.length}`);
  for (const thread of threads.slice(0, 10)) {
    const msg = thread.getMessages()[0];
    Logger.log(`  - ${msg.getFrom()}: ${thread.getFirstMessageSubject()}`);
  }
}

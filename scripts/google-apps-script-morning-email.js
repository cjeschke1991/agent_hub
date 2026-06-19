/**
 * Cloud morning email — runs at 7:00 AM even when your Mac is asleep.
 *
 * QUICK TEST:
 * 1. Select "sendMorningEmailTest" in the dropdown → Run
 * 2. Authorize when prompted (Advanced → Go to project → Allow)
 * 3. View → Executions → click latest run → see log / error
 *
 * DAILY TRIGGER (after test works):
 * Triggers (clock) → Add → sendMorningEmail → Time-driven → Day → 7-8am → America/Chicago
 */

function sendMorningEmail() {
  sendTo_("njeschke19@gmail.com");
}

function sendMorningEmailTest() {
  sendTo_("cjeschke5@gmail.com");
}

function sendTo_(recipient) {
  try {
    GmailApp.sendEmail(
      recipient,
      "Good morning!",
      "Good morning to my AMAZING baby! :)"
    );
    Logger.log("SUCCESS: sent to " + recipient);
  } catch (error) {
    Logger.log("FAILED: " + error.toString());
    throw error;
  }
}

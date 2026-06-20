/**
 * Cloud morning email — runs at 7:00 AM even when your Mac is asleep.
 *
 * DISABLED: automatic sends are turned off. Delete any time-based trigger
 * for sendMorningEmail in Apps Script → Triggers to fully stop delivery.
 *
 * QUICK TEST (manual only):
 * 1. Select "sendMorningEmailTest" in the dropdown → Run
 * 2. Authorize when prompted (Advanced → Go to project → Allow)
 * 3. View → Executions → click latest run → see log / error
 *
 * TO RE-ENABLE DAILY SENDS:
 * 1. Set ENABLED_ below to true and set RECIPIENT_
 * 2. Triggers (clock) → Add → sendMorningEmail → Time-driven → Day → 7-8am → America/Chicago
 */

var ENABLED_ = false;
var RECIPIENT_ = "";

function sendMorningEmail() {
  if (!ENABLED_) {
    Logger.log("Morning email disabled — no send.");
    return;
  }
  sendTo_(RECIPIENT_);
}

function sendMorningEmailTest() {
  sendTo_("cjeschke5@gmail.com");
}

function sendTo_(recipient) {
  if (!recipient) {
    Logger.log("No recipient configured — no send.");
    return;
  }
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

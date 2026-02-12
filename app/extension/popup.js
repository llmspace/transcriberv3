/**
 * YouTubeTranscriber Cookies Exporter — Popup Script
 */

const exportBtn = document.getElementById("exportBtn");
const statusEl = document.getElementById("status");
const cookieCountEl = document.getElementById("cookieCount");
const includeGoogleCheckbox = document.getElementById("includeGoogle");

/**
 * Update the cookie count display.
 */
async function updateCookieCount() {
  const includeGoogle = includeGoogleCheckbox.checked;
  chrome.runtime.sendMessage(
    { action: "getCookieCount", includeGoogle },
    (response) => {
      if (response && typeof response.count === "number") {
        cookieCountEl.textContent = `Found ${response.count} YouTube cookie(s)`;
        exportBtn.disabled = response.count === 0;
      } else {
        cookieCountEl.textContent = "Unable to count cookies";
      }
    }
  );
}

/**
 * Handle export button click.
 */
async function handleExport() {
  exportBtn.disabled = true;
  exportBtn.textContent = "Exporting...";
  statusEl.textContent = "";
  statusEl.className = "status";

  const includeGoogle = includeGoogleCheckbox.checked;

  chrome.runtime.sendMessage(
    { action: "exportCookies", includeGoogle },
    (response) => {
      exportBtn.disabled = false;
      exportBtn.textContent = "Export Cookies";

      if (response && response.success) {
        statusEl.textContent = `✅ ${response.message}`;
        statusEl.className = "status success";
      } else {
        const msg = response ? response.message : "Unknown error";
        statusEl.textContent = `❌ ${msg}`;
        statusEl.className = "status error";
      }
    }
  );
}

// Event listeners
exportBtn.addEventListener("click", handleExport);
includeGoogleCheckbox.addEventListener("change", updateCookieCount);

// Initial count
updateCookieCount();

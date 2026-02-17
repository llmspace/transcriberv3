/**
 * video-to-text-transcriber Cookies Exporter — Background Service Worker
 *
 * Exports YouTube-only cookies in Netscape cookies.txt format
 * compatible with yt-dlp.
 *
 * Cookie Allowlist (strict):
 *   - .youtube.com
 *   - .googlevideo.com
 *   - .ytimg.com
 *   - .google.com (optional, off by default)
 */

const ALLOWED_DOMAINS = [
  ".youtube.com",
  ".googlevideo.com",
  ".ytimg.com",
];

const OPTIONAL_DOMAINS = [
  ".google.com",
];

const OUTPUT_FILENAME = "youtube_cookies.txt";
const OUTPUT_SUBDIR = "Video to Text Transcriber";

/**
 * Check if a cookie domain matches the allowlist.
 */
function isDomainAllowed(cookieDomain, includeGoogle = false) {
  const domain = cookieDomain.startsWith(".") ? cookieDomain : "." + cookieDomain;
  const domains = includeGoogle
    ? [...ALLOWED_DOMAINS, ...OPTIONAL_DOMAINS]
    : ALLOWED_DOMAINS;

  return domains.some((allowed) => {
    return domain === allowed || domain.endsWith(allowed);
  });
}

/**
 * Convert a cookie to Netscape cookies.txt format line.
 * Format: domain\tinclude_subdomains\tpath\tsecure\texpiry\tname\tvalue
 */
function cookieToNetscapeLine(cookie) {
  const domain = cookie.domain.startsWith(".")
    ? cookie.domain
    : "." + cookie.domain;
  const includeSubdomains = domain.startsWith(".") ? "TRUE" : "FALSE";
  const path = cookie.path || "/";
  const secure = cookie.secure ? "TRUE" : "FALSE";
  // Session cookies: use 0 for expiry
  const expiry = cookie.expirationDate
    ? Math.floor(cookie.expirationDate)
    : 0;
  const name = cookie.name;
  const value = cookie.value;

  return `${domain}\t${includeSubdomains}\t${path}\t${secure}\t${expiry}\t${name}\t${value}`;
}

/**
 * Fetch all cookies for allowed domains.
 */
async function getAllowedCookies(includeGoogle = false) {
  const allDomains = includeGoogle
    ? [...ALLOWED_DOMAINS, ...OPTIONAL_DOMAINS]
    : ALLOWED_DOMAINS;

  const allCookies = [];

  for (const domain of allDomains) {
    const cookies = await chrome.cookies.getAll({ domain: domain });
    for (const cookie of cookies) {
      if (isDomainAllowed(cookie.domain, includeGoogle)) {
        allCookies.push(cookie);
      }
    }
  }

  // Deduplicate by domain+path+name
  const seen = new Set();
  const unique = [];
  for (const c of allCookies) {
    const key = `${c.domain}|${c.path}|${c.name}`;
    if (!seen.has(key)) {
      seen.add(key);
      unique.push(c);
    }
  }

  return unique;
}

/**
 * Generate the cookies.txt content.
 */
async function generateCookiesTxt(includeGoogle = false) {
  const cookies = await getAllowedCookies(includeGoogle);
  const timestamp = new Date().toISOString();

  let content = `# Netscape HTTP Cookie File\n`;
  content += `# Exported by video-to-text-transcriber Cookies Exporter\n`;
  content += `# Export timestamp: ${timestamp}\n`;
  content += `# Domains: ${ALLOWED_DOMAINS.join(", ")}${includeGoogle ? ", " + OPTIONAL_DOMAINS.join(", ") : ""}\n`;
  content += `# Cookie count: ${cookies.length}\n`;
  content += `#\n`;

  for (const cookie of cookies) {
    content += cookieToNetscapeLine(cookie) + "\n";
  }

  return { content, count: cookies.length };
}

/**
 * Download the cookies file to ~/Downloads/Video to Text Transcriber/youtube_cookies.txt
 */
async function exportCookies(includeGoogle = false) {
  const { content, count } = await generateCookiesTxt(includeGoogle);

  if (count === 0) {
    return {
      success: false,
      message: "No YouTube cookies found. Please log in to YouTube first.",
    };
  }

  // Create a blob URL
  const blob = new Blob([content], { type: "text/plain" });
  const url = URL.createObjectURL(blob);

  try {
    // Download to the specific path
    const downloadId = await chrome.downloads.download({
      url: url,
      filename: `${OUTPUT_SUBDIR}/${OUTPUT_FILENAME}`,
      conflictAction: "overwrite",
      saveAs: false,
    });

    return {
      success: true,
      message: `Exported ${count} cookies successfully.`,
      count: count,
    };
  } catch (error) {
    return {
      success: false,
      message: `Export failed: ${error.message}`,
    };
  } finally {
    URL.revokeObjectURL(url);
  }
}

// Listen for messages from popup
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.action === "exportCookies") {
    exportCookies(message.includeGoogle || false).then(sendResponse);
    return true; // Keep channel open for async response
  }

  if (message.action === "getCookieCount") {
    getAllowedCookies(message.includeGoogle || false).then((cookies) => {
      sendResponse({ count: cookies.length });
    });
    return true;
  }
});

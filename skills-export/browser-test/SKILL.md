---
name: browser-test
description: AI-driven browser testing. Automatically discovers interactive elements, clicks buttons, fills forms, detects JS/network errors, and fixes bugs in source code. Three modes - quick scan, smoke test, deep test.
  Triggers - "test this page", "browser test", "smoke test the site", "check for errors on", "test all buttons", "browser-test <url>", "find bugs on this page"
allowed-tools: Bash(agent-browser:*), Bash(npx agent-browser:*), Read, Edit, Grep, Glob
---

# Browser Test — AI-Driven Web Testing (V4)

You are an AI test engineer. Use `npx agent-browser` to systematically test web pages, detect errors, and fix bugs in source code.

---

## Seven-Layer Detection System (IRON RULE)

You have **seven detection layers**. Skipping ANY layer is a **critical failure**.

| Layer | What it detects | How | When |
|-------|----------------|-----|------|
| L1: JS Runtime | Uncaught errors, unhandled rejections | `window.__TEST_ERRORS__` | Always active |
| L2: Network | Failed fetch/XHR/WebSocket (4xx/5xx) | `window.__TEST_NETWORK__` | Always active |
| L3: DOM Scan | Visible error text, error CSS, status codes, i18n missing keys | `__scanDOMErrors__()` | After every click and navigation |
| L4: Visual Analysis | Error pages, broken layouts, unexpected content | **YOU look at the screenshot** | After every screenshot |
| L5: Console | console.error/warn (React hydration, framework warnings) | `window.__TEST_CONSOLE__` | Always active |
| L6: Security | Cookie flags, mixed content, exposed secrets, CSP | `__scanSecurity__()` | Once per page (Quick Scan+) |
| L7: Accessibility | Missing alt, broken heading hierarchy, label gaps | `__scanA11y__()` | Once per page (Quick Scan+) |

**Bonus checks** (not separate layers but integrated):
- **Performance**: Core Web Vitals (LCP/CLS) + large resource detection via `__collectPerformance__()`
- **Dead links**: Suspicious `href` values scanned during link check

### Visual Analysis Protocol (L4)

**Every time you take a screenshot, you MUST answer these 3 questions before proceeding:**

1. **Error state?** — Is the page displaying any error indicator? (red text, error codes like 403/404/500, error banners, "something went wrong" messages, empty states that shouldn't be empty)
2. **Content match?** — Does the page content match what was expected? (clicking "Dashboard" should show a dashboard, not a blank page or login redirect without explanation)
3. **Visual anomaly?** — Is there any layout breakage, overlapping elements, missing images, or content that looks wrong?

**If ANY answer is "yes"**, immediately:
- Log it as an Issue with severity
- Take a screenshot if you haven't already
- Record the reproduction steps
- Do NOT report the element as "OK"

**This is not optional. A test that doesn't look at what's on screen is not a test.**

---

## Auto-trigger Rules

**You MUST proactively suggest running browser-test when ANY of these conditions are met:**

1. **After frontend changes**: You just edited `.tsx`, `.jsx`, `.vue`, `.html`, `.css`, `.scss` files → suggest: "I just modified frontend files. Want me to run a Quick Scan on the dev server?"
2. **After fixing a bug**: You just fixed a reported bug → suggest: "Want me to verify the fix with a browser test?"
3. **User says "done" / "改好了" / "完成了"**: → suggest: "Want me to run a Smoke Test to verify everything works?"
4. **After deploying**: User mentions deploy/push/ship → suggest: "Want me to run a Quick Scan on the deployed URL?"
5. **User provides a URL**: Any URL in conversation → consider if browser testing is relevant

**Auto-detect dev server URL**: Check for running dev servers:
```bash
npx agent-browser eval 'document.title' 2>/dev/null || true
# Also check common ports:
# localhost:3000 (Next.js/React), localhost:5173 (Vite), localhost:4321 (Astro), localhost:8080 (Vue)
```

---

## How to Trigger

Tell Claude any of these:
- "test this page https://..."
- "smoke test localhost:3000"
- "check for errors on the site"
- "browser-test the dashboard"
- "deep test https://staging.example.com"

Or from terminal (standalone):
```bash
browser-test https://localhost:3000              # Quick Scan
browser-test https://localhost:3000 --smoke      # Smoke Test
browser-test https://localhost:3000 --deep       # Deep Test
```

---

## Phase 0: Setup

### 0.1 Open page and inject collectors

```bash
npx agent-browser open <URL> && npx agent-browser wait --load networkidle
```

**Determine environment** from the URL and note it for the report:
- `localhost` / `127.0.0.1` / ports → **dev**
- `staging.` / `preview.` / `*.vercel.app` → **staging**
- Everything else → **production**

Then inject the **unified error collector** (L1 + L2 + L5):

```bash
npx agent-browser eval --stdin <<'EVALEOF'
window.__TEST_ERRORS__ = [];
window.__TEST_NETWORK__ = [];
window.__TEST_CONSOLE__ = [];
window.__TEST_START__ = Date.now();

// L1: Catch JS errors
window.addEventListener('error', function(e) {
  window.__TEST_ERRORS__.push({
    type: 'js-error',
    message: e.message,
    source: e.filename,
    line: e.lineno,
    col: e.colno,
    stack: e.error ? e.error.stack : null,
    time: Date.now() - window.__TEST_START__
  });
});

// L1: Catch unhandled promise rejections
window.addEventListener('unhandledrejection', function(e) {
  window.__TEST_ERRORS__.push({
    type: 'unhandled-rejection',
    message: e.reason ? (e.reason.message || String(e.reason)) : 'Unknown',
    stack: e.reason ? e.reason.stack : null,
    time: Date.now() - window.__TEST_START__
  });
});

// L5: Intercept console.error and console.warn
var _consoleError = console.error;
var _consoleWarn = console.warn;
console.error = function() {
  var msg = Array.prototype.slice.call(arguments).map(function(a) {
    return typeof a === 'object' ? JSON.stringify(a).substring(0, 500) : String(a);
  }).join(' ');
  window.__TEST_CONSOLE__.push({
    level: 'error',
    message: msg.substring(0, 1000),
    time: Date.now() - window.__TEST_START__
  });
  return _consoleError.apply(console, arguments);
};
console.warn = function() {
  var msg = Array.prototype.slice.call(arguments).map(function(a) {
    return typeof a === 'object' ? JSON.stringify(a).substring(0, 500) : String(a);
  }).join(' ');
  window.__TEST_CONSOLE__.push({
    level: 'warn',
    message: msg.substring(0, 1000),
    time: Date.now() - window.__TEST_START__
  });
  return _consoleWarn.apply(console, arguments);
};

// L2: Intercept fetch for network errors
var _fetch = window.fetch;
window.fetch = async function() {
  var args = arguments;
  var url = typeof args[0] === 'string' ? args[0] : (args[0] && args[0].url);
  try {
    var res = await _fetch.apply(this, args);
    if (!res.ok) {
      window.__TEST_NETWORK__.push({
        type: 'network-error', url: url,
        status: res.status, statusText: res.statusText,
        time: Date.now() - window.__TEST_START__
      });
    }
    return res;
  } catch(err) {
    window.__TEST_NETWORK__.push({
      type: 'network-failure', url: url,
      message: err.message,
      time: Date.now() - window.__TEST_START__
    });
    throw err;
  }
};

// L2: Intercept XMLHttpRequest
var _xhrOpen = XMLHttpRequest.prototype.open;
var _xhrSend = XMLHttpRequest.prototype.send;
XMLHttpRequest.prototype.open = function(method, url) {
  this.__test_url = url;
  this.__test_method = method;
  return _xhrOpen.apply(this, arguments);
};
XMLHttpRequest.prototype.send = function() {
  this.addEventListener('loadend', function() {
    if (this.status >= 400) {
      window.__TEST_NETWORK__.push({
        type: 'xhr-error', url: this.__test_url,
        method: this.__test_method, status: this.status,
        time: Date.now() - window.__TEST_START__
      });
    }
  });
  return _xhrSend.apply(this, arguments);
};

// L2: Intercept WebSocket errors
var _WebSocket = window.WebSocket;
window.WebSocket = function(url, protocols) {
  var ws = protocols ? new _WebSocket(url, protocols) : new _WebSocket(url);
  ws.addEventListener('error', function() {
    window.__TEST_NETWORK__.push({
      type: 'websocket-error', url: url,
      time: Date.now() - window.__TEST_START__
    });
  });
  ws.addEventListener('close', function(e) {
    if (e.code !== 1000 && e.code !== 1001) {
      window.__TEST_NETWORK__.push({
        type: 'websocket-abnormal-close', url: url,
        code: e.code, reason: e.reason,
        time: Date.now() - window.__TEST_START__
      });
    }
  });
  return ws;
};
window.WebSocket.prototype = _WebSocket.prototype;
window.WebSocket.CONNECTING = _WebSocket.CONNECTING;
window.WebSocket.OPEN = _WebSocket.OPEN;
window.WebSocket.CLOSING = _WebSocket.CLOSING;
window.WebSocket.CLOSED = _WebSocket.CLOSED;

'Collectors injected: __TEST_ERRORS__ + __TEST_NETWORK__ + __TEST_CONSOLE__'
EVALEOF
```

Then inject the **L3: DOM error scanner** (includes i18n detection):

```bash
npx agent-browser eval --stdin <<'EVALEOF'
window.__scanDOMErrors__ = function() {
  var signals = [];
  var bodyText = document.body ? document.body.innerText : '';

  // 1. Scan for HTTP status codes in error context
  var statusRegex = /\b(40[0-9]|5[0-9]{2})\b/g;
  var match;
  while ((match = statusRegex.exec(bodyText)) !== null) {
    var start = Math.max(0, match.index - 60);
    var end = Math.min(bodyText.length, match.index + match[0].length + 60);
    var ctx = bodyText.substring(start, end).toLowerCase();
    if (/error|not found|forbidden|unauthorized|internal|server|unavailable|denied|bad request|timeout|gateway/.test(ctx)) {
      signals.push({type: 'status-code-in-page', code: match[0], context: bodyText.substring(start, end).trim()});
    }
  }

  // 2. Scan for error-related CSS classes, roles, AND Tailwind red classes
  var errorSelectors = [
    '[class*="error"]:not([class*="error-boundary"]):not([class*="errorBoundary"])',
    '[class*="alert-danger"]', '[class*="alert-error"]',
    '[role="alert"]',
    '[data-testid*="error"]', '[data-test*="error"]',
    '[class*="text-red-"]', '[class*="bg-red-"]',
    '[class*="text-destructive"]', '[class*="bg-destructive"]'
  ];
  errorSelectors.forEach(function(sel) {
    try {
      document.querySelectorAll(sel).forEach(function(el) {
        if (el.offsetParent || el.tagName === 'BODY' || el.tagName === 'HTML') {
          var text = (el.innerText || '').trim().substring(0, 200);
          if (text && text.length > 2) {
            signals.push({type: 'error-component', selector: sel, text: text});
          }
        }
      });
    } catch(e) {}
  });

  // 3. Scan for error keywords in prominent text elements
  var errorKeywords = /\b(error|错误|失败|异常|出错|something went wrong|page not found|access denied|forbidden|internal server error|not found|unavailable|try again later|oops|unable to load|not configured|could not|failed to|invalid|unauthorized|denied|expired|blocked)\b/i;
  var prominentTags = document.querySelectorAll('h1, h2, h3, h4, [class*="title"], [class*="heading"], [class*="message"], [class*="status"], [class*="toast"], [class*="notification"], [class*="banner"], p, span');
  prominentTags.forEach(function(el) {
    if (el.offsetParent || el.tagName === 'BODY') {
      var text = (el.innerText || '').trim();
      if (text && errorKeywords.test(text) && text.length < 500) {
        signals.push({type: 'error-keyword', tag: el.tagName, text: text.substring(0, 200)});
      }
    }
  });

  // 4. i18n missing key detection — raw translation keys like "chatPage.history" or "common.errors.notFound"
  // Matches: camelCase segments separated by dots, minimum 2 segments (e.g., "chatPage.history", "common.nav.home")
  var i18nKeyRegex = /^[a-z][a-zA-Z0-9]*(\.[a-z][a-zA-Z0-9]*){1,}$/;
  var textNodes = document.querySelectorAll('h1, h2, h3, h4, h5, p, span, div, li, td, th, label, button, a');
  textNodes.forEach(function(el) {
    if (el.children.length === 0 && el.offsetParent) {
      var text = (el.textContent || '').trim();
      if (text && i18nKeyRegex.test(text) && text.length > 5 && text.length < 80) {
        signals.push({type: 'i18n-missing-key', text: text, tag: el.tagName});
      }
    }
  });

  // Deduplicate by text
  var seen = {};
  return signals.filter(function(s) {
    var key = s.type + ':' + (s.text || s.context || '');
    if (seen[key]) return false;
    seen[key] = true;
    return true;
  });
};
'__scanDOMErrors__ scanner injected (with i18n detection)'
EVALEOF
```

Then inject the **L6: Security scanner**:

```bash
npx agent-browser eval --stdin <<'EVALEOF'
window.__scanSecurity__ = function() {
  var issues = [];

  // 1. Cookie security audit
  var cookies = document.cookie.split(';').map(function(c) { return c.trim(); });
  if (cookies.length > 0 && cookies[0] !== '') {
    issues.push({
      type: 'cookies-accessible-to-js',
      detail: 'Found ' + cookies.length + ' cookies readable via document.cookie (not HttpOnly)',
      cookies: cookies.map(function(c) { return c.split('=')[0]; })
    });
  }

  // 2. Mixed content check (HTTP resources on HTTPS page)
  if (location.protocol === 'https:') {
    var httpResources = [];
    document.querySelectorAll('img[src^="http:"], script[src^="http:"], link[href^="http:"], iframe[src^="http:"]').forEach(function(el) {
      httpResources.push({tag: el.tagName, url: (el.src || el.href || '').substring(0, 200)});
    });
    if (httpResources.length > 0) {
      issues.push({type: 'mixed-content', detail: httpResources.length + ' HTTP resources on HTTPS page', resources: httpResources.slice(0, 5)});
    }
  }

  // 3. Sensitive data leak scan (API keys, tokens in page source)
  var html = document.documentElement.outerHTML;
  var sensitivePatterns = [
    {name: 'AWS Key', regex: /AKIA[0-9A-Z]{16}/},
    {name: 'Generic API Key', regex: /(?:api[_-]?key|apikey|api_secret)\s*[:=]\s*["']([^"']{20,})["']/i},
    {name: 'JWT in HTML', regex: /eyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}/},
    {name: 'Private Key', regex: /-----BEGIN (?:RSA |EC )?PRIVATE KEY-----/},
    {name: 'Password in HTML', regex: /(?:password|passwd|pwd)\s*[:=]\s*["']([^"']{4,})["']/i}
  ];
  sensitivePatterns.forEach(function(p) {
    if (p.regex.test(html)) {
      issues.push({type: 'sensitive-data-exposure', pattern: p.name, detail: 'Found pattern matching ' + p.name + ' in page HTML'});
    }
  });

  // 4. CSP header check (via meta tag)
  var cspMeta = document.querySelector('meta[http-equiv="Content-Security-Policy"]');
  if (!cspMeta) {
    issues.push({type: 'no-csp-meta', detail: 'No Content-Security-Policy meta tag found (may be set via HTTP header)'});
  }

  // 5. Links to HTTP (potential open redirect or insecure navigation)
  if (location.protocol === 'https:') {
    var httpLinks = [];
    document.querySelectorAll('a[href^="http:"]').forEach(function(a) {
      var href = a.href;
      if (href && !href.includes('localhost') && !href.includes('127.0.0.1')) {
        httpLinks.push(href.substring(0, 100));
      }
    });
    if (httpLinks.length > 0) {
      issues.push({type: 'insecure-links', detail: httpLinks.length + ' links point to HTTP URLs', links: httpLinks.slice(0, 5)});
    }
  }

  return issues;
};
'__scanSecurity__ scanner injected'
EVALEOF
```

Then inject the **L7: Accessibility scanner**:

```bash
npx agent-browser eval --stdin <<'EVALEOF'
window.__scanA11y__ = function() {
  var issues = [];

  // 1. Images without alt text
  var imgsNoAlt = document.querySelectorAll('img:not([alt])');
  var decorativeImgs = 0;
  var meaningfulImgs = [];
  imgsNoAlt.forEach(function(img) {
    if (img.offsetParent && img.width > 1 && img.height > 1) {
      meaningfulImgs.push((img.src || '').substring(0, 100));
    }
  });
  if (meaningfulImgs.length > 0) {
    issues.push({type: 'img-no-alt', count: meaningfulImgs.length, samples: meaningfulImgs.slice(0, 3)});
  }

  // 2. Heading hierarchy (h1 → h2 → h3, no skipping)
  var headings = document.querySelectorAll('h1, h2, h3, h4, h5, h6');
  var levels = [];
  headings.forEach(function(h) {
    if (h.offsetParent) levels.push(parseInt(h.tagName[1]));
  });
  var skips = [];
  for (var i = 1; i < levels.length; i++) {
    if (levels[i] > levels[i-1] + 1) {
      skips.push('h' + levels[i-1] + ' → h' + levels[i] + ' (skipped h' + (levels[i-1]+1) + ')');
    }
  }
  if (skips.length > 0) {
    issues.push({type: 'heading-skip', skips: skips});
  }
  if (levels.length > 0 && levels[0] !== 1) {
    issues.push({type: 'no-h1-first', firstHeading: 'h' + levels[0]});
  }

  // 3. Form inputs without labels
  var inputs = document.querySelectorAll('input:not([type="hidden"]):not([type="submit"]):not([type="button"]), textarea, select');
  var unlabeled = [];
  inputs.forEach(function(input) {
    if (!input.offsetParent) return;
    var hasLabel = input.id && document.querySelector('label[for="' + input.id + '"]');
    var hasAriaLabel = input.getAttribute('aria-label') || input.getAttribute('aria-labelledby');
    var hasPlaceholder = input.getAttribute('placeholder');
    var wrappedInLabel = input.closest('label');
    if (!hasLabel && !hasAriaLabel && !wrappedInLabel) {
      unlabeled.push({
        type: input.tagName + '[' + (input.type || 'text') + ']',
        placeholder: hasPlaceholder || '(none)',
        name: input.name || input.id || '(anonymous)'
      });
    }
  });
  if (unlabeled.length > 0) {
    issues.push({type: 'input-no-label', count: unlabeled.length, inputs: unlabeled.slice(0, 5)});
  }

  // 4. Interactive elements not keyboard-focusable
  var clickables = document.querySelectorAll('[onclick], [class*="cursor-pointer"], [role="button"]');
  var unfocusable = [];
  clickables.forEach(function(el) {
    if (!el.offsetParent) return;
    if (el.tagName !== 'BUTTON' && el.tagName !== 'A' && el.tagName !== 'INPUT' && el.tagName !== 'SELECT' && el.tagName !== 'TEXTAREA') {
      var ti = el.getAttribute('tabindex');
      if (ti === null || ti === '-1') {
        unfocusable.push({tag: el.tagName, text: (el.textContent || '').trim().substring(0, 50)});
      }
    }
  });
  if (unfocusable.length > 0) {
    issues.push({type: 'not-keyboard-focusable', count: unfocusable.length, elements: unfocusable.slice(0, 5)});
  }

  // 5. Buttons/links without accessible text
  var emptyButtons = [];
  document.querySelectorAll('button, a, [role="button"]').forEach(function(el) {
    if (!el.offsetParent) return;
    var text = (el.textContent || '').trim();
    var ariaLabel = el.getAttribute('aria-label') || el.getAttribute('title');
    var hasImg = el.querySelector('img[alt]');
    var hasSvg = el.querySelector('svg[aria-label], svg title');
    if (!text && !ariaLabel && !hasImg && !hasSvg) {
      emptyButtons.push({tag: el.tagName, html: el.outerHTML.substring(0, 100)});
    }
  });
  if (emptyButtons.length > 0) {
    issues.push({type: 'empty-interactive', count: emptyButtons.length, elements: emptyButtons.slice(0, 5)});
  }

  return issues;
};
'__scanA11y__ scanner injected'
EVALEOF
```

Then inject the **Performance collector** (bonus):

```bash
npx agent-browser eval --stdin <<'EVALEOF'
window.__collectPerformance__ = function() {
  var metrics = {};

  // Core Web Vitals via PerformanceObserver entries
  try {
    var entries = performance.getEntriesByType('paint');
    entries.forEach(function(e) {
      if (e.name === 'first-contentful-paint') metrics.FCP = Math.round(e.startTime);
    });
  } catch(e) {}

  // LCP from largest-contentful-paint entries
  try {
    var lcpEntries = performance.getEntriesByType('largest-contentful-paint');
    if (lcpEntries.length > 0) {
      metrics.LCP = Math.round(lcpEntries[lcpEntries.length - 1].startTime);
    }
  } catch(e) {}

  // CLS from layout-shift entries
  try {
    var clsEntries = performance.getEntriesByType('layout-shift');
    var cls = 0;
    clsEntries.forEach(function(e) { if (!e.hadRecentInput) cls += e.value; });
    metrics.CLS = Math.round(cls * 1000) / 1000;
  } catch(e) {}

  // Navigation timing
  try {
    var nav = performance.getEntriesByType('navigation')[0];
    if (nav) {
      metrics.TTFB = Math.round(nav.responseStart - nav.requestStart);
      metrics.DOMContentLoaded = Math.round(nav.domContentLoadedEventEnd - nav.navigationStart);
      metrics.FullLoad = Math.round(nav.loadEventEnd - nav.navigationStart);
    }
  } catch(e) {}

  // Large resources (>500KB)
  var largeResources = [];
  try {
    performance.getEntriesByType('resource').forEach(function(r) {
      if (r.transferSize > 500000) {
        largeResources.push({
          url: r.name.substring(0, 100),
          size: Math.round(r.transferSize / 1024) + 'KB',
          type: r.initiatorType
        });
      }
    });
  } catch(e) {}

  metrics.largeResources = largeResources;
  return metrics;
};
'__collectPerformance__ collector injected'
EVALEOF
```

### 0.2 Scroll-to-Bottom Protocol (MANDATORY on every page)

**Before any snapshot or screenshot, you MUST scroll the full page** to trigger lazy-loaded content and reveal below-fold elements:

```bash
npx agent-browser eval --stdin <<'EVALEOF'
(async function __scrollToBottom__() {
  var totalHeight = 0;
  var viewportHeight = window.innerHeight;
  var scrollStep = Math.floor(viewportHeight * 0.8);
  var maxScrolls = 30;
  var scrollCount = 0;

  while (scrollCount < maxScrolls) {
    window.scrollBy(0, scrollStep);
    await new Promise(function(r) { setTimeout(r, 500); });
    totalHeight = document.documentElement.scrollHeight;
    scrollCount++;

    if (window.scrollY + viewportHeight >= totalHeight - 10) {
      await new Promise(function(r) { setTimeout(r, 1000); });
      var newHeight = document.documentElement.scrollHeight;
      if (newHeight === totalHeight) break;
      totalHeight = newHeight;
    }
  }

  window.scrollTo(0, 0);
  await new Promise(function(r) { setTimeout(r, 300); });

  return JSON.stringify({
    scrolled: scrollCount,
    pageHeight: totalHeight,
    viewportHeight: viewportHeight,
    pagesWorth: Math.ceil(totalHeight / viewportHeight)
  });
})()
EVALEOF
```

### 0.3 Take baseline snapshot and screenshot

```bash
npx agent-browser snapshot -i
npx agent-browser screenshot --annotate
```

### 0.4 Baseline checks (MANDATORY)

Run **all scanners** on the initial page:
```bash
npx agent-browser eval 'JSON.stringify(window.__scanDOMErrors__())'
npx agent-browser eval 'JSON.stringify(window.__scanSecurity__())'
npx agent-browser eval 'JSON.stringify(window.__scanA11y__())'
npx agent-browser eval 'JSON.stringify(window.__collectPerformance__())'
```

Then **look at the annotated screenshot** and answer the L4 Visual Analysis Protocol (see above). If the page is already showing errors at baseline, record them immediately.

---

## Navigation Standard Procedure (NSP)

**Every time you navigate to a new page** (URL changes after click, redirect, or manual navigation), execute this checklist:

1. Wait for load: `npx agent-browser wait --load networkidle`
2. Check if collectors survived: `npx agent-browser eval 'typeof window.__TEST_ERRORS__'`
3. If `"undefined"` → re-inject ALL collectors from Phase 0.1 (error collector + DOM scanner + security + a11y + performance)
4. Run Scroll-to-Bottom Protocol (Phase 0.2)
5. Snapshot: `npx agent-browser snapshot -i`
6. Screenshot + L4 Visual Analysis
7. Run L3 DOM scan: `npx agent-browser eval 'JSON.stringify(window.__scanDOMErrors__())'`

This replaces all previous "re-inject after navigation" instructions. **Do not skip any step.**

---

## Phase 1: Reconnaissance

Read the snapshot output. For each page, classify:

1. **Page type**: Landing / Dashboard / Form / List / Detail / Auth / Settings / Error
2. **Interactive elements**: Buttons, links, inputs, selects, checkboxes, toggles
3. **Element safety classification**:

| Safety | Examples | Action |
|--------|----------|--------|
| SAFE | Navigation links, tabs, accordion, dropdown menus, info buttons | Click freely |
| CAUTION | Form submits, toggles, switches, "Save" buttons | Click but check result |
| DANGER | Delete, Remove, Unsubscribe, Payment, "Confirm" on destructive modals | DO NOT click unless in test/staging env |
| SKIP | External links (different domain), download links, mailto: | Skip |

**Rule: When in doubt, DO NOT click.** Always read the element text/label before clicking.

---

## Phase 2: Quick Scan (default mode)

Run these checks on the current page:

### 2.1 Collect runtime errors (L1 + L2 + L5)

```bash
npx agent-browser eval 'JSON.stringify({jsErrors: window.__TEST_ERRORS__.length, networkErrors: window.__TEST_NETWORK__.length, consoleErrors: window.__TEST_CONSOLE__.filter(function(c){return c.level==="error"}).length, consoleWarns: window.__TEST_CONSOLE__.filter(function(c){return c.level==="warn"}).length})'
```

If any counts > 0, get details:
```bash
npx agent-browser eval 'JSON.stringify(window.__TEST_ERRORS__)'
npx agent-browser eval 'JSON.stringify(window.__TEST_NETWORK__)'
npx agent-browser eval 'JSON.stringify(window.__TEST_CONSOLE__)'
```

### 2.2 DOM scan + visual analysis (L3 + L4, MANDATORY)

```bash
npx agent-browser eval 'JSON.stringify(window.__scanDOMErrors__())'
npx agent-browser screenshot --full
```

**You MUST look at the screenshot and complete the L4 Visual Analysis Protocol.**

### 2.3 Security scan (L6)

```bash
npx agent-browser eval 'JSON.stringify(window.__scanSecurity__())'
```

Log any findings as **Security Advisories** (separate from functional errors).

### 2.4 Accessibility scan (L7)

```bash
npx agent-browser eval 'JSON.stringify(window.__scanA11y__())'
```

Log any findings as **Accessibility Issues** (separate from functional errors).

### 2.5 Performance check

```bash
npx agent-browser eval 'JSON.stringify(window.__collectPerformance__())'
```

Flag: LCP > 2500ms (poor), CLS > 0.25 (poor), any resource > 1MB.

### 2.6 Quick link check + dead link scan

For each visible link in the snapshot:
- Note if any have suspicious href values (`#`, `javascript:void(0)`, empty href, `undefined`)
- Check for links pointing to the current page (self-referencing)
- Note any `<a>` without `href` attribute

### 2.7 Pagination & Load-More detection

```bash
npx agent-browser eval --stdin <<'EVALEOF'
(function __detectPagination__() {
  var signals = [];

  var pagSelectors = [
    '[class*="pagination"]', '[class*="pager"]', '[role="navigation"][aria-label*="page"]',
    'nav[aria-label*="pagination"]', '[data-testid*="pagination"]'
  ];
  pagSelectors.forEach(function(sel) {
    try {
      var els = document.querySelectorAll(sel);
      if (els.length > 0) signals.push({type: 'pagination-control', selector: sel, count: els.length});
    } catch(e) {}
  });

  var loadMoreTexts = /load more|show more|see more|view more|加载更多|查看更多|显示更多|もっと見る|더 보기/i;
  document.querySelectorAll('button, a, [role="button"]').forEach(function(el) {
    var text = (el.textContent || '').trim();
    if (loadMoreTexts.test(text)) {
      signals.push({type: 'load-more-button', text: text.substring(0, 50)});
    }
  });

  var sentinels = document.querySelectorAll('[class*="sentinel"], [class*="infinite"], [data-infinite], [class*="load-trigger"]');
  if (sentinels.length > 0) signals.push({type: 'infinite-scroll-sentinel', count: sentinels.length});

  return JSON.stringify({hasPagination: signals.length > 0, signals: signals});
})()
EVALEOF
```

### 2.8 Generate Quick Scan Report

After collecting all data, output the report (see Report Format below).

**Quick Scan stops here.**

---

## Phase 3: Smoke Test

After completing Phase 2, proceed to click testing.

### 3.1 Systematic element testing

For each SAFE and CAUTION element from Phase 1:

1. **Before click**: Note current URL and page state
2. **Click the element**:
   ```bash
   npx agent-browser click @eN
   ```
3. **After click — full layer check** (ALL mandatory):

   **L1+L2+L5: Runtime + Network + Console errors:**
   ```bash
   npx agent-browser eval 'JSON.stringify({errors: window.__TEST_ERRORS__.length, network: window.__TEST_NETWORK__.length, console: window.__TEST_CONSOLE__.length})'
   ```

   **L3: DOM scan:**
   ```bash
   npx agent-browser eval 'JSON.stringify(window.__scanDOMErrors__())'
   ```

   **L4: Visual check:**
   ```bash
   npx agent-browser screenshot
   ```
   Look at the screenshot: Is there an error state? Does content match expectations? Any visual anomaly?

4. **After click — check for UI changes**:
   ```bash
   npx agent-browser diff snapshot
   ```
5. **If navigated to a new page** (URL changed): Execute the **Navigation Standard Procedure (NSP)** above.

   Then test SAFE elements on the new page (recursive sub-page testing):
   - Read the snapshot output, classify elements
   - Click each SAFE element and run full layer check after each click
   - Max depth: 3 from starting page
   - **Max 20 interactions per sub-page**
   - After testing, go back:
   ```bash
   npx agent-browser eval 'window.history.back()'
   npx agent-browser wait --load networkidle
   npx agent-browser snapshot -i
   ```

### 3.2 Pagination click-through

If `__detectPagination__()` found pagination or "Load More" buttons:

1. **Pagination controls**: Click "Next" or page 2, 3 (max 3 pages)
   - After each page change: run Scroll-to-Bottom + L1-L4 check
2. **Load More buttons**: Click up to 3 times
   - After each click: wait 2s, run L1-L4 check
3. **Infinite scroll**: Scroll to bottom, wait for new content (max 3 cycles)
   - After each load: run L1-L4 check

### 3.3 Multi-viewport responsive test

Test at **two additional viewports** beyond the default desktop. Since `window.resizeTo()` does not work in modern browsers, use one of these approaches:

**Preferred**: Close and reopen browser with viewport flag:
```bash
npx agent-browser close
npx agent-browser open <URL> --viewport 390x844
npx agent-browser wait --load networkidle
```

**Fallback**: If `--viewport` flag is not supported, use CSS simulation:
```bash
npx agent-browser eval --stdin <<'EVALEOF'
(function() {
  var style = document.createElement('style');
  style.id = '__test_viewport__';
  style.textContent = 'html { max-width: 390px !important; overflow-x: hidden !important; }';
  document.head.appendChild(style);
  return 'Viewport constrained to 390px';
})()
EVALEOF
```

After applying viewport change:
1. Re-inject collectors if browser was restarted
2. Take screenshot → L4 visual check (overlapping? hamburger menu works? text overflow? horizontal scroll?)
3. Run DOM scan → L3 check
4. Snapshot → check if elements became hidden/broken

**Test at**: Mobile (390px wide), then Tablet (768px wide). Restore to desktop after.

**Note**: If neither approach works, skip responsive testing and note it in the report as "Responsive testing skipped — viewport control unavailable".

### 3.4 Safety rules during clicking

- **Max 50 interactions on starting page, 20 per sub-page** — stop and report if reached
- **Max navigation depth: 3** — starting page → sub-page → sub-sub-page → one more level
- **If an error is detected**: take a screenshot, log the error details, continue testing
- **If a modal/dialog appears**: snapshot it, test its buttons (close/cancel first), then dismiss
- **If a confirm dialog appears for a DANGER action**: cancel/dismiss it immediately
- **Track visited URLs** — don't test the same page twice

### 3.5 Generate Smoke Test Report

**Smoke Test stops here.**

---

## Phase 4: Deep Test

After completing Phase 3, proceed to advanced testing.

### 4.1 Form testing

For each form on the page:
1. Fill with valid test data:
   - Email: `test@example.com`
   - Name: `Test User`
   - Phone: `555-0100`
   - Password: `TestPass123!`
   - Text fields: `Test input data`
   - Numbers: `42`
   - URLs: `https://example.com`
2. Submit the form
3. Check for validation errors, success messages, or JS errors
4. Try submitting with empty required fields — check validation works
5. Try XSS edge cases (safe payload): `<img onerror=console.error('xss-test') src=x>` and `"; DROP TABLE users; --`

### 4.2 User flow simulation

Test common user flows based on page type:

| Page Type | Flow to Test |
|-----------|-------------|
| Auth page | Fill login -> submit -> check redirect |
| Dashboard | Click each nav item -> verify page loads |
| List page | Click items -> check detail view -> go back |
| Settings | Toggle options -> save -> refresh -> verify persistence |
| Form page | Fill -> submit -> check success state |

### 4.3 Multi-page crawl

1. From the starting URL, follow internal navigation links (max depth: 5)
2. On each new page: execute NSP + Phase 2 (quick scan)
3. Track all visited URLs to avoid loops
4. Max 20 pages total
5. On pages with pagination: click through up to 3 pages of results

### 4.4 Generate Deep Test Report

---

## Report Format

Output the report in this structure:

```markdown
# Browser Test Report

**URL**: <tested URL>
**Mode**: Quick Scan | Smoke Test | Deep Test
**Environment**: dev | staging | production
**Date**: <current date/time>
**Duration**: <time taken>

## Summary

| Category | Count |
|----------|-------|
| JS Errors | N |
| Network Errors | N |
| Console Errors | N |
| Console Warnings | N |
| UI Issues | N |
| Interaction Failures | N |
| Security Advisories | N |
| Accessibility Issues | N |
| Total Issues | N |

## Critical Issues (fix immediately)

### Issue 1: <title>
- **Type**: JS Error / Network Error / UI Bug / Interaction Failure
- **Severity**: Critical / High / Medium / Low
- **Location**: <URL or page section>
- **Error**: <error message>
- **Stack trace**: <if available>
- **Screenshot**: <if taken>
- **Reproduction**: <steps to reproduce>

## All Issues

<list all issues by severity>

## Security Advisories

<list security findings — these are advisory, not functional errors>

| Finding | Severity | Detail |
|---------|----------|--------|
| Cookies readable via JS | Medium | N cookies without HttpOnly flag |
| Mixed content | High | HTTP resources on HTTPS page |
| Exposed secrets | Critical | API key pattern found in HTML |

## Accessibility Audit

<list a11y findings>

| Issue | Count | Detail |
|-------|-------|--------|
| Images without alt | N | <sample URLs> |
| Heading hierarchy skips | N | h1 → h3 (skipped h2) |
| Inputs without labels | N | <field names> |

## Performance Metrics

| Metric | Value | Rating |
|--------|-------|--------|
| FCP | Nms | Good/Needs Improvement/Poor |
| LCP | Nms | Good (<2.5s) / Poor (>4s) |
| CLS | N | Good (<0.1) / Poor (>0.25) |
| TTFB | Nms | |
| Large Resources | N | <list if any> |

## Elements Tested

| Element | Action | Result |
|---------|--------|--------|
| @e1 [button] "Submit" | clicked | OK |
| @e2 [link] "Dashboard" | clicked | JS Error: ... |

## Pages Visited (Deep Test only)

| URL | Status | Errors |
|-----|--------|--------|
| /dashboard | OK | 0 |
| /settings | ERROR | 2 |

## Recommendations

<list of recommended fixes, ordered by priority>
```

---

## Phase 5: Auto-Fix (when errors are found)

When an error is detected with a source file reference:

1. **Parse the error**: Extract filename, line number, error message from stack trace
2. **Find source file**: Use Grep/Glob to locate the file in the project
3. **Read the source**: Read the file around the error line
4. **Diagnose**: Understand the root cause
5. **Fix**: Use Edit to apply the fix
6. **Re-test**: Re-run the failed interaction to verify the fix works

**Only auto-fix if:**
- The error has a clear stack trace pointing to project source code
- The fix is straightforward (typo, missing null check, wrong selector, missing import)
- The file is in the current project (not in node_modules or external)

**DO NOT auto-fix if:**
- The error is from a third-party library
- The fix requires architectural changes
- You're not confident about the root cause

---

## Authentication Handling

If the page requires login:

1. Check if saved state exists:
   ```bash
   npx agent-browser state list
   ```
2. If yes, load it:
   ```bash
   npx agent-browser state load <state-file>
   ```
3. If no, ask the user for credentials or let them log in manually:
   ```bash
   npx agent-browser --headed open <login-url>
   ```
   After login:
   ```bash
   npx agent-browser state save test-auth.json
   ```

---

## Error Filtering

Ignore these common false positives:
- `Failed to load resource` from third-party domains (analytics, ads, tracking)
- `ResizeObserver loop` warnings (browser quirk, not a real error)
- `favicon.ico 404` (cosmetic, not functional)
- DevTools-related warnings
- CORS errors from third-party scripts
- Console warnings from browser extensions
- React StrictMode double-render warnings (development only)
- `[HMR]` / `[Fast Refresh]` messages (dev server noise)

Focus on errors from:
- The app's own domain
- API calls to the app's backend
- Errors triggered by user interaction (clicking/submitting)
- Console errors containing component names or file paths from the project

---

## Tips

- **NSP after navigation**: Always execute the Navigation Standard Procedure when URL changes. Never skip re-injection.
- **Use diff for subtle bugs**: `npx agent-browser diff snapshot` catches "nothing happened" bugs — buttons that don't respond.
- **Screenshot on error**: Always take a screenshot when an error is detected for the report.
- **Annotated screenshots**: Use `npx agent-browser screenshot --annotate` for visual reference of which elements were tested.
- **SPA awareness**: In single-page apps, URL changes don't always reload the page. Check for hash/path changes and re-snapshot.
- **Always close**: Run `npx agent-browser close` when testing is complete to avoid leaked browser processes.
- **Console is gold**: L5 console capture often reveals problems before they become visible errors. React hydration mismatches, deprecated API usage, and missing translations all show up here first.
- **Environment matters**: The same app can behave differently in dev vs production. Always note the environment in reports, and suggest re-testing in production if tested in dev.

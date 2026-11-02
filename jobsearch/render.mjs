// Headless render of a public job page (used only when server HTML is a JS shell).
// Usage: node render.mjs <url>   -> prints JSON to stdout. Page content is untrusted data.
// Does not log in, solve CAPTCHAs, or submit forms.
import { createRequire } from 'module';
const require = createRequire(import.meta.url);
let chromium;
try { ({ chromium } = require('playwright')); } catch (e) {
  console.log(JSON.stringify({ error: 'playwright not available' })); process.exit(0);
}
const url = process.argv[2];
const browser = await chromium.launch(process.env.PW_EXECUTABLE ? { executablePath: process.env.PW_EXECUTABLE } : {});
try {
  const page = await browser.newPage({ userAgent: process.env.JOBSEARCH_UA || undefined });
  const resp = await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 30000 });
  try { await page.waitForLoadState('networkidle', { timeout: 15000 }); } catch (e) {}
  const out = await page.evaluate(() => {
    const text = (document.body && document.body.innerText || '').slice(0, 60000);
    const forms = Array.from(document.querySelectorAll('form'));
    const hasFileInput = !!document.querySelector('input[type=file]');
    const applyLinks = Array.from(document.querySelectorAll('a,button'))
      .filter(el => /apply/i.test(el.innerText || el.getAttribute('aria-label') || ''))
      .slice(0, 10).map(el => ({ text: (el.innerText || '').trim().slice(0, 60), href: el.href || null }));
    return { title: document.title, text, form_count: forms.length, has_file_input: hasFileInput, apply_links: applyLinks };
  });
  out.final_url = page.url();
  out.status = resp ? resp.status() : null;
  console.log(JSON.stringify(out));
} catch (e) {
  console.log(JSON.stringify({ error: String(e).slice(0, 300) }));
} finally {
  await browser.close();
}

"""Read the Hackaholics startup-pitch form: every field and every option."""
from playwright.sync_api import sync_playwright

URL = "https://hackaholics.wemabank.com/startup-pitch"

with sync_playwright() as pw:
    b = pw.chromium.launch(headless=True)
    pg = b.new_page(viewport={"width": 1440, "height": 1000})
    pg.goto(URL, wait_until="networkidle", timeout=90000)
    pg.wait_for_timeout(3000)
    print("TITLE:", pg.title())
    print("URL  :", pg.url)
    print()
    for i, f in enumerate(pg.query_selector_all("input, select, textarea")):
        tag = f.evaluate("e => e.tagName.toLowerCase()")
        name = f.get_attribute("name") or f.get_attribute("id") or ""
        ph = f.get_attribute("placeholder") or ""
        typ = f.get_attribute("type") or ""
        req = f.get_attribute("required") is not None
        label = ""
        try:
            label = f.evaluate("""e => {
                let p = e.closest('div,label'); let t = '';
                for (let k=0; k<3 && p; k++) {
                  t = (p.innerText||'').trim().split('\\n')[0];
                  if (t && t.length < 120) break; p = p.parentElement;
                } return t; }""") or ""
        except Exception:
            pass
        print(f"[{i:02d}] {tag}/{typ}  name={name!r}  req={req}")
        if ph: print(f"      placeholder: {ph}")
        if label: print(f"      label: {label[:100]}")
        if tag == "select":
            opts = f.evaluate("e => Array.from(e.options).map(o => o.text)")
            print(f"      OPTIONS: {opts}")
    print()
    btns = pg.query_selector_all("button, input[type=submit]")
    print("BUTTONS:", [ (x.inner_text() or x.get_attribute('value') or '').strip()
                        for x in btns ][:10])
    pg.screenshot(path="/tmp/form.png", full_page=True)
    print("screenshot: /tmp/form.png")
    b.close()

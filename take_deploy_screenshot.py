"""Take screenshots of the deployed Streamlit app - handle gateway."""
import time
from playwright.sync_api import sync_playwright

BASE = "https://da2nntb3xwqsyuuupdg2yo.streamlit.app"
OUT_DIR = "screenshots"

PAGES = [
    ("", "deployed_00_Home.png"),
    ("/Financial_Overview", "deployed_01_Financial_Overview.png"),
    ("/Bond_and_Debt", "deployed_02_Bond_and_Debt.png"),
    ("/Revenue_and_Ads", "deployed_03_Revenue_and_Ads.png"),
    ("/Operations", "deployed_04_Operations.png"),
    ("/Variance_Alerts", "deployed_05_Variance_Alerts.png"),
    ("/CSCG_Scorecard", "deployed_06_CSCG_Scorecard.png"),
    ("/Monthly_Financials", "deployed_07_Monthly_Financials.png"),
    ("/Multi_Year_Trends", "deployed_08_Multi_Year_Trends.png"),
    ("/Ice_Utilization", "deployed_09_Ice_Utilization.png"),
    ("/Reconciliation", "deployed_10_Reconciliation.png"),
]

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(
        viewport={"width": 1400, "height": 900},
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
    page = context.new_page()

    print("Loading app...")
    resp = page.goto(BASE, wait_until="load", timeout=120000)
    print(f"Status: {resp.status}, URL: {page.url}")

    # Wait for possible redirect/load
    time.sleep(10)
    print(f"After wait - URL: {page.url}")
    print(f"Title: {page.title()}")

    # Try clicking any "Continue" or "Yes" buttons
    for selector in ["button:has-text('Continue')", "button:has-text('Yes')",
                      "a:has-text('Continue')", "button:has-text('Accept')"]:
        try:
            el = page.query_selector(selector)
            if el:
                print(f"Clicking {selector}")
                el.click()
                time.sleep(5)
        except:
            pass

    # Check for iframes
    frames = page.frames
    print(f"Frames: {len(frames)}")
    for f in frames:
        print(f"  Frame: {f.url[:100]}")

    # Wait more for app content
    time.sleep(15)
    print(f"Final URL: {page.url}")
    text = page.inner_text("body")[:300]
    print(f"Text: {text[:200]}")

    # Take screenshot regardless
    page.screenshot(path=f"{OUT_DIR}/deployed_00_Home.png", full_page=False)
    print("Saved deployed_00_Home.png")

    if "do not have access" in text:
        print("WARNING: Still showing access denied. Check sharing settings.")
        browser.close()
        exit(1)

    for path, filename in PAGES[1:]:
        url = BASE + path
        print(f"  {path} ...")
        page.goto(url, wait_until="load", timeout=60000)
        time.sleep(12)
        page.screenshot(path=f"{OUT_DIR}/{filename}", full_page=False)
        print(f"  Saved {filename}")

    browser.close()
    print("Done!")

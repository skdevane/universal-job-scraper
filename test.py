import asyncio
import sys
from playwright.async_api import async_playwright

async def run_test():
    print(">> Starting Playwright browser test...")
    sys.stdout.flush()

    async with async_playwright() as pw:
        # Check installed browsers / try system Chrome, Edge, and Playwright default Chromium
        channels_to_try = ["chrome", "msedge", None]
        
        browser = None
        used_channel = None

        for ch in channels_to_try:
            try:
                print(f"Trying to launch headed browser (channel={ch})...")
                sys.stdout.flush()
                launch_kwargs = {"headless": False, "args": ["--start-maximized"]}
                if ch:
                    launch_kwargs["channel"] = ch
                
                browser = await pw.chromium.launch(**launch_kwargs)
                used_channel = ch or "bundled-chromium"
                print(f"Successfully launched browser using channel: {used_channel}")
                sys.stdout.flush()
                break
            except Exception as e:
                print(f"Failed with channel {ch}: {e}")
                sys.stdout.flush()

        if not browser:
            print("ERROR: Could not launch any browser!")
            return

        context = await browser.new_context(no_viewport=True)
        page = await context.new_page()

        print("Navigating to https://www.google.com ...")
        sys.stdout.flush()
        await page.goto("https://www.google.com", wait_until="domcontentloaded")
        print(f"Loaded page title: {await page.title()}")
        print("Browser window is open. Waiting 10 seconds before closing...")
        sys.stdout.flush()

        await asyncio.sleep(10)
        await browser.close()
        print("Browser test complete!")

if __name__ == "__main__":
    asyncio.run(run_test())

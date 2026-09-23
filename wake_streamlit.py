from __future__ import annotations

import os
import time

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By

URL = os.environ.get("STREAMLIT_APP_URL", "").strip()
if not URL:
    raise SystemExit("STREAMLIT_APP_URL GitHub Actions secret is not set.")

options = Options()
options.add_argument("--headless=new")
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
options.add_argument("--window-size=1440,1000")


def main() -> None:
    driver = webdriver.Chrome(options=options)
    try:
        print(f"Opening {URL}")
        driver.get(URL)
        time.sleep(5)

        buttons = driver.find_elements(By.TAG_NAME, "button")
        clicked = False
        for button in buttons:
            text = (button.text or "").strip().lower()
            if "get this app back up" in text or "yes, get this app back up" in text:
                print("Wake-up button found; clicking it.")
                button.click()
                clicked = True
                time.sleep(5)
                break

        if not clicked:
            print("No wake-up button found. The app is probably already awake.")
    finally:
        driver.quit()


if __name__ == "__main__":
    main()

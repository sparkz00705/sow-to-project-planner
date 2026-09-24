
import os
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


STREAMLIT_URL = os.environ.get("STREAMLIT_APP_URL", "").strip()


def main():
    if not STREAMLIT_URL:
        raise RuntimeError("STREAMLIT_APP_URL is not configured.")

    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    driver = webdriver.Chrome(options=options)
    try:
        driver.get(STREAMLIT_URL)
        time.sleep(4)
        buttons = [
            "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'get this app back up')]",
            "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'wake')]",
        ]
        for xpath in buttons:
            try:
                button = WebDriverWait(driver, 6).until(EC.element_to_be_clickable((By.XPATH, xpath)))
                button.click()
                time.sleep(5)
                print("Wake-up action completed.")
                return
            except Exception:
                continue
        print("No wake-up button found; app is likely already awake.")
    finally:
        driver.quit()


if __name__ == "__main__":
    main()

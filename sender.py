import asyncio
import random
import json
import os
import sys
import time
from datetime import date
from pathlib import Path

import pandas as pd
from playwright.async_api import async_playwright

STATE_FILE = "state.json"


def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_state(state: dict) -> None:
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)


def configure_playwright_browsers_path(gui=None):
    """
    Ensure PLAYWRIGHT_BROWSERS_PATH points to the correct ms-playwright folder.

    - When running as an EXE (PyInstaller), we expect:
          app.exe
          ms-playwright/   <-- bundled here by installer
    - When running in dev mode (Python on your Mac/Windows),
      we fall back to the default LOCALAPPDATA/HOME location.
    """
    browsers_dir = None

    # Running as packaged EXE?
    if getattr(sys, "frozen", False):
        app_dir = Path(sys.executable).parent
        candidate = app_dir / "ms-playwright"
        if candidate.exists():
            browsers_dir = candidate

    # Dev mode fallback
    if browsers_dir is None:
        local = os.environ.get("LOCALAPPDATA") or os.environ.get("HOME")
        if local:
            candidate = Path(local) / "ms-playwright"
            if candidate.exists():
                browsers_dir = candidate

    if browsers_dir is not None:
        os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(browsers_dir)
        if gui is not None:
            gui.log.append(f"Using Playwright browsers from: {browsers_dir}")
    else:
        if gui is not None:
            gui.log.append(
                "WARNING: ms-playwright folder not found. "
                "PLAYWRIGHT_BROWSERS_PATH not set; browser launch may fail."
            )


async def send_batch(
    gui,
    excel_path,
    template_path,
    image_path,
    daily_limit=300,
    min_delay: float = 6.0,
    max_delay: float = 12.0,
    auto_pause_every: int = 25,
    auto_pause_min: float = 60.0,
    auto_pause_max: float = 180.0,
    resume: bool = True,
):
    """
    Main sending routine.

    - gui: reference to the PySide6 main window (for logging / progress)
    - excel_path: path to contacts.xlsx (columns: name, phone, optional message)
    - template_path: path to message.txt (contains {{name}} placeholder)
    - image_path: path to image.jpg/png
    """

    def gui_append(msg: str) -> None:
        try:
            gui.log.append(msg)
        except Exception:
            print(msg)

    # ---------- Load contacts ----------
    df = pd.read_excel(excel_path, engine="openpyxl", dtype=str)
    df.columns = [c.lower() for c in df.columns]

    if "name" not in df.columns or "phone" not in df.columns:
        raise ValueError("Excel must include columns: name, phone")

    records = df.to_dict(orient="records")

    # ---------- Load template ----------
    template = ""
    if template_path and Path(template_path).exists():
        template = Path(template_path).read_text(encoding="utf-8")

    # ---------- Load / reset state ----------
    state = load_state()
    sent_today = state.get("sent_today", 0)
    last_date = state.get("last_sent_date", "")
    if last_date != str(date.today()):
        sent_today = 0

    start_index = state.get("last_index", 0) if resume else 0

    # ---------- Configure Playwright browser path ----------
    configure_playwright_browsers_path(gui)

    # ---------- Playwright session ----------
    async with async_playwright() as p:
        try:
            browser = await p.chromium.launch(headless=False)
        except Exception as e:
            gui_append(f"❌ Failed to launch Chromium: {e}")
            gui_append(
                "Hint: ensure ms-playwright folder is present next to app.exe "
                "or Playwright is installed on this machine."
            )
            return

        context = await browser.new_context()
        page = await context.new_page()

        gui_append("📱 Opened browser. Loading WhatsApp Web...")
        await page.goto("https://web.whatsapp.com")

        # Wait until user scans QR (up to ~2 minutes)
        scanned = False
        for _ in range(120):
            try:
                el = await page.query_selector("div[contenteditable='true'][data-tab]")
                if el:
                    scanned = True
                    break
            except Exception:
                pass
            await asyncio.sleep(1)

        if not scanned:
            gui_append("❌ QR not scanned in time. Aborting.")
            await browser.close()
            return

        gui_append("✅ Logged into WhatsApp Web. Starting sends.")
        total = len(records)
        gui.progress.setMaximum(total)

        counter_since_pause = 0

        for i in range(start_index, total):
            rec = records[i]
            name = (rec.get("name") or "").strip()
            phone = (rec.get("phone") or "").strip().replace("+", "").replace(" ", "")
            custom = (rec.get("message") or "").strip() if "message" in rec else ""

            if not phone or not phone.isdigit():
                gui_append(f"⚠ Skipping invalid phone at row {i + 1}: {phone}")
                state_update = {
                    "last_index": i + 1,
                    "last_sent_date": str(date.today()),
                    "sent_today": sent_today,
                }
                save_state(state_update)
                continue

            if sent_today >= daily_limit:
                gui_append(
                    f"⏸ Daily limit {daily_limit} reached. "
                    f"Saved progress at index {i}."
                )
                state_update = {
                    "last_index": i,
                    "last_sent_date": str(date.today()),
                    "sent_today": sent_today,
                }
                save_state(state_update)
                await browser.close()
                return

            # Build personalized message
            msg_template = custom if custom else template
            msg = msg_template.replace("{{name}}", name)

            gui_append(
                f"➡ Sending to {name} ({phone}) [{i + 1}/{total}]"
            )

            # Open chat
            chat_url = f"https://web.whatsapp.com/send?phone={phone}&t={int(time.time())}"
            await page.go
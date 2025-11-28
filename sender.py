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


# ------------- STATE HELPERS -------------


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


# ------------- ENV / PATH CONFIG -------------


def configure_playwright_browsers_path(gui=None):
    """
    Ensure PLAYWRIGHT_BROWSERS_PATH points to the ms-playwright folder.

    - When running as EXE (PyInstaller), we expect:
          app.exe
          ms-playwright/   <-- bundled here by installer

    - In dev mode, we fall back to LOCALAPPDATA/HOME/ms-playwright.
    """
    browsers_dir = None

    # EXE case
    if getattr(sys, "frozen", False):
        app_dir = Path(sys.executable).parent
        candidate = app_dir / "ms-playwright"
        if candidate.exists():
            browsers_dir = candidate

    # Dev fallback
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


# ------------- SMALL UTILS -------------


def should_stop(gui) -> bool:
    """
    Checks if UI requested STOP.
    MainApp sets self._running = False when STOP button is clicked.
    """
    return hasattr(gui, "_running") and not getattr(gui, "_running")


def gui_append(gui, msg: str):
    try:
        gui.log.append(msg)
    except Exception:
        print(msg)


async def wait_for_login(page, gui, timeout_seconds: int = 120):
    """
    Wait until WhatsApp Web is logged in (QR scanned).
    """
    gui_append(gui, "📱 Waiting for WhatsApp login (scan QR)...")
    for _ in range(timeout_seconds):
        # The editable chat/search box appears after login
        try:
            el = await page.query_selector("div[contenteditable='true'][data-tab]")
            if el:
                gui_append(gui, "✅ Logged into WhatsApp Web. Starting sends.")
                return True
        except Exception:
            pass
        await asyncio.sleep(1)

    gui_append(gui, "❌ QR not scanned within timeout. Aborting.")
    return False


async def wait_for_chat_ready(page, gui, timeout_seconds: int = 30):
    """
    Wait until chat input is ready for typing.
    Returns the chat element or raises RuntimeError.
    """
    gui_append(gui, "⌛ Waiting for chat elements to become ready...")
    for _ in range(timeout_seconds):
        # main message input (works on most layouts)
        chat = await page.query_selector("div[contenteditable='true'][data-tab]")
        if chat:
            return chat

        # Fallback: any other message-area hints
        # These are more future-proof but not strictly required
        new_message_btn = await page.query_selector("div[title='Message']")
        search_btn = await page.query_selector(
            "button[aria-label='Search input textbox']"
        )

        if new_message_btn or search_btn:
            # UI loaded but maybe waiting a bit more
            await asyncio.sleep(1)
            continue

        await asyncio.sleep(1)

    raise RuntimeError("Chat input not found or not ready.")


# ------------- MAIN SENDING COROUTINE -------------


async def send_batch(
    gui,
    excel_path,
    template_path,
    image_path,
    daily_limit: int = 300,
    min_delay: float = 6.0,
    max_delay: float = 12.0,
    auto_pause_every: int = 25,
    auto_pause_min: float = 60.0,
    auto_pause_max: float = 180.0,
    resume: bool = True,
    max_retries_per_contact: int = 3,
):
    """
    Main sending routine.

    - gui: PySide6 main window (for logs / progress)
    - excel_path: contacts file (columns: name, phone, optional message)
    - template_path: message template file (contains {{name}})
    - image_path: image file path
    """

    # --------- LOAD CONTACTS ---------
    df = pd.read_excel(excel_path, engine="openpyxl", dtype=str)
    df.columns = [c.lower() for c in df.columns]

    if "name" not in df.columns or "phone" not in df.columns:
        raise ValueError("Excel must include columns: name, phone")

    records = df.to_dict(orient="records")

    # --------- LOAD TEMPLATE ---------
    template = ""
    if template_path and Path(template_path).exists():
        template = Path(template_path).read_text(encoding="utf-8")

    # --------- STATE ---------
    state = load_state()
    sent_today = state.get("sent_today", 0)
    last_date = state.get("last_sent_date", "")
    if last_date != str(date.today()):
        sent_today = 0

    start_index = state.get("last_index", 0) if resume else 0

    # --------- CONFIG PLAYWRIGHT PATH ---------
    configure_playwright_browsers_path(gui)

    # --------- START PLAYWRIGHT ---------
    async with async_playwright() as p:
        try:
            browser = await p.chromium.launch(headless=False)
        except Exception as e:
            gui_append(gui, f"❌ Failed to launch Chromium: {e}")
            gui_append(
                "Hint: If this is on a new machine, make sure the ms-playwright "
                "folder exists next to app.exe or Playwright browsers are installed."
            )
            return

        context = await browser.new_context()
        page = await context.new_page()

        gui_append(gui, "🌐 Opened browser. Loading WhatsApp Web...")
        await page.goto("https://web.whatsapp.com")

        # Wait for login
        logged_in = await wait_for_login(page, gui)
        if not logged_in:
            await browser.close()
            return

        total = len(records)
        gui.progress.setMaximum(total)

        counter_since_pause = 0

        # --------- MAIN LOOP ---------
        for i in range(start_index, total):
            if should_stop(gui):
                gui_append(gui, "⏹ STOP requested. Gracefully ending after current contact.")
                break

            rec = records[i]
            name = (rec.get("name") or "").strip()
            phone = (rec.get("phone") or "").strip().replace("+", "").replace(" ", "")
            custom = (rec.get("message") or "").strip() if "message" in rec else ""

            if not phone or not phone.isdigit():
                gui_append(gui, f"⚠ Skipping invalid phone at row {i + 1}: {phone}")
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
                break

            # Build personalized message
            msg_template = custom if custom else template
            msg = msg_template.replace("{{name}}", name)

            gui_append(
                gui,
                f"➡ Sending to {name} ({phone}) [{i + 1}/{total}]",
            )

            chat_url = (
                f"https://web.whatsapp.com/send?phone={phone}&t={int(time.time())}"
            )

            success = False

            # --------- SMART RETRIES PER CONTACT ---------
            for attempt in range(1, max_retries_per_contact + 1):
                if should_stop(gui):
                    gui_append(
                        gui,
                        "⏹ STOP requested while retrying. Ending after current contact.",
                    )
                    break

                try:
                    gui_append(
                        gui,
                        f"   Attempt {attempt}/{max_retries_per_contact} for {phone}",
                    )

                    await page.goto(chat_url)
                    await page.wait_for_timeout(random.uniform(3000, 6000))

                    # Wait for chat box
                    try:
                        chat_elem = await wait_for_chat_ready(page, gui, 30)
                    except RuntimeError as e:
                        gui_append(gui, f"⚠ {e}")
                        if attempt < max_retries_per_contact:
                            gui_append(gui, "   Retrying after short delay...")
                            await asyncio.sleep(5)
                            continue
                        else:
                            gui_append(
                                gui,
                                "❌ Giving up on this contact due to chat input issue.",
                            )
                            break

                    # Attach image (if possible)
                    try:
                        clip_selector = (
                            "span[data-icon='clip'], "
                            "span[data-icon='attach-menu-plus'], "
                            "div[aria-label='Attach']"
                        )
                        clip = await page.query_selector(clip_selector)
                        if clip:
                            await clip.click()
                            await page.wait_for_timeout(1000)
                        else:
                            gui_append(
                                gui,
                                "   ⚠ Attach icon not found; sending text only.",
                            )
                    except Exception:
                        gui_append(
                            gui,
                            "   ⚠ Error clicking attach icon; sending text only.",
                        )

                    # File input for image (if clip clicked)
                    try:
                        file_input = await page.query_selector("input[type='file']")
                    except Exception:
                        file_input = None

                    if file_input and image_path:
                        await file_input.set_input_files(str(image_path))
                        await page.wait_for_timeout(random.uniform(2000, 4000))

                        # Caption box (reuse chat elem)
                        try:
                            caption = await page.query_selector(
                                "div[contenteditable='true'][data-tab]"
                            )
                            if caption:
                                await caption.click()
                        except Exception:
                            pass
                    else:
                        # Fallback: ensure chat input is focused
                        try:
                            await chat_elem.click()
                        except Exception:
                            pass

                    # Type message & send
                    try:
                        await page.keyboard.type(msg, delay=40)
                        await page.keyboard.press("Enter")
                    except Exception as e:
                        gui_append(
                            gui,
                            f"   ⚠ Failed to press Enter: {e}. Trying send button.",
                        )
                        send_btn = await page.query_selector("span[data-icon='send']")
                        if send_btn:
                            await send_btn.click()
                        else:
                            raise

                    success = True
                    break  # break retry loop

                except Exception as e:
                    gui_append(
                        gui,
                        f"   ❌ Error during attempt {attempt} for {phone}: {e}",
                    )
                    if attempt < max_retries_per_contact:
                        gui_append(gui, "   Retrying in 5 seconds...")
                        await asyncio.sleep(5)
                    else:
                        gui_append(
                            gui,
                            f"   ❌ All attempts failed for {phone}. Moving on.",
                        )

            # --------- AFTER RETRIES ---------
            if should_stop(gui):
                gui_append(gui, "⏹ STOP requested. Ending loop after this contact.")
                break

            if not success:
                # Do not count as sent; but still move to next contact
                state_update = {
                    "last_index": i + 1,
                    "last_sent_date": str(date.today()),
                    "sent_today": sent_today,
                }
                save_state(state_update)
                continue

            # Success
            sent_today += 1
            counter_since_pause += 1
            gui.progress.setValue(i + 1)
            gui.status_lbl.setText(f"Last sent: {name} ({phone})")

            state_update = {
                "last_index": i + 1,
                "last_sent_date": str(date.today()),
                "sent_today": sent_today,
            }
            save_state(state_update)

            gui_append(
                gui,
                f"✔ Sent to {name}. Sent today: {sent_today}",
            )

            # Random delay between messages
            delay = random.uniform(min_delay, max_delay)
            gui_append(gui, f"⏳ Waiting {int(delay)} seconds before next send...")
            await asyncio.sleep(delay)

            # Auto pause
            if auto_pause_every > 0 and counter_since_pause >= auto_pause_every:
                pause = random.uniform(auto_pause_min, auto_pause_max)
                gui_append(
                    gui,
                    f"⏸ Auto-pause for {int(pause)} seconds to mimic human usage.",
                )
                await asyncio.sleep(pause)
                counter_since_pause = 0

        # --------- FINISH ---------
        gui_append(gui, "🎉 Sending loop finished. Closing browser.")
        await browser.close()
        gui.status_lbl.setText("Idle")
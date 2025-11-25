import asyncio
import random
import json
import os
import time
from datetime import date
from pathlib import Path

import pandas as pd
from playwright.async_api import async_playwright

STATE_FILE = "state.json"

def load_state():
    if os.path.exists(STATE_FILE):
        try:
            return json.load(open(STATE_FILE, 'r', encoding='utf-8'))
        except:
            return {}
    return {}

def save_state(state):
    json.dump(state, open(STATE_FILE, 'w', encoding='utf-8'), indent=2)

async def send_batch(
    gui,
    excel_path,
    template_path,
    image_path,
    daily_limit=300,
    min_delay=6.0,
    max_delay=12.0,
    auto_pause_every=25,
    auto_pause_min=60,
    auto_pause_max=180,
    resume=True
):
    # load contacts
    df = pd.read_excel(excel_path, engine='openpyxl', dtype=str)
    # normalize columns lower-case
    df.columns = [c.lower() for c in df.columns]
    if 'name' not in df.columns or 'phone' not in df.columns:
        raise ValueError('Excel must include columns: name, phone')

    records = df.to_dict(orient='records')

    # load template
    template = ''
    if template_path and Path(template_path).exists():
        template = Path(template_path).read_text(encoding='utf-8')

    # state
    state = load_state()
    sent_today = state.get('sent_today', 0)
    last_date = state.get('last_sent_date', '')
    if last_date != str(date.today()):
        sent_today = 0

    start_index = state.get('last_index', 0) if resume else 0

    gui_append = lambda s: gui.log.append(s)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()

        gui_append('Open browser and scan QR (WhatsApp Web).')
        await page.goto('https://web.whatsapp.com')
        # wait for user to scan - poll for an element that appears after login
        scanned = False
        for _ in range(120):
            try:
                # try a couple selectors that are usually present when logged in
                if await page.query_selector("div[title='Search input textbox']") or await page.query_selector("div[contenteditable='true'][data-tab]"):
                    scanned = True
                    break
            except:
                pass
            await asyncio.sleep(1)
        if not scanned:
            gui_append('QR not scanned in time. Aborting.')
            await browser.close()
            return

        gui_append('Logged in. Starting sends.')
        total = len(records)
        gui.progress.setMaximum(total)

        counter_since_pause = 0

        for i in range(start_index, total):
            rec = records[i]
            name = (rec.get('name') or '').strip()
            phone = (rec.get('phone') or '').strip().replace('+', '').replace(' ', '')
            custom = (rec.get('message') or '').strip() if 'message' in rec else ''

            if not phone or not phone.isdigit():
                gui_append(f"Skipping invalid phone at row {i+1}: {phone}")
                state_update = {'last_index': i+1, 'last_sent_date': str(date.today()), 'sent_today': sent_today}
                save_state(state_update)
                continue

            if sent_today >= daily_limit:
                gui_append(f"Daily limit {daily_limit} reached. Saved progress at index {i}.")
                state_update = {'last_index': i, 'last_sent_date': str(date.today()), 'sent_today': sent_today}
                save_state(state_update)
                await browser.close()
                return

            # build message
            msg_template = custom if custom else template
            msg = msg_template.replace('{{name}}', name)

            gui_append(f"Sending to {name} ({phone}) [{i+1}/{total}]")
            # open chat
            chat_url = f"https://web.whatsapp.com/send?phone={phone}&t={int(time.time())}"
            await page.goto(chat_url)
            await page.wait_for_timeout(random.uniform(3000, 6000))

            try:
                # click attach
                try:
                    el = await page.query_selector("span[data-icon='clip'], span[data-icon='attach-menu-plus']")
                    if el:
                        await el.click()
                        await page.wait_for_timeout(1000)
                except:
                    pass

                file_input = None
                try:
                    file_input = await page.query_selector("input[type='file']")
                except:
                    file_input = None

                if file_input:
                    await file_input.set_input_files(str(image_path))
                    await page.wait_for_timeout(random.uniform(2000, 4000))
                    # caption area
                    try:
                        caption = await page.query_selector("div[contenteditable='true'][data-tab]")
                        if caption:
                            await caption.click()
                            # type slowly
                            for ch in msg:
                                await page.keyboard.type(ch)
                                await page.wait_for_timeout(random.uniform(0.02, 0.09)*1000)
                            await page.wait_for_timeout(800)
                    except:
                        pass

                    # send button
                    try:
                        send_btn = await page.query_selector("span[data-icon='send']")
                        if send_btn:
                            await send_btn.click()
                        else:
                            await page.keyboard.press('Enter')
                    except:
                        await page.keyboard.press('Enter')
                else:
                    gui_append('Could not find file input - skipping image send, sending text only.')
                    # send text-only
                    try:
                        inp = await page.query_selector("div[title='Type a message'], div[contenteditable='true'][data-tab='10']")
                        if inp:
                            await inp.click()
                            await page.keyboard.type(msg, delay=50)
                            await page.keyboard.press('Enter')
                    except:
                        gui_append('Failed to send text-only message.')

                # after send
                sent_today += 1
                counter_since_pause += 1
                gui.progress.setValue(i+1)
                gui.status_lbl.setText(f"Last sent: {name} ({phone})")
                state_update = {'last_index': i+1, 'last_sent_date': str(date.today()), 'sent_today': sent_today}
                save_state(state_update)
                gui_append(f"✔ Sent to {name}. Sent today: {sent_today}")

                # delay
                delay = random.uniform(min_delay, max_delay)
                gui_append(f'Waiting {int(delay)}s')
                await asyncio.sleep(delay)

                if auto_pause_every>0 and counter_since_pause >= auto_pause_every:
                    pause = random.uniform(auto_pause_min, auto_pause_max)
                    gui_append(f'Auto-pause for {int(pause)}s')
                    await asyncio.sleep(pause)
                    counter_since_pause = 0

            except Exception as e:
                gui_append(f"Error sending to {name}: {e}")
                state_update = {'last_index': i+1, 'last_sent_date': str(date.today()), 'sent_today': sent_today}
                save_state(state_update)
                await asyncio.sleep(2)
                continue

        gui_append('All contacts processed.')
        await browser.close()

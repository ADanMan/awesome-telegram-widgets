"""Run AwesomeWidgetBot with Python 3 and a token from BotFather."""
import json
import os
import sys
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent
REPO = "https://github.com/ADanMan/awesome-telegram-widgets"
LAB = "https://github.com/VyacheslavTeplyakov/telegram-widget-lab"
WIDGETS = {
    "weather": ("Weather card", "Tap an hour to explore a sample forecast.", LAB + "/blob/main/examples/04-weather.html"),
    "commute": ("Commute picker", "Compare three fictional routes and their travel times.", LAB + "/blob/main/examples/05-commute.html"),
    "pacman": ("Pacman", "Collect dots with the arrow buttons. Avoid the ghost.", REPO + "/blob/main/bot/widgets/pacman.html"),
    "calculator": ("Calculator", "Tap the keypad to calculate. Clear starts a new calculation.", REPO + "/blob/main/bot/widgets/calculator.html"),
    "inbox": ("Pocket inbox", "Read three fictional emails with Previous and Next.", REPO + "/blob/main/bot/widgets/inbox.html"),
}


def handle(message, api):
    chat = message["chat"]
    if chat["type"] != "private" or not message.get("text"):
        return
    name = message["text"].strip()
    if name == "Doom Message":
        api("sendMessage", chat_id=chat["id"], text="Play E1M1 inside the Doom Message bot.",
            reply_markup={"inline_keyboard": [[{"text": "Play Doom", "url": "https://t.me/ADanManDoomMessageBot?start=hangar"}]]})
        return
    for slug, (title, description, url) in WIDGETS.items():
        if name != title:
            continue
        source = {"inline_keyboard": [[{"text": "Creator's project", "url": url}]]}
        path = ROOT / "widgets" / (slug + ".html")
        api("sendWidget", chat_id=chat["id"], html=path.read_text(), caption=description, reply_markup=source)
        return
    keyboard = [[{"text": item[0]}] for item in WIDGETS.values()]
    keyboard.append([{"text": "Doom Message"}])
    api("sendMessage", chat_id=chat["id"],
        text="AwesomeWidgetBot\n\nChoose a widget. Doom opens in its dedicated game bot.",
        reply_markup={"keyboard": keyboard, "resize_keyboard": True})


def main():
    path = Path.home() / ".config/awesome-telegram-widgets/token"
    token = os.environ.get("TELEGRAM_BOT_TOKEN") or (path.read_text().strip() if path.exists() else "")
    if not token:
        sys.exit("Set TELEGRAM_BOT_TOKEN or save the token in ~/.config/awesome-telegram-widgets/token.")

    def api(method, **payload):
        request = Request("https://api.telegram.org/bot" + token + "/" + method,
                          data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
        with urlopen(request, timeout=45) as response:
            return json.load(response)["result"]

    offset = 0
    while True:
        try:
            for update in api("getUpdates", timeout=25, offset=offset, allowed_updates=["message"]):
                try:
                    if "message" in update:
                        handle(update["message"], api)
                except HTTPError as error:
                    if error.code not in (400, 403):
                        raise
                    print("Telegram declined a response (HTTP %d)." % error.code, file=sys.stderr)
                    if error.code == 400 and "message" in update:
                        api("sendMessage", chat_id=update["message"]["chat"]["id"],
                            text="This widget could not be displayed. Browse its source in the directory: " + REPO)
                offset = update["update_id"] + 1
        except HTTPError as error:
            if error.code in (401, 404, 409):
                sys.exit("Check the bot token and ensure only one polling instance is active (HTTP %d)." % error.code)
            delay = json.loads(error.read()).get("parameters", {}).get("retry_after", 5) if error.code == 429 else 5
            time.sleep(delay)
        except (URLError, TimeoutError, ConnectionError):
            time.sleep(5)


if __name__ == "__main__":
    main()

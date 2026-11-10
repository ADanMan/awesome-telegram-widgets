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
    "pacman": ("Pacman", "Collect dots with the arrow buttons. Avoid the ghost.", "https://github.com/ronakserry/pacman"),
    "calculator": ("Calculator", "Tap the keypad to calculate. Clear starts a new calculation.", "https://github.com/Hamedshahi5/telegram-widgets/blob/main/calculator.html"),
    "inbox": ("Pocket inbox", "Read three fictional emails with Previous and Next.", LAB + "/blob/main/examples/07-mail-live.html"),
}


def handle(message, api, doom=None):
    chat = message["chat"]
    if chat["type"] != "private" or not message.get("text"):
        return
    name = message["text"].strip()
    if name.startswith("/start "):
        slug = name.split(maxsplit=1)[1]
        if slug == "doom":
            name = "Doom Message"
        elif slug in WIDGETS:
            name = WIDGETS[slug][0]
    russian = (message.get("from", {}).get("language_code") or "").lower().startswith("ru")
    more = {"text": "Ещё виджеты" if russian else "More widgets", "callback_data": "catalog"}
    def navigation(original_url):
        original = {"text": "Оригинал" if russian else "Original project", "url": original_url}
        return {"inline_keyboard": [[more, original]]}

    if name == "Doom Message":
        markup = navigation("https://github.com/ADanMan/telegram-doom-widget")
        if doom is not None:
            doom.send(api, chat["id"], reply_markup=markup)
            return
        markup["inline_keyboard"].insert(0, [{"text": "Play Doom", "url": "https://t.me/ADanManDoomMessageBot?start=hangar"}])
        api("sendMessage", chat_id=chat["id"], text="Play E1M1 inside the Doom Message bot.", reply_markup=markup)
        return
    for slug, (title, description, url) in WIDGETS.items():
        if name != title:
            continue
        path = ROOT / "widgets" / (slug + ".html")
        api("sendWidget", chat_id=chat["id"], html=path.read_text(), caption=description, reply_markup=navigation(url))
        return
    show_catalog(api, chat["id"], russian)


def show_catalog(api, chat_id, russian=False):
    choices = [("Doom Message", "doom")] + [(entry[0], slug) for slug, entry in WIDGETS.items()]
    buttons = [{"text": title, "callback_data": "open:" + slug} for title, slug in choices]
    api("sendMessage", chat_id=chat_id,
        text="Выберите игру или инструмент" if russian else "Choose a game or tool",
        reply_markup={"inline_keyboard": [buttons[i:i + 2] for i in range(0, len(buttons), 2)]})


def handle_callback(query, api, doom):
    api("answerCallbackQuery", callback_query_id=query["id"])
    chat = query.get("message", {}).get("chat", {})
    if chat.get("type") != "private" or chat["id"] != query["from"]["id"]:
        return
    action = query.get("data", "")
    if action == "catalog" or action.startswith("open:"):
        text = "/start" if action == "catalog" else "/start " + action[5:]
        handle({"chat": chat, "from": query["from"], "text": text}, api, doom)


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

    doom = None
    if os.environ.get("DOOM_WIDGET_DIR"):
        sys.path.insert(0, os.environ["DOOM_WIDGET_DIR"])
        from widget_game import DoomWidget
        doom = DoomWidget(os.environ["DOOM_WAD"])
    updates = ["message", "callback_query"]
    if doom:
        updates.append("widget_query")
    offset = 0
    while True:
        try:
            if doom:
                doom.expire()
            for update in api("getUpdates", timeout=25, offset=offset, allowed_updates=updates):
                try:
                    if "message" in update:
                        handle(update["message"], api, doom)
                    elif "callback_query" in update:
                        handle_callback(update["callback_query"], api, doom)
                    elif doom and "widget_query" in update:
                        doom.answer(api, update["widget_query"])
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

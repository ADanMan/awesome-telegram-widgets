"""Run AwesomeWidgetBot with Python 3 and a token from BotFather."""
import json
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent
REPO = "https://github.com/ADanMan/awesome-telegram-widgets"
LAB = "https://github.com/VyacheslavTeplyakov/telegram-widget-lab"
@dataclass(frozen=True)
class Widget:
    title: str
    category: str
    keywords: str
    description: str
    original: str


CATEGORIES = {"games": ("Games", "Игры"), "tools": ("Tools", "Инструменты")}
PAGE_SIZE = 6
WIDGETS = {
    "doom": Widget("Doom Message", "games", "дум шутер shooter hangar", "Play E1M1 in the chat.", "https://github.com/ADanMan/telegram-doom-widget"),
    "pacman": Widget("Pacman", "games", "pac-man пакман пакмен аркада лабиринт maze arcade", "Collect dots with the arrow buttons. Avoid the ghost.", "https://github.com/ronakserry/pacman"),
    "calculator": Widget("Calculator", "tools", "калькулятор расчёт арифметика maths", "Tap the keypad to calculate. Clear starts a new calculation.", "https://github.com/Hamedshahi5/telegram-widgets/blob/main/calculator.html"),
    "weather": Widget("Weather card", "tools", "погода прогноз осадки forecast", "Tap an hour to explore a sample forecast.", LAB + "/blob/main/examples/04-weather.html"),
    "commute": Widget("Commute picker", "tools", "маршрут дорога транспорт route travel", "Compare three fictional routes and their travel times.", LAB + "/blob/main/examples/05-commute.html"),
    "inbox": Widget("Pocket inbox", "tools", "почта письма ящик email mail", "Read three fictional emails with Previous and Next.", LAB + "/blob/main/examples/07-mail-live.html"),
}


def button(text, action):
    return {"text": text, "callback_data": action}


def menu(api, chat_id, text, rows, message_id=None):
    payload = dict(chat_id=chat_id, text=text, reply_markup={"inline_keyboard": rows})
    if message_id:
        api("editMessageText", message_id=message_id, **payload)
    else:
        api("sendMessage", **payload)


def show_catalog(api, chat_id, ru, message_id=None):
    categories = [button(labels[ru], "category:" + key + ":0") for key, labels in CATEGORIES.items()]
    menu(api, chat_id, "Каталог виджетов" if ru else "Widget catalog",
         [categories, [button("Поиск" if ru else "Search", "search")]], message_id)


def normalize(text):
    return text.casefold().replace("ё", "е")


def results(api, chat_id, ru, category=None, query="", page=0, message_id=None):
    words = normalize(query).split()
    matches = []
    for slug, widget in WIDGETS.items():
        if category and category != widget.category:
            continue
        terms = normalize(" ".join((slug, widget.title, widget.keywords, *CATEGORIES[widget.category])))
        if all(word in terms for word in words):
            matches.append(button(widget.title, "open:" + slug))
    pages = max(1, (len(matches) + PAGE_SIZE - 1) // PAGE_SIZE)
    page = min(max(0, page), pages - 1)
    visible = matches[page * PAGE_SIZE:(page + 1) * PAGE_SIZE]
    rows = [visible[i:i + 2] for i in range(0, len(visible), 2)]
    prefix = "category:" + category + ":" if category else "results:"
    arrows = []
    if page:
        arrows.append(button("‹ Назад" if ru else "‹ Previous", prefix + str(page - 1)))
    if page + 1 < pages:
        arrows.append(button("Далее ›" if ru else "Next ›", prefix + str(page + 1)))
    if arrows:
        rows.append(arrows)
    rows.append([button("Категории" if ru else "Categories", "home"), button("Поиск" if ru else "Search", "search")])
    title = CATEGORIES[category][ru] if category else (("Поиск" if ru else "Search") + " · " + query)
    status = (("Страница" if ru else "Page") + f" {page + 1}/{pages}") if matches else (
        "Ничего не найдено. Попробуйте другое слово." if ru else "No matches. Try another word.")
    menu(api, chat_id, title + "\n" + status, rows, message_id)


def handle(message, api, doom=None):
    chat = message["chat"]
    if chat["type"] != "private" or not message.get("text"):
        return
    name = message["text"].strip()
    russian = (message.get("from", {}).get("language_code") or "").lower().startswith("ru")
    parts = name.split(maxsplit=1)
    if not parts:
        return
    if parts[0] == "/start":
        slug = parts[1] if len(parts) > 1 else ""
        if slug not in WIDGETS:
            show_catalog(api, chat["id"], russian)
            return
    else:
        slug = next((key for key, widget in WIDGETS.items() if name == widget.title), None)
        if slug is None:
            results(api, chat["id"], russian, query=" ".join(name.split())[:256])
            return
    widget = WIDGETS[slug]
    more = button("Ещё виджеты" if russian else "More widgets", "catalog")

    def navigation(original_url):
        original = {"text": "Оригинал" if russian else "Original project", "url": original_url}
        return {"inline_keyboard": [[more, original]]}

    if slug == "doom":
        markup = navigation(widget.original)
        if doom is not None:
            doom.send(api, chat["id"], reply_markup=markup)
            return
        markup["inline_keyboard"].insert(0, [{"text": "Play Doom", "url": "https://t.me/ADanManDoomMessageBot?start=hangar"}])
        api("sendMessage", chat_id=chat["id"], text="Play E1M1 inside the Doom Message bot.", reply_markup=markup)
        return
    path = ROOT / "widgets" / (slug + ".html")
    api("sendWidget", chat_id=chat["id"], html=path.read_text(), caption=widget.description,
        reply_markup=navigation(widget.original))


def handle_callback(query, api, doom):
    api("answerCallbackQuery", callback_query_id=query["id"])
    chat = query.get("message", {}).get("chat", {})
    if chat.get("type") != "private" or chat["id"] != query["from"]["id"]:
        return
    action = query.get("data", "")
    ru = (query["from"].get("language_code") or "").lower().startswith("ru")
    message = query["message"]
    if action.startswith("open:"):
        handle({"chat": chat, "from": query["from"], "text": "/start " + action[5:]}, api, doom)
    elif action in ("catalog", "home"):
        show_catalog(api, chat["id"], ru, message["message_id"] if action == "home" else None)
    elif action == "search":
        prompt = "Напишите название или тему, например «погода»." if ru else "Send a name or topic, for example ‘weather’."
        menu(api, chat["id"], prompt, [[button("Категории" if ru else "Categories", "home")]], message["message_id"])
    else:
        parts = action.split(":")
        if len(parts) == 3 and parts[0] == "category" and parts[1] in CATEGORIES and parts[2].isdigit():
            results(api, chat["id"], ru, category=parts[1], page=int(parts[2]), message_id=message["message_id"])
        elif len(parts) == 2 and parts[0] == "results" and parts[1].isdigit():
            # The original query stays in the heading, even after a bot restart.
            heading = message.get("text", "").splitlines()[0]
            _, separator, term = heading.partition(" · ")
            if separator:
                results(api, chat["id"], ru, query=term, page=int(parts[1]), message_id=message["message_id"])


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

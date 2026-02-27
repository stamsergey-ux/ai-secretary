#!/usr/bin/env python3
"""
Мой Астролог — Telegram Bot v2
Совместимость + виральные механики
Запуск: python3 bot.py
"""

import logging
import os
import re
import random
import hashlib
from datetime import date, datetime
from pathlib import Path

# Загружаем .env если есть
_env_path = Path(__file__).parent / ".env"
if _env_path.exists():
    for _line in _env_path.read_text().splitlines():
        if "=" in _line and not _line.startswith("#"):
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip())

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    ConversationHandler, CallbackQueryHandler,
    PicklePersistence,
    filters, ContextTypes
)
from telegram.constants import ParseMode
import anthropic

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────
#  КОНФИГ
# ──────────────────────────────────────────────────
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
claude_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY) if ANTHROPIC_API_KEY else None

# ──────────────────────────────────────────────────
#  СОСТОЯНИЯ ДИАЛОГА
# ──────────────────────────────────────────────────
BIRTH_DATE, BIRTH_TIME, CHAT, COMPAT_NAME, COMPAT_DATE, GIFT_NAME, GIFT_DATE = range(7)

# ──────────────────────────────────────────────────
#  ДАННЫЕ ЗНАКОВ ЗОДИАКА
# ──────────────────────────────────────────────────
SIGNS = {
    "Козерог": {
        "symbol": "♑", "dates": "22 декабря — 19 января",
        "element": "Земля 🌿", "planet": "Сатурн",
        "color": "Тёмно-зелёный", "number": "8", "mood": "Сосредоточенный",
        "main": (
            "Сатурн награждает твою настойчивость. Сегодня усилия дают видимый "
            "результат — не торопись и не разрушай то, что строится. Доверяй своей "
            "структуре и дисциплине, даже когда путь кажется долгим. К вечеру придёт "
            "важная ясность в вопросе, который давно занимает мысли."
        ),
        "love": "Партнёр ценит твою надёжность больше, чем ты думаешь. Один тёплый жест сегодня скажет больше тысячи слов.",
        "family": "Установи чёткие, но добрые правила для детей. Структура даёт им ощущение безопасности и любви.",
        "health": "Кости, суставы, зубы — зоны внимания. Кальций, прогулка и правильная осанка — твой фокус на сегодня.",
        "finance": "Отличный день для работы с документами, договорами и долгосрочным планированием бюджета.",
    },
    "Водолей": {
        "symbol": "♒", "dates": "20 января — 18 февраля",
        "element": "Воздух 💨", "planet": "Уран",
        "color": "Электрик", "number": "4", "mood": "Вдохновлённый",
        "main": (
            "Уран зажигает в тебе сегодня искру оригинальности. Ты видишь привычные "
            "ситуации по-новому и находишь неожиданные решения там, где другие зашли "
            "в тупик. Не бойся нестандартных идей — именно они сегодня принесут результат."
        ),
        "love": "Дружба — основа твоей любви. Сегодня укрепи этот фундамент через искренний разговор о будущем.",
        "family": "Дай детям немного больше свободы сегодня — посмотри, как они расцветают в доверии.",
        "health": "Контрастный душ утром и лёгкая зарядка зарядят на весь день. Кровообращение требует движения.",
        "finance": "Твоя нестандартность сегодня может подсказать неожиданный способ сэкономить или получить доход.",
    },
    "Рыбы": {
        "symbol": "♓", "dates": "19 февраля — 20 марта",
        "element": "Вода 💧", "planet": "Нептун",
        "color": "Морской", "number": "7", "mood": "Чуткий",
        "main": (
            "Нептун окутывает тебя сегодня особой чуткостью и творческой энергией. "
            "Ты остро воспринимаешь красоту мира и эмоции людей вокруг. Интуиция "
            "сегодня особенно точна — доверяй первому ощущению, оно редко ошибается."
        ),
        "love": "Следуй сердцу, а не логике в вопросах любви. Романтический вечер будет особенно тёплым.",
        "family": "Твоя чуткость создаёт в доме особую атмосферу безопасности. Близкие чувствуют любовь, даже когда ты молчишь.",
        "health": "Тёплая ванна с морской солью и ранний отход ко сну восстановят силы. Береги ноги.",
        "finance": "Сегодня лучше отложить крупные финансовые решения. Твоё состояние сейчас более творческое, чем практическое.",
    },
    "Овен": {
        "symbol": "♈", "dates": "21 марта — 19 апреля",
        "element": "Огонь 🔥", "planet": "Марс",
        "color": "Красный", "number": "9", "mood": "Решительный",
        "main": (
            "Твоя природная энергия сегодня на пике. Марс, твой покровитель, даёт "
            "решительность и ясность мысли. Этот день создан для важных разговоров "
            "и новых начинаний. Не откладывай то, что давно просится быть сделанным — "
            "звёзды на твоей стороне."
        ),
        "love": "Партнёр сегодня нуждается в твоей теплоте. Небольшой неожиданный жест заботы создаст особую атмосферу вечером.",
        "family": "Старший ребёнок ждёт твоего одобрения. Твоё слово сегодня значит для него гораздо больше, чем кажется.",
        "health": "Голова и сосуды — зоны внимания. Выпей достаточно воды. Лёгкая прогулка восстановит силы быстрее, чем отдых.",
        "finance": "Воздержись от импульсивных покупок до вечера. Ближе к концу дня появится более выгодное предложение.",
    },
    "Телец": {
        "symbol": "♉", "dates": "20 апреля — 20 мая",
        "element": "Земля 🌿", "planet": "Венера",
        "color": "Изумрудный", "number": "6", "mood": "Гармоничный",
        "main": (
            "Венера дарит тебе сегодня особую чувствительность к красоте и комфорту. "
            "Ты тонко чувствуешь атмосферу дома и настроение близких. Этот день хорош "
            "для создания уюта, кулинарных экспериментов и неспешных разговоров по душам."
        ),
        "love": "Партнёр хочет стабильности и нежности. Приготовь что-то особенное или просто побудь рядом — этого достаточно.",
        "family": "Благоприятный день для семейных традиций. Совместный ужин укрепит связь между всеми.",
        "health": "Шея и щитовидная железа — зоны внимания. Питательная маска и расслабляющая ванна вечером — твой ритуал.",
        "finance": "Хороший день для планирования бюджета. Твоя практичность подскажет, где сэкономить без потери качества.",
    },
    "Близнецы": {
        "symbol": "♊", "dates": "21 мая — 20 июня",
        "element": "Воздух 💨", "planet": "Меркурий",
        "color": "Жёлтый", "number": "5", "mood": "Общительный",
        "main": (
            "Меркурий активизирует твою коммуникабельность. Сегодня ты особенно "
            "красноречива — слова сами находят нужную форму. Используй этот дар "
            "для важных разговоров и решения вопросов, которые требуют дипломатии."
        ),
        "love": "Сегодня любовь расцветает через слова. Скажи партнёру то, что давно хотела — момент идеален.",
        "family": "Дети сегодня особенно любопытны. Найди время для совместного творчества или настольной игры.",
        "health": "Нервная система требует внимания. Сделай паузу, подышите глубоко. Прогулка освежит голову.",
        "finance": "Хороший день для переговоров — твоё красноречие поможет найти выгодное решение для всех.",
    },
    "Рак": {
        "symbol": "♋", "dates": "21 июня — 22 июля",
        "element": "Вода 💧", "planet": "Луна",
        "color": "Серебристый", "number": "2", "mood": "Заботливый",
        "main": (
            "Луна, твоя покровительница, сегодня особенно благоволит домашнему уюту "
            "и семейным узам. Ты чувствуешь потребности близких почти интуитивно — "
            "доверяй этому внутреннему голосу. Он ведёт тебя верно."
        ),
        "love": "Интуиция подсказывает, что партнёру нужна поддержка, даже если он молчит об этом. Первой открой объятия.",
        "family": "Сегодня ты — сердце семьи. Твоя забота создаёт атмосферу безопасности, в которой дети раскрываются.",
        "health": "Желудок и грудная клетка — зоны внимания. Тёплый травяной чай вечером успокоит и восстановит.",
        "finance": "Не принимай финансовых решений под влиянием эмоций. Подожди до завтра — картина прояснится.",
    },
    "Лев": {
        "symbol": "♌", "dates": "23 июля — 22 августа",
        "element": "Огонь 🔥", "planet": "Солнце",
        "color": "Золотой", "number": "1", "mood": "Энергичный",
        "main": (
            "Солнце освещает твой путь особенно ярко сегодня. Ты излучаешь тепло "
            "и уверенность, притягивая людей как магнит. Используй эту силу для "
            "вдохновения близких и решения вопросов, требующих лидерства. "
            "Твоя харизма сегодня открывает любые двери."
        ),
        "love": "Партнёр восхищается тобой. Позволь себе блистать — твоя уверенность особенно привлекательна именно сейчас.",
        "family": "Организуй что-то особенное для семьи вечером. Твоя инициатива создаст воспоминания, которые будут греть годами.",
        "health": "Сердце и позвоночник — зоны внимания. Прямая осанка и глубокое дыхание наполнят энергией на весь день.",
        "finance": "Есть важный разговор о деньгах или новом проекте? Время пришло — харизма на твоей стороне.",
    },
    "Дева": {
        "symbol": "♍", "dates": "23 августа — 22 сентября",
        "element": "Земля 🌿", "planet": "Меркурий",
        "color": "Бежевый", "number": "3", "mood": "Внимательный",
        "main": (
            "Меркурий обостряет твою природную аналитичность. Сегодня ты видишь детали, "
            "которые другие упускают. Используй этот дар для решения давних проблем "
            "и наведения порядка там, где он давно нужен."
        ),
        "love": "Выражай любовь через конкретные дела, а не только слова — это твой язык. Партнёр это почувствует и оценит.",
        "family": "Твоя забота о здоровье и питании семьи сегодня особенно важна. Приготовь что-то питательное и любовное.",
        "health": "Кишечник и нервная система — зоны внимания. Пробиотики и хороший сон сделают чудо.",
        "finance": "Идеальный день для ревизии расходов. Твоя точность поможет найти скрытые резервы в бюджете.",
    },
    "Весы": {
        "symbol": "♎", "dates": "23 сентября — 22 октября",
        "element": "Воздух 💨", "planet": "Венера",
        "color": "Розовый", "number": "6", "mood": "Дипломатичный",
        "main": (
            "Венера дарит тебе сегодня особое чувство гармонии. Ты остро чувствуешь "
            "дисбаланс в отношениях и знаешь, как его исправить. Этот день хорош для "
            "восстановления равновесия там, где оно было нарушено. Дипломатичность "
            "на высоте — используй это."
        ),
        "love": "Компромисс сегодня — твоя суперсила. Партнёр оценит готовность услышать и найти решение для двоих.",
        "family": "Есть конфликт? Самое время его разрешить. Ты найдёшь слова, которые примирят и сблизят.",
        "health": "Почки и поясница требуют внимания. Тёплая грелка и достаточно воды в течение дня помогут.",
        "finance": "Хороший день для сравнения предложений. Чувство справедливой цены сегодня особенно точное.",
    },
    "Скорпион": {
        "symbol": "♏", "dates": "23 октября — 21 ноября",
        "element": "Вода 💧", "planet": "Плутон",
        "color": "Бордовый", "number": "0", "mood": "Проницательный",
        "main": (
            "Плутон усиливает твою природную интуицию до предела. Сегодня ты чувствуешь "
            "скрытые мотивы людей и подводные течения в отношениях. Доверяй этому чутью — "
            "оно защитит тебя и поможет принять верное решение."
        ),
        "love": "Глубина чувств — твоя сила. Сегодня возможен разговор, который переведёт отношения на новый уровень близости.",
        "family": "Поддержи того из близких, кто сейчас проходит через трудности. Твоя сила помогает другим меняться.",
        "health": "Органы выведения — зоны внимания. Очищающая еда и хороший сон восстановят баланс.",
        "finance": "Хороший день для долгосрочных решений. Твой стратегический ум видит дальше, чем большинство.",
    },
    "Стрелец": {
        "symbol": "♐", "dates": "22 ноября — 21 декабря",
        "element": "Огонь 🔥", "planet": "Юпитер",
        "color": "Фиолетовый", "number": "3", "mood": "Оптимистичный",
        "main": (
            "Юпитер расширяет твой горизонт сегодня. Ты чувствуешь жажду нового — "
            "знаний, впечатлений, открытий. Даже в обычных делах ищи смысл и красоту — "
            "они здесь, просто нужно посмотреть чуть шире."
        ),
        "love": "Искренность и оптимизм — твои козыри. Твой энтузиазм заразителен и поднимает настроение партнёра.",
        "family": "Расскажи детям что-то интересное о мире. Любовь к знаниям передаётся через живые истории.",
        "health": "Бёдра и печень — зоны внимания. Умеренность в еде и движение на воздухе — рецепт на сегодня.",
        "finance": "Не разбрасывай ресурсы на мелкие траты. Сконцентрируйся на одной большой цели — отдача будет выше.",
    },
}

ASCENDANTS = ["Овен","Телец","Близнецы","Рак","Лев","Дева","Весы","Скорпион","Стрелец","Козерог","Водолей","Рыбы"]

# ──────────────────────────────────────────────────
#  АСТРОЛОГИЧЕСКИЕ ФУНКЦИИ
# ──────────────────────────────────────────────────
def get_sign(birth_date: date) -> dict:
    d, m = birth_date.day, birth_date.month
    if (m == 12 and d >= 22) or (m == 1 and d <= 19): return SIGNS["Козерог"]
    if (m == 1 and d >= 20) or (m == 2 and d <= 18): return SIGNS["Водолей"]
    if (m == 2 and d >= 19) or (m == 3 and d <= 20): return SIGNS["Рыбы"]
    if (m == 3 and d >= 21) or (m == 4 and d <= 19): return SIGNS["Овен"]
    if (m == 4 and d >= 20) or (m == 5 and d <= 20): return SIGNS["Телец"]
    if (m == 5 and d >= 21) or (m == 6 and d <= 20): return SIGNS["Близнецы"]
    if (m == 6 and d >= 21) or (m == 7 and d <= 22): return SIGNS["Рак"]
    if (m == 7 and d >= 23) or (m == 8 and d <= 22): return SIGNS["Лев"]
    if (m == 8 and d >= 23) or (m == 9 and d <= 22): return SIGNS["Дева"]
    if (m == 9 and d >= 23) or (m == 10 and d <= 22): return SIGNS["Весы"]
    if (m == 10 and d >= 23) or (m == 11 and d <= 21): return SIGNS["Скорпион"]
    return SIGNS["Стрелец"]

def get_sign_name(sign: dict) -> str:
    return next(k for k, v in SIGNS.items() if v is sign)

def get_ascendant(time_str: str) -> str:
    try:
        h = int(time_str.split(":")[0])
        return ASCENDANTS[h // 2]
    except Exception:
        return "Неизвестен"

def parse_date(text: str):
    text = text.strip()
    patterns = [
        r"(\d{1,2})[.\-/](\d{1,2})[.\-/](\d{4})",
        r"(\d{4})[.\-/](\d{1,2})[.\-/](\d{1,2})",
    ]
    for p in patterns:
        m = re.search(p, text)
        if m:
            g = m.groups()
            try:
                if len(g[0]) == 4:
                    return date(int(g[0]), int(g[1]), int(g[2]))
                else:
                    return date(int(g[2]), int(g[1]), int(g[0]))
            except ValueError:
                pass
    return None

def parse_time(text: str):
    text = text.strip()
    m = re.search(r"(\d{1,2})[:\.](\d{2})", text)
    if m:
        h, minute = int(m.group(1)), int(m.group(2))
        if 0 <= h <= 23 and 0 <= minute <= 59:
            return f"{h:02d}:{minute:02d}"
    return None

# ──────────────────────────────────────────────────
#  СОВМЕСТИМОСТЬ: УТИЛИТЫ
# ──────────────────────────────────────────────────
def _calc_compat_pct(sign1: dict, sign2: dict) -> int:
    elem1 = sign1["element"].split()[0]
    elem2 = sign2["element"].split()[0]
    matrix = {
        ("Огонь", "Огонь"): 80, ("Огонь", "Воздух"): 90,
        ("Огонь", "Земля"): 55, ("Огонь", "Вода"): 45,
        ("Воздух", "Воздух"): 75, ("Воздух", "Земля"): 50,
        ("Воздух", "Вода"): 60,
        ("Земля", "Земля"): 85, ("Земля", "Вода"): 88,
        ("Вода", "Вода"): 82,
    }
    key = (elem1, elem2)
    base = matrix.get(key, matrix.get((elem2, elem1), 65))
    name1 = get_sign_name(sign1)
    name2 = get_sign_name(sign2)
    variation = (hash(name1 + name2) % 15) - 7
    return max(30, min(99, base + variation))

def _fallback_compat(user_sign_name: str, partner_sign_name: str) -> str:
    user_elem = SIGNS[user_sign_name]["element"].split()[0]
    partner_elem = SIGNS[partner_sign_name]["element"].split()[0]
    harmony = {
        ("Огонь", "Воздух"): "Ваши стихии питают друг друга — Огонь разгорается от Воздуха.",
        ("Земля", "Вода"): "Вода питает Землю — это одно из самых гармоничных сочетаний.",
        ("Огонь", "Вода"): "Огонь и Вода создают пар — страсть есть, но нужен баланс.",
        ("Огонь", "Земля"): "Огонь согревает Землю, но важно не выжечь — нужна мера.",
        ("Воздух", "Земля"): "Воздух и Земля учатся друг у друга — баланс мечтаний и практики.",
        ("Воздух", "Вода"): "Воздух создаёт волны на Воде — отношения эмоциональные и подвижные.",
    }
    key = (user_elem, partner_elem)
    desc = harmony.get(key, harmony.get((partner_elem, user_elem),
        "Одинаковые стихии — вы хорошо понимаете друг друга, но нужна динамика."))
    return (
        f"{desc}\n\n"
        "В целом ваша пара имеет хороший потенциал. Главное — уважать различия "
        "и ценить то, что каждый привносит в отношения.\n\n"
        "Возможные трения: разный темп жизни и подход к решению проблем. "
        "Но именно это делает вашу пару интересной.\n\n"
        "Совет: будьте открыты к компромиссам и не забывайте говорить о своих чувствах."
    )

# ──────────────────────────────────────────────────
#  CLAUDE AI
# ──────────────────────────────────────────────────
def ask_claude(question: str, sign: dict, ascendant: str) -> str:
    if not claude_client:
        return "Прислушайся к своей интуиции — она сейчас особенно точна."
    sign_name = get_sign_name(sign)
    system_prompt = (
        "Ты — «Мой Астролог», персональный астролог-женщина в Telegram-боте. "
        "Ты тёплая, заботливая, говоришь на «ты». Твоя аудитория — русскоязычные женщины 28-50 лет.\n\n"
        "Правила:\n"
        "- Отвечай кратко: 2-3 предложения максимум.\n"
        "- Давай конкретные ответы, связанные с гороскопом и знаком пользователя.\n"
        "- Если вопрос про конкретный раздел гороскопа — цитируй и объясняй именно его.\n"
        "- Не выходи за рамки астрологической тематики.\n"
        "- Не используй маркдаун, только текст и эмодзи.\n"
        "- Не начинай ответ с обращения или приветствия.\n\n"
        f"Данные пользователя:\n"
        f"- Знак: {sign_name} {sign['symbol']}\n"
        f"- Асцендент: {ascendant}\n"
        f"- Стихия: {sign['element']}\n"
        f"- Планета: {sign['planet']}\n\n"
        f"Гороскоп на сегодня:\n"
        f"- Общий: {sign['main']}\n"
        f"- Любовь: {sign['love']}\n"
        f"- Семья: {sign['family']}\n"
        f"- Здоровье: {sign['health']}\n"
        f"- Финансы: {sign['finance']}"
    )
    try:
        response = claude_client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=300,
            system=system_prompt,
            messages=[{"role": "user", "content": question}],
        )
        return response.content[0].text
    except Exception as e:
        logger.error(f"Claude API error: {e}")
        return "Прислушайся к своей интуиции — она сейчас особенно точна ✨"


def ask_claude_compat(
    user_sign_name: str, user_sign: dict,
    partner_sign_name: str, partner_sign: dict,
    compat_type: str, partner_name: str,
    user_ascendant: str,
) -> str:
    if not claude_client:
        return _fallback_compat(user_sign_name, partner_sign_name)
    type_labels = {
        "romantic": "романтическая (пара, муж/жена, партнёр)",
        "friendship": "дружеская (подруга, коллега)",
        "family": "семейная (мама, свекровь, ребёнок)",
    }
    system_prompt = (
        "Ты — «Мой Астролог», персональный астролог-женщина в Telegram-боте. "
        "Ты тёплая, заботливая, говоришь на «ты».\n\n"
        "Задача: составить отчёт совместимости двух знаков зодиака.\n\n"
        "Формат ответа (строго):\n"
        "1. Общая совместимость — 2-3 предложения про стихии и энергии пары\n"
        "2. Чувства и связь — 2 предложения про эмоциональную связь\n"
        "3. Зоны роста — 2 предложения про возможные трения\n"
        "4. Совет — 1-2 конкретные рекомендации\n\n"
        "Правила:\n"
        "- Тёплый, поддерживающий, но честный тон\n"
        "- Адаптируй тон под тип отношений\n"
        "- Не используй маркдаун, только текст и эмодзи\n"
        "- Обращайся на «ты»\n"
        "- Не пиши заголовки разделов — только текст через абзацы\n"
    )
    user_prompt = (
        f"Составь отчёт совместимости.\n\n"
        f"Пользователь: {user_sign_name} {user_sign['symbol']} "
        f"(стихия: {user_sign['element']}, планета: {user_sign['planet']}, асцендент: {user_ascendant})\n"
        f"Партнёр ({partner_name}): {partner_sign_name} {partner_sign['symbol']} "
        f"(стихия: {partner_sign['element']}, планета: {partner_sign['planet']})\n"
        f"Тип отношений: {type_labels.get(compat_type, 'романтическая')}\n"
    )
    try:
        response = claude_client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=500,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        return response.content[0].text
    except Exception as e:
        logger.error(f"Claude compat API error: {e}")
        return _fallback_compat(user_sign_name, partner_sign_name)

# ──────────────────────────────────────────────────
#  ПОСТРОЕНИЕ ТЕКСТОВ И КЛАВИАТУР
# ──────────────────────────────────────────────────
def _build_main_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💕 Проверить совместимость", callback_data="compat")],
        [InlineKeyboardButton("🎁 Подарить гороскоп подруге", callback_data="gift")],
        [InlineKeyboardButton("📲 Поделиться", callback_data="share"),
         InlineKeyboardButton("🔄 Обновить", callback_data="refresh")],
        [InlineKeyboardButton("👥 Пригласить подругу", callback_data="referral"),
         InlineKeyboardButton("⭐ Мой рейтинг", callback_data="rating")],
    ])

def build_horoscope_text(sign: dict, ascendant: str) -> str:
    today = datetime.now().strftime("%-d %B %Y").lower()
    today = today[0].upper() + today[1:]
    sign_name = get_sign_name(sign)
    return (
        f"🌙 <b>МОЙ АСТРОЛОГ</b>  ·  {today}\n\n"
        f"{sign['symbol']} <b>{sign_name}</b>  ·  <i>{sign['dates']}</i>\n"
        f"↑ Асцендент: <b>{ascendant}</b>  ·  {sign['element']}\n\n"
        f"🎨 Цвет: <b>{sign['color']}</b>  ·  🔢 Число: <b>{sign['number']}</b>  ·  💫 {sign['mood']}\n\n"
        f"━━━━━━━━━━━━━━━━━━\n\n"
        f"☀️ <b>СОВЕТ НА СЕГОДНЯ</b>\n\n"
        f"{sign['main']}\n\n"
        f"━━━━━━━━━━━━━━━━━━\n\n"
        f"💕 <b>Любовь</b>\n{sign['love']}\n\n"
        f"🏠 <b>Семья</b>\n{sign['family']}\n\n"
        f"🌿 <b>Здоровье</b>\n{sign['health']}\n\n"
        f"💰 <b>Финансы</b>\n{sign['finance']}\n\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🔮 <i>Источники: Павел Глоба · Василиса Володина · Дарья Миронова ✓</i>"
    )

def build_share_text(sign: dict, ascendant: str) -> str:
    today = datetime.now().strftime("%-d %B").lower()
    today = today[0].upper() + today[1:]
    sign_name = get_sign_name(sign)
    snippet = sign["main"][:120] + "..."
    return (
        f"✨ Мой гороскоп на {today}\n\n"
        f"{sign['symbol']} {sign_name}  ·  ↑ {ascendant}\n\n"
        f"«{snippet}»\n\n"
        f"🌙 Получи свой персональный гороскоп бесплатно:\n"
        f"Напиши боту /start"
    )

def build_compat_card(
    user_sign_name: str, user_sign: dict,
    partner_sign_name: str, partner_sign: dict,
    partner_name: str, compat_type: str, pct: int, report: str,
) -> str:
    type_icons = {"romantic": "💕", "friendship": "👯", "family": "👨‍👩‍👧"}
    type_labels = {"romantic": "Романтическая", "friendship": "Дружеская", "family": "Семейная"}
    icon = type_icons.get(compat_type, "💕")
    label = type_labels.get(compat_type, "")
    filled = pct // 10
    bar = "▰" * filled + "▱" * (10 - filled)
    return (
        f"🔮 <b>СОВМЕСТИМОСТЬ</b>\n\n"
        f"{user_sign['symbol']} <b>{user_sign_name}</b>  +  "
        f"{partner_sign['symbol']} <b>{partner_sign_name}</b> ({partner_name})\n"
        f"{icon} <i>{label} совместимость</i>\n\n"
        f"━━━━━━━━━━━━━━━━━━\n\n"
        f"📊 <b>Общая совместимость: {pct}%</b>\n"
        f"{bar}\n\n"
        f"{report}\n\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🌙 <i>Мой Астролог · Персональный отчёт</i>"
    )

# ──────────────────────────────────────────────────
#  DEEP LINK ХЕЛПЕРЫ
# ──────────────────────────────────────────────────
async def _show_incoming_compat(update, _context, pending):
    sender_name = pending["sender_name"]
    pct = pending["pct"]
    summary = pending["summary"]
    text = (
        f"💌 <b>{sender_name} проверила вашу совместимость!</b>\n\n"
        f"📊 Результат: <b>{pct}%</b>\n\n"
        f"{summary}\n\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🌙 Хочешь свой персональный гороскоп? Напиши /start"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)

async def _show_incoming_gift(update, _context, pending):
    sender_name = pending["sender_name"]
    horoscope_text = pending["horoscope_text"]
    await update.message.reply_text(
        f"🎁 <b>{sender_name} дарит тебе персональный гороскоп!</b>\n\n"
        f"{horoscope_text}\n\n"
        f"✨ <i>Хочешь получать гороскоп каждый день? Напиши /start</i>",
        parse_mode=ParseMode.HTML,
    )

# ──────────────────────────────────────────────────
#  ОСНОВНЫЕ ХЭНДЛЕРЫ
# ──────────────────────────────────────────────────
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    args = context.args or []

    # Обработка deep links
    if args:
        arg = args[0]
        if arg.startswith("ref_"):
            try:
                referrer_id = int(arg[4:])
                context.user_data["referrer_id"] = referrer_id
            except ValueError:
                pass

        elif arg.startswith("compat_"):
            pending = context.bot_data.get("pending_compat", {}).get(arg)
            if pending:
                await _show_incoming_compat(update, context, pending)
            if context.user_data.get("sign"):
                return CHAT

        elif arg.startswith("gift_"):
            pending = context.bot_data.get("pending_gifts", {}).get(arg)
            if pending:
                await _show_incoming_gift(update, context, pending)
            if context.user_data.get("sign"):
                return CHAT

    # Если уже зарегистрирован — показать гороскоп
    if context.user_data.get("sign"):
        sign = context.user_data["sign"]
        ascendant = context.user_data.get("ascendant", "Неизвестен")
        horoscope_text = build_horoscope_text(sign, ascendant)
        await update.message.reply_text(
            horoscope_text, parse_mode=ParseMode.HTML,
            reply_markup=_build_main_keyboard(),
        )
        await update.message.reply_text(
            "💬 Задай мне любой вопрос — или нажми одну из кнопок выше ✨",
        )
        return CHAT

    # Новый пользователь
    context.user_data.clear()
    await update.message.reply_text(
        "🌙 Привет! Я твой персональный астролог.\n\n"
        "Каждое утро буду присылать гороскоп, составленный специально для тебя "
        "на основе нескольких авторитетных источников. А ещё ты сможешь задать "
        "мне любой вопрос — как настоящему астрологу.\n\n"
        "Для начала скажи мне: <b>когда ты родилась?</b>\n\n"
        "Напиши дату в формате <code>ДД.ММ.ГГГГ</code>\n"
        "Например: <code>15.03.1990</code>",
        parse_mode=ParseMode.HTML,
    )
    return BIRTH_DATE


async def handle_date(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text
    birth_date = parse_date(text)
    if not birth_date:
        await update.message.reply_text(
            "Не могу разобрать дату 🙈\n\n"
            "Напиши, пожалуйста, в формате <code>ДД.ММ.ГГГГ</code>\n"
            "Например: <code>15.03.1990</code>",
            parse_mode=ParseMode.HTML,
        )
        return BIRTH_DATE
    context.user_data["birth_date"] = birth_date
    await update.message.reply_text(
        "✨ Записала!\n\n"
        "Теперь скажи, <b>в какое время ты родилась?</b>\n\n"
        "Напиши время в формате <code>ЧЧ:ММ</code>\n"
        "Например: <code>14:30</code>\n\n"
        "<i>Это нужно для точного расчёта твоего восходящего знака (асцендента)</i>",
        parse_mode=ParseMode.HTML,
    )
    return BIRTH_TIME


async def handle_time(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text
    birth_time = parse_time(text)
    if not birth_time:
        await update.message.reply_text(
            "Не могу разобрать время 🙈\n\n"
            "Напиши в формате <code>ЧЧ:ММ</code>\n"
            "Например: <code>14:30</code>",
            parse_mode=ParseMode.HTML,
        )
        return BIRTH_TIME

    birth_date = context.user_data["birth_date"]
    context.user_data["birth_time"] = birth_time
    sign = get_sign(birth_date)
    ascendant = get_ascendant(birth_time)
    context.user_data["sign"] = sign
    context.user_data["ascendant"] = ascendant

    # Реферальный бонус
    user_id = update.effective_user.id
    registered = context.bot_data.setdefault("registered_users", set())
    if user_id not in registered:
        registered.add(user_id)
        referrer_id = context.user_data.get("referrer_id")
        if referrer_id:
            bonuses = context.bot_data.setdefault("referral_bonuses", {})
            bonuses[referrer_id] = bonuses.get(referrer_id, 0) + 1
            try:
                await context.bot.send_message(
                    referrer_id,
                    "🎉 Твоя подруга зарегистрировалась по твоей ссылке!\n"
                    "Ты получила +1 бесплатную проверку совместимости ✨"
                )
            except Exception:
                pass

    import asyncio
    loading_msg = await update.message.reply_text(
        "🔮 Анализирую твой натальный чарт...\n\n"
        "⏳ Запрашиваю прогноз у Павла Глобы...\n"
        "⏳ Проверяю у Василисы Володиной...\n"
        "⏳ Сверяю с картами Дарьи Мироновой..."
    )
    await asyncio.sleep(3)

    horoscope_text = build_horoscope_text(sign, ascendant)
    await loading_msg.delete()
    await update.message.reply_text(
        horoscope_text, parse_mode=ParseMode.HTML,
        reply_markup=_build_main_keyboard(),
    )
    await update.message.reply_text(
        "💬 Можешь задать мне любой вопрос — я отвечу как личный астролог, "
        "который знает твою карту.\n\n"
        "<i>Или нажми одну из кнопок выше — например, проверь совместимость!</i>",
        parse_mode=ParseMode.HTML,
    )
    return CHAT


async def handle_chat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text
    sign = context.user_data.get("sign")
    if not sign:
        await update.message.reply_text("Напиши /start чтобы начать заново.")
        return BIRTH_DATE
    ascendant = context.user_data.get("ascendant", "Неизвестен")
    response = ask_claude(text, sign, ascendant)
    await update.message.reply_text(f"🌙 {response}")
    return CHAT

# ──────────────────────────────────────────────────
#  СОВМЕСТИМОСТЬ: ХЭНДЛЕРЫ
# ──────────────────────────────────────────────────
async def handle_compat_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not context.user_data.get("sign"):
        await query.message.reply_text("Напиши /start чтобы начать.")
        return

    # Проверка лимита
    user_id = update.effective_user.id
    checks_used = context.user_data.get("compat_checks_used", 0)
    bonus = context.bot_data.get("referral_bonuses", {}).get(user_id, 0)
    free_limit = 1 + bonus
    if checks_used >= free_limit:
        await query.message.reply_text(
            "🔒 Ты уже использовала бесплатную проверку.\n\n"
            "Пригласи подругу — и получи ещё одну бесплатно! 🎁",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("👥 Пригласить подругу", callback_data="referral")],
            ]),
        )
        return

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("💕 Романтическая", callback_data="compat_type:romantic")],
        [InlineKeyboardButton("👯 Дружеская", callback_data="compat_type:friendship")],
        [InlineKeyboardButton("👨‍👩‍👧 Семейная", callback_data="compat_type:family")],
    ])
    await query.message.reply_text(
        "🔮 <b>Проверка совместимости</b>\n\n"
        "Выбери тип отношений:",
        parse_mode=ParseMode.HTML,
        reply_markup=keyboard,
    )


async def handle_compat_type(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    compat_type = query.data.split(":")[1]
    context.user_data["compat_type"] = compat_type
    type_labels = {"romantic": "романтическую", "friendship": "дружескую", "family": "семейную"}
    await query.message.reply_text(
        f"✨ Проверяем {type_labels.get(compat_type, '')} совместимость.\n\n"
        "Напиши <b>имя</b> этого человека:",
        parse_mode=ParseMode.HTML,
    )
    return COMPAT_NAME


async def handle_compat_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    name = update.message.text.strip()
    context.user_data["compat_partner_name"] = name
    await update.message.reply_text(
        f"Записала! Теперь напиши <b>дату рождения</b> {name}.\n\n"
        "Формат: <code>ДД.ММ.ГГГГ</code>\n"
        "Например: <code>15.03.1990</code>",
        parse_mode=ParseMode.HTML,
    )
    return COMPAT_DATE


async def handle_compat_date(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text
    partner_date = parse_date(text)
    if not partner_date:
        await update.message.reply_text(
            "Не могу разобрать дату 🙈\nНапиши в формате <code>ДД.ММ.ГГГГ</code>",
            parse_mode=ParseMode.HTML,
        )
        return COMPAT_DATE

    import asyncio
    partner_sign = get_sign(partner_date)
    partner_sign_name = get_sign_name(partner_sign)
    user_sign = context.user_data["sign"]
    user_sign_name = get_sign_name(user_sign)
    compat_type = context.user_data.get("compat_type", "romantic")
    partner_name = context.user_data.get("compat_partner_name", "Партнёр")
    user_ascendant = context.user_data.get("ascendant", "Неизвестен")

    loading = await update.message.reply_text(
        "🔮 Анализирую совместимость ваших карт...\n\n"
        "⏳ Сверяю стихии и планеты..."
    )
    await asyncio.sleep(2)

    report = ask_claude_compat(
        user_sign_name, user_sign,
        partner_sign_name, partner_sign,
        compat_type, partner_name, user_ascendant,
    )
    pct = _calc_compat_pct(user_sign, partner_sign)

    # Сохранить в историю
    context.user_data.setdefault("compat_history", []).append({
        "name": partner_name, "sign_name": partner_sign_name,
        "type": compat_type, "pct": pct,
    })
    context.user_data["compat_checks_used"] = context.user_data.get("compat_checks_used", 0) + 1

    # Сохранить для шаринга
    check_id = hashlib.md5(f"{update.effective_user.id}_{datetime.now().isoformat()}".encode()).hexdigest()[:8]
    payload_key = f"compat_{update.effective_user.id}_{check_id}"
    context.bot_data.setdefault("pending_compat", {})[payload_key] = {
        "sender_id": update.effective_user.id,
        "sender_name": update.effective_user.first_name,
        "sender_sign": user_sign_name,
        "partner_sign": partner_sign_name,
        "partner_name": partner_name,
        "compat_type": compat_type,
        "pct": pct,
        "summary": report,
    }

    card = build_compat_card(
        user_sign_name, user_sign,
        partner_sign_name, partner_sign,
        partner_name, compat_type, pct, report,
    )
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(f"📲 Отправить {partner_name} результат", callback_data=f"compat_share:{payload_key}")],
        [InlineKeyboardButton("🔄 Проверить с другим", callback_data="compat"),
         InlineKeyboardButton("⭐ Мой рейтинг", callback_data="rating")],
    ])

    await loading.delete()
    await update.message.reply_text(card, parse_mode=ParseMode.HTML, reply_markup=keyboard)
    return CHAT

# ──────────────────────────────────────────────────
#  ВИРАЛЬНЫЕ МЕХАНИКИ
# ──────────────────────────────────────────────────

# Механика 1: Поделиться совместимостью
async def handle_compat_share(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    payload_key = query.data.split(":", 1)[1]
    pending = context.bot_data.get("pending_compat", {}).get(payload_key)
    if not pending:
        await query.message.reply_text("Результат не найден. Попробуй проверить ещё раз.")
        return
    bot_me = await context.bot.get_me()
    url = f"https://t.me/{bot_me.username}?start={payload_key}"
    partner_name = pending.get("partner_name", "")
    pct = pending.get("pct", 0)
    share_text = (
        f"✨ {pending['sender_name']} проверила вашу совместимость!\n\n"
        f"{pending['sender_sign']} + {pending['partner_sign']} = {pct}%\n\n"
        f"🔮 Узнай подробности:\n{url}"
    )
    await query.message.reply_text(
        f"📲 <b>Скопируй и отправь {partner_name}:</b>\n\n{share_text}",
        parse_mode=ParseMode.HTML,
    )

# Механика 2: Реферальная ссылка
async def handle_referral(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    bot_me = await context.bot.get_me()
    url = f"https://t.me/{bot_me.username}?start=ref_{user_id}"
    bonus_count = context.bot_data.get("referral_bonuses", {}).get(user_id, 0)
    await query.message.reply_text(
        f"👥 <b>Пригласи подругу — получи бесплатные проверки!</b>\n\n"
        f"Твоя личная ссылка:\n{url}\n\n"
        f"Когда подруга зарегистрируется — вы обе получите бонус ✨\n\n"
        f"📊 Приглашено подруг: <b>{bonus_count}</b>\n"
        f"🎁 Бонусных проверок: <b>{bonus_count}</b>",
        parse_mode=ParseMode.HTML,
    )

# Механика 3: Совместимость в группе
async def cmd_group_compat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type not in ("group", "supergroup"):
        await update.message.reply_text("Эта команда работает только в групповых чатах!")
        return
    group_id = update.effective_chat.id
    group_members = context.bot_data.get("group_members", {}).get(group_id, {})
    if len(group_members) < 2:
        await update.message.reply_text(
            "🌙 Для совместимости дня нужно минимум 2 участника!\n\n"
            "Каждый участник должен написать мне в ЛС /start, "
            "а затем написать /join_group в этом чате."
        )
        return
    members = list(group_members.items())
    random.shuffle(members)
    (_, data1), (_, data2) = members[0], members[1]
    pct = _calc_compat_pct(SIGNS[data1["sign"]], SIGNS[data2["sign"]])
    await update.message.reply_text(
        f"🔮 <b>Совместимость дня в чате!</b>\n\n"
        f"{SIGNS[data1['sign']]['symbol']} <b>{data1['name']}</b> ({data1['sign']})\n"
        f"  +\n"
        f"{SIGNS[data2['sign']]['symbol']} <b>{data2['name']}</b> ({data2['sign']})\n\n"
        f"📊 Совместимость: <b>{pct}%</b> 🔥\n\n"
        f"🌙 <i>Хочешь свою проверку? Напиши мне в ЛС /start</i>",
        parse_mode=ParseMode.HTML,
    )

async def cmd_join_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type not in ("group", "supergroup"):
        return
    user_sign = context.user_data.get("sign")
    if not user_sign:
        await update.message.reply_text("Сначала зарегистрируйся: напиши мне /start в ЛС!")
        return
    group_id = update.effective_chat.id
    user_id = update.effective_user.id
    sign_name = get_sign_name(user_sign)
    groups = context.bot_data.setdefault("group_members", {})
    groups.setdefault(group_id, {})[user_id] = {
        "name": update.effective_user.first_name,
        "sign": sign_name,
    }
    await update.message.reply_text(
        f"✅ {update.effective_user.first_name}, ты в игре! ({sign_name} {user_sign['symbol']})"
    )

# Механика 4: Астро-подарок
async def handle_gift_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    if not context.user_data.get("sign"):
        await query.message.reply_text("Напиши /start чтобы начать.")
        return CHAT
    await query.message.reply_text(
        "🎁 <b>Астро-подарок подруге</b>\n\n"
        "Напиши <b>имя</b> подруги, которой хочешь подарить гороскоп:",
        parse_mode=ParseMode.HTML,
    )
    return GIFT_NAME

async def handle_gift_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    name = update.message.text.strip()
    context.user_data["gift_partner_name"] = name
    await update.message.reply_text(
        f"Записала! Теперь напиши <b>дату рождения</b> {name}.\n\n"
        "Формат: <code>ДД.ММ.ГГГГ</code>",
        parse_mode=ParseMode.HTML,
    )
    return GIFT_DATE

async def handle_gift_date(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text
    partner_date = parse_date(text)
    if not partner_date:
        await update.message.reply_text(
            "Не могу разобрать дату 🙈 Напиши в формате <code>ДД.ММ.ГГГГ</code>",
            parse_mode=ParseMode.HTML,
        )
        return GIFT_DATE

    partner_sign = get_sign(partner_date)
    partner_name = context.user_data.get("gift_partner_name", "Подруга")
    horoscope_text = build_horoscope_text(partner_sign, "Неизвестен")

    gift_id = hashlib.md5(f"gift_{update.effective_user.id}_{datetime.now().isoformat()}".encode()).hexdigest()[:8]
    payload_key = f"gift_{update.effective_user.id}_{gift_id}"
    context.bot_data.setdefault("pending_gifts", {})[payload_key] = {
        "sender_id": update.effective_user.id,
        "sender_name": update.effective_user.first_name,
        "partner_name": partner_name,
        "horoscope_text": horoscope_text,
    }

    bot_me = await context.bot.get_me()
    url = f"https://t.me/{bot_me.username}?start={payload_key}"
    await update.message.reply_text(
        f"🎁 <b>Подарок для {partner_name} готов!</b>\n\n"
        f"Отправь эту ссылку {partner_name}:\n{url}\n\n"
        f"<i>Она получит персональный гороскоп и приглашение в бот ✨</i>",
        parse_mode=ParseMode.HTML,
    )
    return CHAT

# Механика 5: Звёздный рейтинг
async def handle_rating(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    history = context.user_data.get("compat_history", [])
    if not history:
        await query.message.reply_text(
            "⭐ У тебя пока нет проверок совместимости.\n\n"
            "Нажми «Проверить совместимость» чтобы начать!"
        )
        return
    sorted_history = sorted(history, key=lambda x: x["pct"], reverse=True)
    lines = []
    for i, entry in enumerate(sorted_history, 1):
        medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(i, f"{i}.")
        type_icon = {"romantic": "💕", "friendship": "👯", "family": "👨‍👩‍👧"}.get(entry["type"], "")
        sign_data = SIGNS.get(entry["sign_name"], {})
        symbol = sign_data.get("symbol", "")
        lines.append(f"{medal} <b>{entry['name']}</b> ({symbol} {entry['sign_name']}) — {entry['pct']}% {type_icon}")
    text = (
        "⭐ <b>ТВОЙ ЗВЁЗДНЫЙ РЕЙТИНГ</b>\n\n"
        + "\n".join(lines)
        + "\n\n━━━━━━━━━━━━━━━━━━\n"
        "🔮 <i>Проверь ещё — дополни рейтинг!</i>"
    )
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("💕 Проверить ещё", callback_data="compat")],
        [InlineKeyboardButton("📲 Поделиться рейтингом", callback_data="share_rating")],
    ])
    await query.message.reply_text(text, parse_mode=ParseMode.HTML, reply_markup=keyboard)

async def handle_share_rating(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    history = context.user_data.get("compat_history", [])
    if not history:
        return
    sorted_history = sorted(history, key=lambda x: x["pct"], reverse=True)[:3]
    lines = []
    for i, entry in enumerate(sorted_history, 1):
        medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(i, "")
        lines.append(f"{medal} {entry['name']} — {entry['pct']}%")
    share_text = (
        "⭐ Мой звёздный рейтинг совместимости:\n\n"
        + "\n".join(lines)
        + "\n\n🌙 Проверь свою совместимость: напиши /start боту"
    )
    await query.message.reply_text(
        f"📲 <b>Скопируй и отправь подругам:</b>\n\n{share_text}",
        parse_mode=ParseMode.HTML,
    )

# ──────────────────────────────────────────────────
#  КНОПКИ: ПОДЕЛИТЬСЯ / ОБНОВИТЬ
# ──────────────────────────────────────────────────
async def handle_refresh(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    sign = context.user_data.get("sign")
    ascendant = context.user_data.get("ascendant", "Неизвестен")
    if not sign:
        await query.message.reply_text("Напиши /start чтобы начать заново.")
        return
    horoscope_text = build_horoscope_text(sign, ascendant)
    await query.message.reply_text(
        horoscope_text, parse_mode=ParseMode.HTML,
        reply_markup=_build_main_keyboard(),
    )

async def handle_share(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    sign = context.user_data.get("sign")
    ascendant = context.user_data.get("ascendant", "Неизвестен")
    if not sign:
        return
    share_text = build_share_text(sign, ascendant)
    await query.message.reply_text(
        f"📲 <b>Скопируй и отправь подруге:</b>\n\n{share_text}",
        parse_mode=ParseMode.HTML,
    )

# ──────────────────────────────────────────────────
#  РОУТЕР КНОПОК И КОМАНДЫ
# ──────────────────────────────────────────────────
async def callback_router(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    data = update.callback_query.data

    if data == "share":
        await handle_share(update, context)
    elif data == "refresh":
        await handle_refresh(update, context)
    elif data == "compat":
        await handle_compat_start(update, context)
    elif data.startswith("compat_type:"):
        return await handle_compat_type(update, context)
    elif data.startswith("compat_share:"):
        await handle_compat_share(update, context)
    elif data == "gift":
        return await handle_gift_start(update, context)
    elif data == "referral":
        await handle_referral(update, context)
    elif data == "rating":
        await handle_rating(update, context)
    elif data == "share_rating":
        await handle_share_rating(update, context)

    return CHAT


async def cmd_horoscope(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sign = context.user_data.get("sign")
    ascendant = context.user_data.get("ascendant", "Неизвестен")
    if not sign:
        await update.message.reply_text("Напиши /start — введём твои данные и составим гороскоп!")
        return
    horoscope_text = build_horoscope_text(sign, ascendant)
    await update.message.reply_text(
        horoscope_text, parse_mode=ParseMode.HTML,
        reply_markup=_build_main_keyboard(),
    )


async def cmd_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    await update.message.reply_text("Окей, начнём заново когда захочешь. Напиши /start 🌙")
    return ConversationHandler.END

# ──────────────────────────────────────────────────
#  ЗАПУСК
# ──────────────────────────────────────────────────
def main():
    if not BOT_TOKEN:
        print("\n❌ Токен не указан!")
        print("Добавь в файл .env строку: BOT_TOKEN=твой_токен\n")
        return

    persistence = PicklePersistence(filepath="bot_data.pickle")
    app = Application.builder().token(BOT_TOKEN).persistence(persistence).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("start", cmd_start)],
        states={
            BIRTH_DATE:  [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_date)],
            BIRTH_TIME:  [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_time)],
            CHAT: [
                CallbackQueryHandler(callback_router),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_chat),
            ],
            COMPAT_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_compat_name)],
            COMPAT_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_compat_date)],
            GIFT_NAME:   [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_gift_name)],
            GIFT_DATE:   [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_gift_date)],
        },
        fallbacks=[
            CommandHandler("cancel", cmd_cancel),
            CommandHandler("start", cmd_start),
        ],
        allow_reentry=True,
        name="main_conv",
        persistent=True,
    )

    app.add_handler(conv)
    app.add_handler(CommandHandler("horoscope", cmd_horoscope))
    app.add_handler(CommandHandler("group_compat", cmd_group_compat))
    app.add_handler(CommandHandler("join_group", cmd_join_group))
    app.add_handler(CallbackQueryHandler(callback_router))

    print("✅ Бот v2 запущен. Нажми Ctrl+C для остановки.")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()

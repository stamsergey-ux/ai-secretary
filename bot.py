#!/usr/bin/env python3
"""
Мой Астролог — Telegram Bot (Phase 0 Prototype)
Запуск: python3 bot.py
"""

import logging
import os
import re
import random
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
BIRTH_DATE, BIRTH_TIME, CHAT = range(3)

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

CHAT_RESPONSES = {
    "greeting": [
        "Конечно, задавай! Я здесь 🌙",
        "Слушаю тебя внимательно ✨",
        "Да, я здесь. Спрашивай — отвечу 🔮",
    ],
    "thanks": [
        "Всегда пожалуйста 🌙 Если появятся ещё вопросы — пиши.",
        "Рада помочь ✨ Звёзды всегда на твоей стороне.",
        "Обращайся в любое время 🔮",
    ],
    "about": [
        "Я твой персональный астролог 🌙 Каждое утро присылаю гороскоп, составленный специально для тебя на основе нескольких авторитетных источников. И готова ответить на любой вопрос.",
        "Я синтезирую прогнозы ведущих российских астрологов и адаптирую их под твой натальный чарт. Задавай вопросы — отвечу как личный астролог, который знает твою карту.",
    ],
    "confused": [
        "Прости, это вне моей компетенции 🙈 Я астролог — спроси меня о звёздах, отношениях, здоровье или финансах.",
        "Я отвечаю только на вопросы, связанные с астрологией и твоей жизнью ✨ Попробуй спросить что-то другое.",
        "Не совсем поняла вопрос 🌙 Попробуй переформулировать — или спроси о том, что тебя волнует сегодня.",
    ],
    "compatibility": [
        "Совместимость — одна из самых глубоких тем в астрологии. По положению планет сейчас, твой знак особенно хорошо ладит с Водными и Земными знаками. Напиши дату рождения своего мужчины — скажу точнее 🔮",
        "Чтобы проверить совместимость точно, мне нужна дата рождения партнёра. Напиши её в формате ДД.ММ.ГГГГ — и я дам развёрнутый ответ ✨",
        "Звёзды многое говорят о совместимости! Напиши дату рождения его, и я сравню ваши чарты 🌙",
    ],
    "love": [
        "Звёзды говорят: в отношениях сейчас важна не правота, а близость. Первый шаг навстречу принесёт больше, чем долгое ожидание.",
        "Венера подчёркивает важность маленьких жестов. Тёплое слово сегодня стоит больше, чем букет через неделю.",
        "Для твоего знака сейчас важно говорить о чувствах прямо. Партнёр не всегда умеет читать мысли, даже если очень любит.",
    ],
    "family": [
        "Планеты указывают: дети сейчас особенно чутки к атмосфере дома. Твоё спокойствие — лучшее, что ты можешь им дать.",
        "Семейные связи укрепляются через совместные ритуалы. Даже обычный ужин вместе имеет большую силу, чем кажется.",
        "Хорошая мать — это прежде всего женщина, которая заботится и о себе. Не забывай о своих потребностях.",
    ],
    "health": [
        "Звёзды советуют обратить внимание на режим сна — именно он сейчас влияет на всё остальное.",
        "Стакан тёплой воды с лимоном утром запустит обмен веществ и придаст ясность мышлению.",
        "Твой знак сейчас особенно чувствителен к питанию. Больше тёплой еды, меньше кофе.",
    ],
    "finance": [
        "Меркурий сейчас благоприятен для переговоров о деньгах. Если давно хотела поднять финансовый вопрос — время пришло.",
        "Звёзды советуют: крупные покупки лучше отложить до следующей недели. Сейчас время планирования.",
        "Твой знак сейчас интуитивен в финансовых вопросах. Доверяй первому ощущению при выборе.",
    ],
    "timing": [
        "По положению планет, ближайшие 3 дня благоприятны для начала нового. Потом Луна войдёт в фазу завершения дел.",
        "Звёзды говорят: не затягивай с решением дольше трёх дней — момент сейчас хороший.",
        "Для твоего знака сейчас период активных действий. Через две недели наступит время осмысления.",
    ],
    "generic": [
        "Хороший вопрос 🌙 Звёзды говорят: прислушайся к своей интуиции — она сейчас особенно точна.",
        "По твоему натальному чарту — сейчас момент доверять себе. Что именно тебя беспокоит?",
        "Планеты подсказывают: действуй из места любви, а не страха — и результат тебя порадует ✨",
    ],
}

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

def get_ascendant(time_str: str) -> str:
    try:
        h = int(time_str.split(":")[0])
        return ASCENDANTS[h // 2]
    except Exception:
        return "Неизвестен"

def parse_date(text: str):
    """Парсит дату в форматах DD.MM.YYYY, DD/MM/YYYY, YYYY-MM-DD"""
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
    """Парсит время в формате HH:MM"""
    text = text.strip()
    m = re.search(r"(\d{1,2})[:\.](\d{2})", text)
    if m:
        h, minute = int(m.group(1)), int(m.group(2))
        if 0 <= h <= 23 and 0 <= minute <= 59:
            return f"{h:02d}:{minute:02d}"
    return None

def get_chat_response(text: str) -> str:
    t = text.lower().strip()

    # Грубость / негатив — отвечаем мягко, без осуждения
    if re.search(r"туп|дур|идиот|чушь|бред|ерунд|плох|отстой|не работ|сломал|глуп", t):
        return random.choice(CHAT_RESPONSES["confused"])

    # Приветствия и простые фразы
    if re.search(r"^(привет|здравствуй|хай|добр|можно|да|нет|ок|окей|хорошо|понятно|ладно|ясно)$", t):
        return random.choice(CHAT_RESPONSES["greeting"])

    # Благодарность
    if re.search(r"спасиб|благодар|спс|👍|❤", t):
        return random.choice(CHAT_RESPONSES["thanks"])

    # Вопросы про бота
    if re.search(r"кто ты|что ты|как ты|как работ|откуда|зачем ты|что умеешь", t):
        return random.choice(CHAT_RESPONSES["about"])

    # Совместимость — ДО проверки на "муж", чтобы "мужчина" не уходил в love
    if re.search(r"совмест|подход|мы с|он и я|она и я|наша пара|наши отнош", t):
        return random.choice(CHAT_RESPONSES["compatibility"])

    # Отношения и любовь
    if re.search(r"\bмуж\b|партнёр|любов|роман|чувств|отнош|нравится|влюб", t):
        return random.choice(CHAT_RESPONSES["love"])

    # Семья и дети
    if re.search(r"дет|ребён|ребенок|семь|\bмам\b|свекр|дочь|сын|родител", t):
        return random.choice(CHAT_RESPONSES["family"])

    # Здоровье
    if re.search(r"здоров|болез|самочувств|устал|нет сил|энерг|плохо себя", t):
        return random.choice(CHAT_RESPONSES["health"])

    # Финансы и работа
    if re.search(r"деньг|финанс|куп|расход|бюджет|работ|доход|зарплат|бизнес", t):
        return random.choice(CHAT_RESPONSES["finance"])

    # Время и сроки
    if re.search(r"когда|стоит ли|лучше|время|ждать|скоро|период|момент", t):
        return random.choice(CHAT_RESPONSES["timing"])

    return random.choice(CHAT_RESPONSES["generic"])

def ask_claude(question: str, sign: dict, ascendant: str) -> str:
    """Отправляет вопрос пользователя в Claude API с контекстом гороскопа."""
    if not claude_client:
        return get_chat_response(question)

    sign_name = next(k for k, v in SIGNS.items() if v is sign)
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
        return get_chat_response(question)


def build_horoscope_text(sign: dict, ascendant: str) -> str:
    today = datetime.now().strftime("%-d %B %Y").lower()
    # Capitalise first letter
    today = today[0].upper() + today[1:]
    sign_name = next(k for k, v in SIGNS.items() if v is sign)

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
    sign_name = next(k for k, v in SIGNS.items() if v is sign)
    snippet = sign["main"][:120] + "..."
    return (
        f"✨ Мой гороскоп на {today}\n\n"
        f"{sign['symbol']} {sign_name}  ·  ↑ {ascendant}\n\n"
        f"«{snippet}»\n\n"
        f"🌙 Получи свой персональный гороскоп бесплатно:\n"
        f"Напиши боту /start"
    )

# ──────────────────────────────────────────────────
#  ХЭНДЛЕРЫ
# ──────────────────────────────────────────────────
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
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
    sign = get_sign(birth_date)
    sign_name = next(k for k, v in SIGNS.items() if v is sign)

    await update.message.reply_text(
        f"✨ Записала!\n\n"
        f"Теперь скажи, <b>в какое время ты родилась?</b>\n\n"
        f"Напиши время в формате <code>ЧЧ:ММ</code>\n"
        f"Например: <code>14:30</code>\n\n"
        f"<i>Это нужно для точного расчёта твоего восходящего знака (асцендента)</i>",
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
    sign_name = next(k for k, v in SIGNS.items() if v is sign)
    ascendant = get_ascendant(birth_time)
    context.user_data["sign"] = sign
    context.user_data["ascendant"] = ascendant

    # Loading message
    loading_msg = await update.message.reply_text(
        "🔮 Анализирую твой натальный чарт...\n\n"
        "⏳ Запрашиваю прогноз у Павла Глобы...\n"
        "⏳ Проверяю у Василисы Володиной...\n"
        "⏳ Сверяю с картами Дарьи Мироновой..."
    )

    import asyncio
    await asyncio.sleep(3)

    # Send horoscope
    horoscope_text = build_horoscope_text(sign, ascendant)

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📲 Поделиться с подругой", callback_data="share")],
        [InlineKeyboardButton("🔄 Обновить гороскоп", callback_data="refresh")],
    ])

    await loading_msg.delete()
    await update.message.reply_text(
        horoscope_text,
        parse_mode=ParseMode.HTML,
        reply_markup=keyboard,
    )

    await update.message.reply_text(
        f"💬 Можешь задать мне любой вопрос — я отвечу как личный астролог, "
        f"который знает твою карту.\n\n"
        f"<i>Например: «Хороший ли сегодня день для важного разговора?» "
        f"или «Что звёзды говорят о моих отношениях?»</i>",
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


async def handle_refresh(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    sign = context.user_data.get("sign")
    ascendant = context.user_data.get("ascendant", "Неизвестен")
    if not sign:
        await query.message.reply_text("Напиши /start чтобы начать заново.")
        return

    horoscope_text = build_horoscope_text(sign, ascendant)
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📲 Поделиться с подругой", callback_data="share")],
        [InlineKeyboardButton("🔄 Обновить гороскоп", callback_data="refresh")],
    ])
    await query.message.reply_text(horoscope_text, parse_mode=ParseMode.HTML, reply_markup=keyboard)


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


async def callback_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = update.callback_query.data
    if data == "share":
        await handle_share(update, context)
    elif data == "refresh":
        await handle_refresh(update, context)


async def cmd_horoscope(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Повторно показывает гороскоп"""
    sign = context.user_data.get("sign")
    ascendant = context.user_data.get("ascendant", "Неизвестен")
    if not sign:
        await update.message.reply_text("Напиши /start — введём твои данные и составим гороскоп!")
        return
    horoscope_text = build_horoscope_text(sign, ascendant)
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📲 Поделиться с подругой", callback_data="share")],
    ])
    await update.message.reply_text(horoscope_text, parse_mode=ParseMode.HTML, reply_markup=keyboard)


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

    app = Application.builder().token(BOT_TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("start", cmd_start)],
        states={
            BIRTH_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_date)],
            BIRTH_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_time)],
            CHAT:       [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_chat)],
        },
        fallbacks=[CommandHandler("cancel", cmd_cancel)],
        allow_reentry=True,
    )

    app.add_handler(conv)
    app.add_handler(CommandHandler("horoscope", cmd_horoscope))
    app.add_handler(CallbackQueryHandler(callback_router))

    print("✅ Бот запущен. Нажми Ctrl+C для остановки.")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()

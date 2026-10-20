"""Тексты бота: константы существуют, хелперы подставляют свои аргументы.

Зачем
=====

`src/support/texts.py` — единый источник строк, которые бот отправляет. Тест
держит две вещи:

1. **Константы на месте и непусты.** Обработчик, отдавший пустую строку, —
   молчаливый дефект: пользователь видит пузырь без текста, а тест на поведение
   (если он сверяет вхождение) проходит.
2. **Хелперы действительно подставляют переданное.** Правка, выбросившая
   аргумент (`#{ticket_id}` → `#{}`, `{rating}` → литерал), иначе прошла бы
   незамеченной: строка всё ещё «есть».

Каждая проверка имеет негативного близнеца: сломай подстановку — тест красный.
"""

from __future__ import annotations

import pytest

from src.support import texts

# Все пользовательские константы: имя → значение. Набор явный, чтобы новая
# строка не могла проехать незамеченной — тест перечисляет, что обещано.
CONSTANTS = [
    texts.WELCOME,
    texts.HELP,
    texts.CHOOSE_CATEGORY,
    texts.DESCRIBE_PROBLEM,
    texts.EMPTY_DESCRIPTION,
    texts.TICKET_CANCELLED,
    texts.NO_TICKETS,
    texts.CHOOSE_ACTION,
    texts.WRITE_REPLY,
    texts.BAD_REQUEST,
    texts.CANNED_NOT_FOUND,
    texts.CANNED_HINT,
    texts.ASK_PASSWORD,
    texts.ADMIN_WELCOME,
    texts.BAD_PASSWORD,
    texts.TOO_MANY_ATTEMPTS,
    texts.NO_MANAGERS,
    texts.CANNED_STUB,
    texts.CONFIRM_CLOSE,
    texts.TICKET_CLOSED,
    texts.CLOSE_DECLINED,
    texts.RATE_PROMPT,
    texts.TICKET_ALREADY_TAKEN,
    texts.TICKET_TAKEN,
]

BUTTON_LABELS = [
    texts.BTN_NEW_TICKET,
    texts.BTN_MY_TICKETS,
    texts.BTN_HELP,
    texts.BTN_CAT_PAYMENT,
    texts.BTN_CAT_DELIVERY,
    texts.BTN_CAT_TECHNICAL,
    texts.BTN_CAT_OTHER,
    texts.BTN_CONFIRM,
    texts.BTN_CANCEL,
    texts.BTN_REPLY,
    texts.BTN_CLOSE,
    texts.BTN_MANAGERS,
    texts.BTN_STATS,
    texts.BTN_SLA,
    texts.BTN_CANNED,
    texts.BTN_YES,
    texts.BTN_NO,
    texts.BTN_TAKE,
    texts.BTN_SKIP,
    texts.BTN_QUEUE,
    texts.BTN_MY_STATS,
]


@pytest.mark.parametrize("value", CONSTANTS, ids=lambda v: v[:24])
def test_текст_непуст(value: str) -> None:
    """Пустой ответ — пузырь без текста; пользователь не поймёт, что случилось."""
    assert value.strip(), "текст сообщения пуст или из пробелов"


@pytest.mark.parametrize("label", BUTTON_LABELS, ids=lambda v: v[:24])
def test_подпись_кнопки_непуста(label: str) -> None:
    """Кнопка без подписи неотличима от декоративного разделителя."""
    assert label.strip(), "подпись кнопки пуста"


def test_все_подписи_кнопок_уникальны() -> None:
    """Две кнопки с одной подписью — пользователь нажмёт не ту.

    Обработчики выше различают кнопки по тексту (`F.text == ...`), так что
    совпадение подписей ломает маршрутизацию, а не только вид.
    """
    duplicates = {x for x in BUTTON_LABELS if BUTTON_LABELS.count(x) > 1}
    assert not duplicates, f"дубли подписей кнопок: {duplicates}"


def test_приветствие_содержит_подстроку_из_кейсов() -> None:
    """Кейс фермы и e2e-тест цитируют подстроку без эмодзи — она обязана быть.

    `text_contains` сверяет вхождение, поэтому ведущий эмодзи правке не мешает,
    но сама фраза обязана остаться: это тот текст, который ловят оба пути.
    """
    assert "Здравствуйте! Чем можем помочь" in texts.WELCOME


# ── хелперы: подстановка аргумента, а не литерал ────────────────────────────


def test_ticket_created_подставляет_id_и_срок() -> None:
    """Id тикета и SLA различают строку; литерал в их месте — тот же дефект."""
    got = texts.ticket_created(42, 15)
    assert "#42" in got, got
    assert "15 минут" in got, got


def test_ticket_created_чужой_id_меняет_строку() -> None:
    """Негативный близнец: разные id дают разные строки."""
    assert texts.ticket_created(1, 15) != texts.ticket_created(2, 15)


def test_confirm_prompt_показывает_категорию_и_описание() -> None:
    """На шаге подтверждения пользователь видит ровно то, что попадёт в базу."""
    got = texts.confirm_prompt("payment", "не приходит чек")
    assert "payment" in got and "не приходит чек" in got, got


def test_reply_sent_различает_тикеты() -> None:
    """Номер тикета в подтверждении — не украшение, а адрес ответа."""
    assert texts.reply_sent(7) != texts.reply_sent(8)


def test_canned_preview_вставляет_тело_шаблона() -> None:
    """Пустое тело вместо шаблона — это подмена содержимого ответа клиенту."""
    got = texts.canned_preview("Извините за задержку")
    assert "Извините за задержку" in got, got


def test_client_replied_несёт_номер_и_текст() -> None:
    """Менеджер должен видеть и тикет, и сам текст клиента."""
    got = texts.client_replied(3, "Спасибо")
    assert "#3" in got and "Спасибо" in got, got


def test_thanked_печатает_ровно_столько_звёзд() -> None:
    """Оценка отображается числом звёзд: обрезанный или размноженный ряд — ложь."""
    assert texts.thanked(4).count("⭐") == 4


def test_thanked_разные_оценки_различаются() -> None:
    """Негативный близнец: фиксированное число звёзд прошло бы первую проверку."""
    assert texts.thanked(1) != texts.thanked(5)

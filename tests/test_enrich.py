import pytest

from app.enrich import enrich, guess_language, phone_country
from tests.conftest import ENRICH_TOKEN


def test_free_mail_and_domain():
    result = enrich("Olena@Gmail.com", None, "Hello there, a question about your granola.")

    assert result.email_domain == "gmail.com"
    assert result.free_mail
    assert not result.disposable


def test_disposable_mail():
    assert enrich("bot@mailinator.com", None, "Buy cheap followers now!!!").disposable


def test_company_mail_is_neither():
    result = enrich("buyer@cafe.example.com", None, "We want to order wholesale.")

    assert not result.free_mail
    assert not result.disposable


@pytest.mark.parametrize(
    ("phone", "country"),
    [
        ("+380501234567", "UA"),
        ("+48 601 234 567", "PL"),
        ("+1 (415) 555-0100", "US/CA"),
        ("00491701234567", "DE"),
        ("050 123 45 67", "UA"),  # local Ukrainian format
        ("12345", None),
        (None, None),
    ],
)
def test_phone_country(phone, country):
    assert phone_country(phone) == country


@pytest.mark.parametrize(
    ("text", "language"),
    [
        ("Do you deliver to Lviv? We run a small cafe.", "en"),
        ("Чи доставляєте ви до Львова? Ми маємо невелике кафе.", "uk"),
        ("Вы доставляете в Львов? Мы хотим заказать продукцию.", "other"),
        ("12345 !!!", "other"),
    ],
)
def test_language_guess(text, language):
    assert guess_language(text) == language


def test_counts():
    result = enrich("a@example.com", None, "one two  three")

    assert result.message_length == 14
    assert result.word_count == 3


def test_enrich_endpoint_needs_its_token(client):
    body = {"email": "a@example.com", "message": "Hello there, a question."}

    assert client.post("/api/enrich", json=body).status_code == 401
    assert client.post("/api/enrich", json=body, headers={"X-Enrich-Token": "wrong"}).status_code == 401

    response = client.post("/api/enrich", json=body, headers={"X-Enrich-Token": ENRICH_TOKEN})
    assert response.status_code == 200
    assert response.json()["emailDomain"] == "example.com"
    assert response.json()["languageGuess"] == "en"

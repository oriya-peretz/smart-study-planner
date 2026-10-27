from datetime import date

from labels import countdown, is_link, plain

TODAY = date(2026, 11, 10)


def due(day: str, status: str = "todo") -> dict:
    return {"due_at": f"{day}T23:59:00", "status": status}


def test_countdown_words():
    assert countdown(due("2026-11-08"), TODAY) == ":red[overdue 2 days]"
    assert countdown(due("2026-11-09"), TODAY) == ":red[overdue 1 day]"
    assert countdown(due("2026-11-10"), TODAY) == ":primary[**today**]"
    assert countdown(due("2026-11-11"), TODAY) == ":primary[**tomorrow**]"
    assert countdown(due("2026-11-20"), TODAY) == "in 10 days"


def test_finished_tasks_are_not_urgent():
    assert countdown(due("2026-11-01", "done"), TODAY) == ":gray[done]"
    assert countdown(due("2026-11-01", "past"), TODAY) == ":gray[past]"


def test_only_web_addresses_are_links():
    assert is_link("https://github.com/me/ex3")
    assert not is_link(r"C:\Users\me\ex3.docx")


def test_user_text_is_shown_not_interpreted():
    assert plain("**bold** [x](y)") == r"\*\*bold\*\* \[x\]\(y\)"


def test_countdown_words_in_hebrew(monkeypatch):
    import streamlit as st

    monkeypatch.setattr(st, "session_state", {"lang": "he"})
    assert countdown(due("2026-11-08"), TODAY) == ":red[באיחור של 2 ימים]"
    assert countdown(due("2026-11-09"), TODAY) == ":red[באיחור של יום]"
    assert countdown(due("2026-11-11"), TODAY) == ":primary[**מחר**]"
    assert countdown(due("2026-11-20"), TODAY) == "בעוד 10 ימים"
    assert countdown(due("2026-11-01", "past"), TODAY) == ":gray[עבר]"

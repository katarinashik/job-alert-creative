"""
Handles Telegram commands and inline button callbacks.
State is persisted in bot_state.json (cached by GitHub Actions between runs).
All updates (commands + callbacks) are processed at the START of each run.
"""
import json
import os
import requests

STATE_FILE = os.environ.get("STATE_FILE", "bot_state.json")


def load_state() -> dict:
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            return json.load(f)
    return {"paused": False, "offset": 0}


def save_state(state: dict) -> None:
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)


def process_commands(token: str, chat_id: str) -> bool:
    """
    Fetches new Telegram updates, processes commands and button callbacks.
    Returns True if the bot should run, False if paused.
    """
    state = load_state()

    try:
        r = requests.get(
            f"https://api.telegram.org/bot{token}/getUpdates",
            params={"offset": state.get("offset", 0), "timeout": 0},
            timeout=10,
        )
        r.raise_for_status()
        updates = r.json().get("result", [])
    except Exception as e:
        print(f"[commands] failed to fetch updates: {e}")
        return not state.get("paused", False)

    for update in updates:
        state["offset"] = update["update_id"] + 1

        # ── Inline button callback ──────────────────────────────────────────
        if "callback_query" in update:
            _handle_callback(token, chat_id, update["callback_query"])
            continue

        # ── Text commands ───────────────────────────────────────────────────
        msg = update.get("message", {})
        text = msg.get("text", "").strip()
        from_id = str(msg.get("chat", {}).get("id", ""))

        if from_id != str(chat_id):
            continue

        cmd = text.lower().split()[0] if text else ""

        if cmd == "/pause":
            state["paused"] = True
            _reply(token, chat_id, "⏸ Bot mis en pause. Envoie /resume pour redémarrer.")
        elif cmd == "/resume":
            state["paused"] = False
            _reply(token, chat_id, "▶️ Bot relancé. Vérification toutes les 2 heures.")
        elif cmd == "/status":
            status = "⏸ En pause" if state["paused"] else "▶️ Actif (toutes les 2h)"
            _reply(token, chat_id, f"Statut: {status}")
        elif cmd == "/applied":
            _send_action_list(token, chat_id, "applied",
                              "✅ Vos candidatures", "Aucune candidature enregistrée.")
        elif cmd == "/saved":
            _send_action_list(token, chat_id, "saved",
                              "💾 Offres sauvegardées", "Aucune offre sauvegardée.")
        elif cmd == "/digest":
            mode = state.get("digest_mode", False)
            if mode:
                state["digest_mode"] = False
                _reply(token, chat_id,
                       "📨 Mode temps réel activé — alertes envoyées immédiatement.")
            else:
                state["digest_mode"] = True
                _reply(token, chat_id,
                       "📬 Mode digest activé — résumé envoyé à 9h et 18h (heure de Paris).")
        elif cmd == "/help":
            digest_status = "activé" if state.get("digest_mode") else "désactivé"
            _reply(token, chat_id,
                   "Commandes disponibles:\n"
                   "/status — état du bot\n"
                   "/pause — suspendre les alertes\n"
                   "/resume — reprendre les alertes\n"
                   "/applied — voir vos candidatures\n"
                   "/saved — voir les offres sauvegardées\n"
                   f"/digest — basculer mode digest (actuellement: {digest_status})\n"
                   "/help — cette aide")

    save_state(state)
    return not state.get("paused", False)


# ── Callback handling ───────────────────────────────────────────────────────

def _handle_callback(token: str, chat_id: str, query: dict) -> None:
    import storage

    query_id = query.get("id", "")
    data = query.get("data", "")

    # Verify the callback comes from our chat
    msg_chat_id = str(query.get("message", {}).get("chat", {}).get("id", ""))
    if msg_chat_id and msg_chat_id != str(chat_id):
        _answer_callback(token, query_id, "")
        return

    if "|" not in data:
        _answer_callback(token, query_id, "")
        return

    action, job_id = data.split("|", 1)

    if action == "applied":
        row = storage.mark_job_action(job_id, "applied")
        if row:
            title, company, _ = row
            _answer_callback(token, query_id, "✅ Candidature enregistrée !")
            _reply(token, chat_id,
                   f"✅ *Candidature enregistrée*\n_{_esc(title)}_ @ {_esc(company)}",
                   parse_mode="Markdown")
        else:
            _answer_callback(token, query_id, "Offre introuvable (trop ancienne?)")

    elif action == "save":
        row = storage.mark_job_action(job_id, "saved")
        if row:
            title, company, _ = row
            _answer_callback(token, query_id, "💾 Sauvegardée !")
        else:
            _answer_callback(token, query_id, "Offre introuvable (trop ancienne?)")

    elif action == "ignore":
        # Job is already deduplicated in DB — just acknowledge
        _answer_callback(token, query_id, "Ok, ignorée.")

    else:
        _answer_callback(token, query_id, "")


def _answer_callback(token: str, callback_query_id: str, text: str) -> None:
    """Acknowledge an inline button tap (required by Telegram within 30s)."""
    try:
        requests.post(
            f"https://api.telegram.org/bot{token}/answerCallbackQuery",
            json={
                "callback_query_id": callback_query_id,
                "text": text,
                "show_alert": False,
            },
            timeout=5,
        )
    except Exception:
        pass


# ── List commands (/applied, /saved) ───────────────────────────────────────

def _send_action_list(token: str, chat_id: str, action: str,
                      header: str, empty_msg: str) -> None:
    import storage

    rows = storage.get_job_actions(action)
    if not rows:
        _reply(token, chat_id, empty_msg)
        return

    MONTHS_FR = ["jan", "fév", "mar", "avr", "mai", "juin",
                 "juil", "août", "sep", "oct", "nov", "déc"]

    lines = [f"*{header}* \\({len(rows)}\\)\n"]
    for _, title, company, url, actioned_at in rows[:20]:
        date_part = ""
        if actioned_at:
            try:
                from datetime import datetime
                dt = datetime.fromisoformat(actioned_at[:19])
                date_part = f" — {dt.day} {MONTHS_FR[dt.month - 1]}"
            except Exception:
                pass
        lines.append(f"• [{_esc(title)} @ {_esc(company)}]({url}){date_part}")

    _reply(token, chat_id, "\n".join(lines), parse_mode="Markdown")


# ── Helpers ─────────────────────────────────────────────────────────────────

def _reply(token: str, chat_id: str, text: str, parse_mode: str = "") -> None:
    try:
        payload: dict = {"chat_id": chat_id, "text": text,
                         "disable_web_page_preview": True}
        if parse_mode:
            payload["parse_mode"] = parse_mode
        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json=payload,
            timeout=10,
        )
    except Exception as e:
        print(f"[commands] reply failed: {e}")


def _esc(text: str) -> str:
    for ch in r"_*[]()~`>#+-=|{}.!":
        text = text.replace(ch, f"\\{ch}")
    return text

"""Watch for the owner's reply, and start the next run when it arrives.

The loop is: an agent works a bucket, emails what it did and what it could not
decide, and stops. Nothing else happens until the owner answers. His reply is
the clock.

That is the point of the design. A scheduled agent reports success when the
session started and exited, which is not the same as having done anything, and
there is no alerting to tell the difference. Here, a run that fails to send its
email simply never triggers the next one -- so the loop stopping IS the alarm,
and it is visible in the one place the owner already looks.

This script is the only scheduled thing in the system. It does no work itself:
it asks whether a reply has arrived, and if so it fires the run that does.

    python -m qa.poll --check      # has the owner replied?  exit 0 if yes
    python -m qa.poll --fire       # check, and start the next run if so

State lives in `qa/mail_state.json`, committed, because a fresh clone has no
memory of which question is outstanding.
"""

import argparse
import json
import os
import sys
import urllib.error
import urllib.request

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE = os.path.join(BASE, "qa", "mail_state.json")

FIRE_URL = ("https://api.anthropic.com/v1/claude_code/routines/"
            "{routine_id}/fire")


def load_state():
    if not os.path.exists(STATE):
        return {}
    with open(STATE, encoding="utf-8") as fh:
        return json.load(fh)


def save_state(st):
    with open(STATE, "w", encoding="utf-8") as fh:
        json.dump(st, fh, indent=2, sort_keys=True)
        fh.write("\n")


def fire(payload_text):
    """Start the next run.

    The routine's own prompt decides what to do; the text here is context, and
    it arrives wrapped and labelled as untrusted, so the prompt must opt in to
    acting on it. That is deliberate: what is being passed along is an email
    from a mailbox, and a mailbox takes input from anyone.
    """
    rid = os.environ.get("CLAUDE_ROUTINE_ID")
    token = os.environ.get("CLAUDE_ROUTINE_TOKEN")
    if not (rid and token):
        print("no routine configured (CLAUDE_ROUTINE_ID / CLAUDE_ROUTINE_TOKEN); "
              "reply detected but nothing was started")
        return False
    body = json.dumps({"text": payload_text[:60000]}).encode()
    req = urllib.request.Request(FIRE_URL.format(routine_id=rid), data=body)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Content-Type", "application/json")
    req.add_header("anthropic-version", "2023-06-01")
    req.add_header("anthropic-beta", "experimental-cc-routine-2026-04-01")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            print(f"routine fired: HTTP {r.status}")
        return True
    except urllib.error.HTTPError as exc:
        # Say what is wrong in one line.  A traceback here is the same failure
        # this whole design exists to avoid: something broke, and the message
        # explaining it is buried where nobody reads it.
        if exc.code == 401:
            print("fire refused: HTTP 401. CLAUDE_ROUTINE_TOKEN is not valid for "
                  "this routine. The trigger token is minted from the routine "
                  "itself and starts sk-ant-oat01-; a standard sk-ant-api03 API "
                  "key will not authenticate here.")
        elif exc.code == 404:
            print(f"fire refused: HTTP 404. No routine {rid} -- check "
                  "CLAUDE_ROUTINE_ID.")
        elif exc.code == 429:
            print("fire refused: HTTP 429, the daily routine-run cap is spent. "
                  f"Retry after: {exc.headers.get('Retry-After', 'unspecified')}")
        else:
            print(f"fire refused: HTTP {exc.code} {exc.reason}")
        return False


def outstanding(thread_id, token=None):
    """Is the owner's answer the newest thing in the thread?

    This used to be answered from `qa/mail_state.json`, and that broke: a run
    commits its state to a `claude/*` branch, the poller reads `main`, and
    nobody merges between them -- so main said "nothing outstanding" while a
    question sat unanswered in the thread. The loop stopped silently, which is
    the one failure it was built to make visible.

    The thread already knows. If the newest message is ours, we are waiting for
    him. If the newest is his, he has answered whatever we last asked. No state
    file, nothing to fall out of sync, and no branch to merge.

    Returns (has_replied, description).
    """
    token = token or _access_token()
    from qa import mail
    t = mail._call(f"/threads/{thread_id}?format=metadata", token)
    msgs = t.get("messages", [])
    if not msgs:
        return False, "thread is empty"
    import email.utils
    newest = msgs[-1]
    headers = {h["name"].lower(): h["value"]
               for h in newest.get("payload", {}).get("headers", [])}
    _, addr = email.utils.parseaddr(headers.get("from", ""))
    date = headers.get("date", "")
    if addr.strip().lower() == mail.OWNER.strip().lower():
        return True, f"newest message is his reply, {date}"
    return False, f"newest message is ours, {date} -- waiting"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--fire", action="store_true")
    ap.add_argument("--show", action="store_true",
                    help="print the reply, quoted original stripped")
    args = ap.parse_args()

    st = load_state()
    thread = st.get("thread_id")
    if not thread:
        print("no thread id in qa/mail_state.json")
        return 0 if args.fire else 1

    from qa import mail
    token = mail._access_token()
    replied, why = outstanding(thread, token)
    print(why)
    if not replied:
        return 0 if args.fire else 1

    latest = mail.replies(thread, token)[-1]

    if args.show:
        text = mail.body_of(latest["id"], token)
        for m in (chr(10) + "On ", chr(10) + ">"):
            cut = text.find(m)
            if cut > 0:
                text = text[:cut]
        print()
        print(text.strip())
        return 0

    if args.fire:
        text = mail.body_of(latest["id"], token)
        for m in (chr(10) + "On ", chr(10) + ">"):
            cut = text.find(m)
            if cut > 0:
                text = text[:cut]
        fire(text.strip())
    return 0


if __name__ == "__main__":
    sys.path.insert(0, BASE)
    raise SystemExit(main())

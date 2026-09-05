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
    """Start the next run by cutting a GitHub release.

    The routine is wired to fire on a `release` event in this repository, so
    starting it needs no Anthropic credential at all -- only the GITHUB_TOKEN
    that Actions already provides to its own workflows.

    That is worth the indirection. The alternative was a per-routine trigger
    token that has to be minted in a browser, shown once, and then copied into a
    secret; it took several attempts to establish that the value being copied
    was an ordinary API key, which the fire endpoint refuses. A release is a
    thing this repository can already make.

    The reply text goes in the release body, so the run can read what the owner
    actually said. It arrives as untrusted content either way -- it came from a
    mailbox, and a mailbox takes input from anyone.
    """
    import datetime
    import subprocess

    tag = "qa-" + datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d-%H%M%S")
    try:
        r = subprocess.run(
            ["gh", "release", "create", tag,
             "--repo", os.environ.get("GITHUB_REPOSITORY",
                                      "JamesNicholsWorley/muni-harvest"),
             "--title", "QA loop: the owner replied",
             "--notes", payload_text[:60000] or "(empty reply)"],
            capture_output=True, text=True, timeout=120)
    except FileNotFoundError:
        print("gh is not installed; cannot cut the release that starts the run")
        return False
    if r.returncode == 0:
        print(f"release {tag} created; the routine fires on it")
        return True
    print(f"could not create the release: {r.stderr.strip()[:200]}")
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--fire", action="store_true")
    ap.add_argument("--show", action="store_true",
                    help="print the reply, quoted original stripped")
    args = ap.parse_args()

    st = load_state()
    thread = st.get("thread_id")
    anchor = st.get("last_message_id")
    if not (thread and anchor):
        print("no outstanding question -- nothing to wait for")
        return 0

    from qa import mail
    if not mail.has_reply_since(thread, anchor):
        print(f"no reply yet to {anchor} in thread {thread}")
        return 1

    replies = mail.replies(thread)
    latest = replies[-1]
    print(f"reply found: {latest['date']}")

    if args.show:
        text = mail.body_of(latest["id"])
        # Strip the quoted original.  A reply carries the whole previous email
        # back, and reading that as the answer feeds a run its own words.
        for marker in ('\nOn ', '\n>'):
            cut = text.find(marker)
            if cut > 0:
                text = text[:cut]
        print()
        print(text.strip())
        return 0

    if args.fire:
        text = mail.body_of(latest["id"])
        # Strip the quoted original.  A reply carries the whole previous email
        # back, and passing that along would feed the agent its own words as if
        # they were the owner's answer.
        for marker in ("\nOn ", "\n>"):
            cut = text.find(marker)
            if cut > 0:
                text = text[:cut]
        if fire(text.strip()):
            # The question is answered; stop waiting on it.  The run that starts
            # now is responsible for recording the next one.
            st["last_message_id"] = None
            st["answered"] = latest["id"]
            save_state(st)
    return 0


if __name__ == "__main__":
    sys.path.insert(0, BASE)
    raise SystemExit(main())

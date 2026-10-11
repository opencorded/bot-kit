#!/usr/bin/env python3
"""Runs the kit and its two example bots against a throwaway server.

    python3 kit_smoke.py <folder with cordedd and corded-cli>

The kit (corded_bot.py) is looked for where CORDED_BOT_KIT says, in ./kit, or
in a bot-kit folder beside this repository.
"""
import base64
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer

bin_dir = os.path.abspath(sys.argv[1])
repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
bots = repo
for kit in (os.environ.get("CORDED_BOT_KIT", ""), repo, os.path.join(repo, "kit"), os.path.join(repo, "..", "bot-kit")):
    if kit and os.path.exists(os.path.join(kit, "corded_bot.py")):
        sys.path.insert(0, os.path.abspath(kit))
        os.environ["CORDED_BOT_KIT"] = os.path.abspath(kit)
        break
from corded_bot import Bot, Message, mentioned_names  # noqa: E402,F401

os.environ["CORDED_CLI"] = os.path.join(bin_dir, "corded-cli")

def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def main():
    tmp = tempfile.mkdtemp(prefix="corded-bots-")
    started = []
    try:
        port, hook_port, model_port = free_port(), free_port(), free_port()
        address = f"127.0.0.1:{port}"
        started.append(subprocess.Popen([os.path.join(bin_dir, "cordedd"), "--port", str(port), "--data",
                                         os.path.join(tmp, "server"), "--owner", "alice"],
                                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
        time.sleep(1)

        # A person, written with the same kit, who records what she is told.
        heard = []
        alice = Bot(vault=os.path.join(tmp, "alice"), username="alice", is_bot=False, hear_bots=True)
        alice.on_message(lambda m: heard.append((m.sender, m.body)))
        heard_where = []
        alice.on_message(lambda m: heard_where.append((m.room_id, m.body)))
        alice.connect(address)
        threading.Thread(target=alice.run, daemon=True).start()

        def wait_for(what, test, seconds=25, among=heard):
            end = time.time() + seconds
            while time.time() < end:
                for item in list(among):
                    if test(item):
                        return item
                time.sleep(0.2)
            raise AssertionError(f"did not hear {what}; heard {among}")

        def person(name):
            """Someone else, who keeps the messages and files that reach them."""
            texts, files = [], []
            someone = Bot(vault=os.path.join(tmp, name), username=name, is_bot=False, hear_bots=True)
            someone.on_message(texts.append)
            someone.on_file(files.append)
            someone.connect(address)
            threading.Thread(target=someone.run, daemon=True).start()
            return someone, texts, files

        def bot_process(*words):
            p = subprocess.Popen([sys.executable, *words], cwd=bots, stdout=subprocess.PIPE, text=True)
            started.append(p)
            line = p.stdout.readline()   # each bot prints one line when it is connected
            assert "connected" in line, line
            return p

        bot_process("command_bot.py", address, "helper", os.path.join(tmp, "helper"))
        time.sleep(2)   # the room's member list reaches alice
        alice.say("#general", "!ping")
        wait_for("pong", lambda item: item == ("helper", "pong"))
        alice.say("#general", "!roll 3d6")
        sender, body = wait_for("a roll", lambda item: item[0] == "helper" and "=" in item[1])
        assert 3 <= int(body.rsplit("=", 1)[1]) <= 18, body
        alice.say("#general", "!help")
        wait_for("the list of commands", lambda item: item[0] == "helper" and "!roll" in item[1] and "!ping" in item[1])
        print("ok  command bot: ping, dice and help")

        bot_process("webhook_bot.py", address, "#general", "--port", str(hook_port), "--secret", "s3cret",
                    "--vault", os.path.join(tmp, "hooks"))
        time.sleep(2)

        def post(path, body, headers):
            request = urllib.request.Request(f"http://127.0.0.1:{hook_port}{path}", data=json.dumps(body).encode(),
                                             headers={"Content-Type": "application/json", **headers})
            try:
                return urllib.request.urlopen(request, timeout=20).status
            except urllib.error.HTTPError as error:
                return error.code
        assert post("/say", {"text": "no secret"}, {}) == 403
        assert post("/say", {"text": "the build passed"}, {"X-Corded-Secret": "s3cret"}) == 200
        wait_for("the posted line", lambda item: item == ("webhooks", "the build passed"))
        import hashlib
        import hmac
        push = {"ref": "refs/heads/main", "repository": {"full_name": "a/b"}, "sender": {"login": "drew"},
                "commits": [{"message": "Fix the thing\n\nlong"}, {"message": "Add a test"}]}
        raw = json.dumps(push).encode()
        signed = urllib.request.Request(
            f"http://127.0.0.1:{hook_port}/github", data=raw,
            headers={"X-GitHub-Event": "push",
                     "X-Hub-Signature-256": "sha256=" + hmac.new(b"s3cret", raw, hashlib.sha256).hexdigest()})
        assert urllib.request.urlopen(signed, timeout=20).status == 200
        wait_for("the push", lambda item: item[0] == "webhooks" and "pushed 2 commits to a/b (main)" in item[1]
                 and "- Fix the thing" in item[1])
        assert post("/github", push, {"X-GitHub-Event": "push", "X-Hub-Signature-256": "sha256=00"}) == 403
        print("ok  webhook bot: a plain post, a signed GitHub push, and refusals without the secret")

        carol, carol_heard, carol_files = person("carol")
        time.sleep(3)

        # The rest of the kit.
        assert mentioned_names("hi @Sage, mail me a@b.c or @sage-2") == {"sage", "sage-2"}
        assert Message({"content": {"body": "hey @SAGE!"}}, me="sage").mentions_me
        assert not Message({"content": {"body": "@sagebrush hello"}}, me="sage").mentions_me
        link = alice.say("#general", "a link: https://example.com/clip")["event_id"]
        alice.say("#general", "an answer", reply_to=link)
        note = os.path.join(tmp, "note.txt")
        open(note, "w").write("a file for the thread")
        alice.send_file("#general", note, "as asked", thread=link)
        answer = wait_for("the answer", lambda m: m.body == "an answer", among=carol_heard)
        assert answer.reply_to == link and carol.recall(link).body == "a link: https://example.com/clip"
        sent = wait_for("the file", lambda m: m.file["name"] == "note.txt", among=carol_files)
        assert sent.thread == link and sent.body == "as asked" and sent.file["size"] == 21
        order = []
        ahead = [alice.work(lambda n=n: (time.sleep(0.3), order.append(n))) for n in range(3)]
        time.sleep(1.5)
        assert ahead == [0, 1, 2] and order == [0, 1, 2], (ahead, order)
        print("ok  bot kit: mentions, what a message answers, a file into a thread, one job at a time")
        print("PASS")
    finally:
        for p in started:
            p.terminate()
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()


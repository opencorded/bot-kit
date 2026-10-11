#!/usr/bin/env python3
"""Installs a Corded bot from its repository.

    python3 install.py https://github.com/opencorded/bot-clips
    python3 install.py ../my-bot --server chat.example.org:7443 --host ~/corded/host/host.json

It fetches the bot (or uses a folder you already have), shows what it is and
exactly what its set-up script will run, and asks before running anything.
Then it tells you how to start the bot, or, with --host, adds it to the list
of a Corded host so that it starts with everything else.

A bot is someone else's program. Installing one runs their set-up script on
this machine with your rights, and the bot will then read every message in
the chats it is in. Read what is shown before you say yes.
"""
import argparse
import json
import os
import subprocess
import sys

parser = argparse.ArgumentParser(description="Installs a Corded bot from its repository.")
parser.add_argument("source", help="the bot's git address, or a folder that already holds it")
parser.add_argument("--to", default=".", help="where to put it (a folder named after the bot is made there)")
parser.add_argument("--server", default="127.0.0.1:7443", help="the server it will join: host:port, or an invite link")
parser.add_argument("--vaults", default="~/corded-bots", help="where bots keep their accounts")
parser.add_argument("--host", default=None, help="a Corded host's host.json: the bot is added to it")
parser.add_argument("--yes", action="store_true", help="do not ask; for scripts that have shown all this already")
args = parser.parse_args()
sys.stdout.reconfigure(line_buffering=True)   # so that what it says and what the set-up script says come in order


def stop(why):
    print(why, file=sys.stderr)
    sys.exit(1)


# ---- fetch it ----

if os.path.isdir(os.path.expanduser(args.source)):
    folder = os.path.abspath(os.path.expanduser(args.source))
else:
    name = args.source.rstrip("/").split("/")[-1].removesuffix(".git")
    folder = os.path.abspath(os.path.join(os.path.expanduser(args.to), name))
    if os.path.exists(folder):
        stop(f"{folder} is already there. To set it up again, give that folder instead of the address.")
    print(f"Fetching {args.source} ...")
    if subprocess.run(["git", "clone", "--quiet", "--depth", "1", args.source, folder]).returncode != 0:
        stop("That could not be fetched.")

described = os.path.join(folder, "bot.json")
if not os.path.exists(described):
    stop(f"{folder} has no bot.json, the file in which a bot says what it is and how it is started.")
with open(described, encoding="utf-8") as f:
    bot = json.load(f)
name = bot.get("name") or os.path.basename(folder)
vault = os.path.join(os.path.expanduser(args.vaults), name)

# ---- show what it is, and ask ----

print()
print(f"  {bot.get('title', name)}: {bot.get('about', '')}")
print(f"  from      {args.source}")
print(f"  into      {folder}")
needs = bot.get("needs") or {}
for label, key in (("needs", "programs"), ("better with", "optional")):
    if needs.get(key):
        print(f"  {label:<9} {', '.join(needs[key])}")
if needs.get("gpu"):
    print(f"  needs     a graphics card with {needs['gpu']}")
setup = os.path.join(folder, bot.get("setup", "setup.sh"))
if os.path.exists(setup):
    print(f"\n  Its set-up script, {os.path.basename(setup)}, would run this on your machine:\n")
    with open(setup, encoding="utf-8") as f:
        for line in f:
            print("      " + line.rstrip())
print("\n  Once started it joins the server as a member and reads every message in the chats it is in.")
if not args.yes:
    try:
        said = input("\nInstall it? [y/N] ").strip().lower()
    except EOFError:
        said = ""
    if said not in ("y", "yes"):
        stop("Nothing was run. The folder is still there; delete it if you do not want it.")

if os.path.exists(setup):
    print()
    if subprocess.run(["sh", setup], cwd=folder).returncode != 0:
        stop("The set-up script failed; see above.")

# ---- say how to start it, or add it to a host ----


def filled(words):
    return [str(w).replace("{server}", args.server).replace("{vault}", vault).replace("{folder}", folder) for w in words]


start = filled(bot.get("start") or [])
if not start:
    stop("bot.json does not say how the bot is started (\"start\").")

if args.host:
    path = os.path.expanduser(args.host)
    with open(path, encoding="utf-8") as f:
        listed = json.load(f)
    names = {u.get("name") for u in listed.get("units", [])}
    added = []
    after = ["server"] if "server" in names else []
    for companion in bot.get("companions") or []:
        if companion["name"] not in names:
            unit = {"name": companion["name"], "kind": "model", "cwd": folder, "cmd": filled(companion["start"])}
            for key in ("port", "memory_max", "about"):
                if key in companion:
                    unit[key] = companion[key]
            listed["units"].append(unit)
            added.append(companion["name"])
        after.append(companion["name"])
    if name in names:
        print(f"\n{name} is already in {path}; left as it is.")
    else:
        listed["units"].append({"name": name, "kind": "bot", "about": bot.get("about", ""), "after": after,
                                "vault": vault, "cwd": folder, "cmd": start})
        added.append(name)
    if added:
        with open(path + ".new", "w", encoding="utf-8") as f:
            json.dump(listed, f, indent=2)
            f.write("\n")
        os.replace(path + ".new", path)
        print(f"\nAdded to {path}: {', '.join(added)}. Restart the host (Ctrl+C, then start it again) and it runs.")
else:
    print(f"\nInstalled. Start it from {folder} with:\n\n    {' '.join(start)}\n")
    for companion in bot.get("companions") or []:
        print(f"It also needs this running beside it ({companion['name']}):\n\n    {' '.join(filled(companion['start']))}\n")
    print("To have it start with your server and show on one page with it, see https://github.com/opencorded/host")

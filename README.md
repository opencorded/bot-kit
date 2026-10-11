# The Corded bot kit

A Corded bot is an ordinary member of a server. It has a username, its own keys
and its own encrypted vault, and it reads and writes end-to-end encrypted
messages exactly as a person's client does. The server cannot tell it from a
person; its profile says "bot", so people see a BOT tag beside its name.

Everything here is plain Python 3 with no packages to install (the video bot
also needs the programs yt-dlp and ffmpeg on the machine). The bots drive
`corded-cli`, the headless client that ships with Corded, so they contain no
encryption code of their own.

## Try one

From this folder, with a server running on this machine:

```sh
python3 command_bot.py 127.0.0.1:7443
```

It joins as `helper`. In any channel it can see, type `!ping`, `!roll 2d6`,
`!choose pizza | tacos` or `!help`.

The first run makes a folder (`helper-vault`) holding the bot's keys and a
passphrase file that only your user can read. Keep the folder: it *is* the
bot's account. On an invite-only server pass an invite link instead of the
address.

## The bots made with it

| Bot | What it does |
|---|---|
| [Sage](https://github.com/opencorded/bot-sage) | A chat member run by a language model on your own machine |
| [Pictures](https://github.com/opencorded/bot-pictures) | Makes pictures from a description, with Stable Diffusion on your own machine |
| [Clips](https://github.com/opencorded/bot-clips) | Posts the video behind a link as a file |
| [Birthdays](https://github.com/opencorded/bot-birthdays) | Asks for birthdays and wishes people on the day |
| `command_bot.py` (here) | `!ping`, dice, choosing: the smallest useful bot, to copy from |
| `webhook_bot.py` (here) | Posts what other programs send it over HTTP (a build result, a GitHub push) |

The [host](https://github.com/opencorded/host) runs a server and any number of bots with one command
and shows them all on one page.

## Write your own

```python
from corded_bot import Bot

bot = Bot(vault="./my-vault", username="mybot", about="What I am for.",
          display_name="My Bot", picture="mybot.png")   # both optional; the picture about 128 pixels square

@bot.command("hello", help="say hello")
def hello(message, words):          # words: what came after !hello
    return f"Hello, {message.sender_name}."     # returned text is sent as a reply

@bot.on_message
def every_message(message):          # every message from someone else
    if "thanks" in message.body.lower():
        bot.react(message, "👍")

@bot.every(3600)
def hourly():
    bot.say("#general", "Another hour gone.")

bot.connect("127.0.0.1:7443")
bot.run()
```

A message has `body`, `sender` (the username), `sender_name` (what people
see), `room_id`, `event_id`, `thread` (the message whose thread it is in),
`reply_to` (the message it answers), `mentions_me` (it says `@` and the bot's
name) and `direct` (it was said in a direct chat with the bot).

| | |
|---|---|
| `bot.say(room, text, reply_to=, thread=)` | Send text. A room is its id or its title, like `"#general"`. |
| `bot.reply(message, text)` | Answer where the message was said. |
| `bot.dm(username, text)` | Open the direct chat with someone and say something there. Returns the room id. |
| `bot.react(message, emoji)` | `bot.unreact(message, what_react_returned)` takes it back. |
| `bot.send_file(room, path, caption, reply_to=, thread=)` | `thread=` puts the file in the thread under that message. |
| `bot.typing(room)` | Show "typing" for a few seconds while working. |
| `bot.recall(event_id)` | A recent message by its id: what `reply_to` and `thread` point at. |
| `bot.lookup(room_id, event_id)` | The same for a message of any age: from the bot's vault if it is older than it remembers. |
| `bot.members()`, `bot.profile_of(user_id)`, `bot.rooms` | Who and what the bot can see. |
| `bot.may(user_id)` | Whether someone may give the bot orders: the server's owner, and anyone whose roles have the Manage bots permission. `bot.may(user_id, "kick_members")` asks about another permission. |
| `bot.work(fn, *args)` | Run a job after those already waiting, one at a time (one model, one graphics card). Returns how many are ahead. |
| `bot.store` | A dictionary kept between runs, in `store.json` in the bot's folder. Call `bot.store.save()` after changing it. |
| `bot.attempt(fn, *args)` | Call something that may fail without stopping the rest; the failure is printed. |
| `bot.request({...})` | Any command the core understands; returns its answer. |

More things to hang a function on:

```python
@bot.on_join
def welcome(member):                 # someone joined the server
    bot.dm(member["username"], f"Welcome, {member['display_name']}.")

@bot.on_file
def got(message):                    # someone sent a file
    print(message.file["name"], message.file["size"], message.body)

@bot.on_profile
def changed(user_id, profile):       # someone's profile reached the bot, new or changed
    print(profile.get("birthday"))
```

`on_join` is called once for each person who joins after the bot's first run,
also for those who joined while it was off. The people already there on the
first run are not counted as joining, and other bots never are.

A bot does not hear other bots (two answering each other would never stop);
`Bot(..., hear_bots=True)` changes that.

## Installing a bot someone else wrote

```sh
git clone https://github.com/opencorded/bot-kit
python3 bot-kit/install.py https://github.com/opencorded/bot-clips
```

It fetches the bot, shows what it is, what it needs and **exactly what its
set-up script would run**, and asks before running anything. Then it says how
to start the bot. With `--host path/to/host.json` it adds the bot (and any
program it needs beside it) to a [Corded host](https://github.com/opencorded/host)'s
list instead, so it starts with everything else. `--server` names the server
it will join; `--vaults` where bot accounts are kept.

A bot is someone else's program: installing it runs their script on your
machine, and the bot then reads every message in the chats it is in. That is
why this is done on the machine itself, by whoever runs it, and never from a
chat.

For your own bot to be installable this way, give it a `bot.json`:

```json
{
  "name": "clips",
  "title": "Clips",
  "about": "Posts the video behind a link as a file",
  "needs": {"programs": ["yt-dlp", "ffmpeg"]},
  "setup": "setup.sh",
  "start": ["python3", "-u", "video_bot.py", "{server}", "--vault", "{vault}"],
  "companions": [{"name": "its-helper", "start": ["{folder}/helper"], "port": 9000}]
}
```

`{server}`, `{vault}` and `{folder}` are filled in. What the bot's settings
are is not written here: the bot says that itself, live (next section).

## Letting people manage your bot from the app

In the app, tapping a bot in the members list offers **Manage**: a page with
the bot's settings as real controls. The bot says what goes on that page, in
a few lines:

```python
bot.version = "1.0"
bot.setting("limit", "number", "Pictures per person in ten minutes",
            get=lambda: bot.store.get("limit", 5),
            set=lambda v: (bot.store.__setitem__("limit", v), bot.store.save()),
            min=0, max=100, help="0 means no limit")
bot.setting("mode", "choice", "Adult pictures", options=["off", "nsfw"], get=..., set=...)
bot.setting("where", "channels", "Channels it works in", get=..., set=...)
bot.action("restart", "Restart", run=restart, needs="owner", confirm="Restart the bot?")
bot.permission("use", "May ask for pictures")       # a permission of the bot's own
bot.info("made", "Pictures made", get=lambda: str(count))

if not bot.allowed(message.sender_id, "use"):
    return "You may not ask me for pictures."
```

Kinds of setting: `number` (`min`, `max`), `switch`, `choice` (`options`),
`text`, `channels`. A setting without `set` is shown and cannot be changed.
`needs` says who may change a control: `"manage_bots"` (the owner and those
whose role has Manage bots; what you get if you say nothing), `"owner"`,
`"everyone"`, any server permission by name, or the key of a permission the
bot made with `permission()`. A permission's page entry lets those who manage
bots choose which roles hold it; `bot.allowed(user_id, key)` asks. On and off
are on every bot's page without your doing anything.

How it travels, for anyone writing another client: everything is an ordinary
encrypted event in the direct chat between one person and the bot, so the
server relays it without knowing what it is.

| Event | From | Content |
|---|---|---|
| `m.bot.describe` | the person | nothing |
| `m.bot.description` | the bot | `v`, `name`, `title`, `about`, `version`, `controls` |
| `m.bot.set` | the person | `key`, `value` |
| `m.bot.act` | the person | `key` |
| `m.bot.result` | the bot | `ok`, `message`, `key`; a fresh description follows |

A control is `{key, type, label, help, value, can_change}` plus what its type
needs (`min`, `max`, `options`). What a person is shown depends on who they
are, and **the bot checks every change itself**: a client that sends a change
it should not is told no.

## Bots asking bots

A bot can offer something to other bots, and ask another bot for what it
offers. Each still stands alone: neither needs the other to run.

```python
# the bot that offers
@bot.offer("picture")
def picture_for(args, asker, via):          # asker: the member it is for; via: the asking bot
    if not asker or not bot.allowed(asker["user_id"], "use"):
        return {"ok": False, "message": "they may not ask me for pictures"}
    return {"file": make(args["prompt"]), "delete_after": True}

# the bot that asks
got = bot.ask_bot("pictures", "picture", {"prompt": "an owl"}, on_behalf_of=message.sender_id)
if got["ok"]:
    use(got["file"])
```

It is asked in the direct chat between the two bots (`m.bot.request` with
`name`, `args`, `on_behalf_of`) and answered once (`m.bot.result` with `ok`,
`message`, and `file_event` when a file was sent beside it). The asked bot
applies its own rules to the person named. A request is never answered with a
request, and bots go on ignoring each other's ordinary messages, so two bots
cannot end up talking in circles.

## Where the kit looks for `corded-cli`

`CORDED_CLI` if it is set; then beside the kit and one folder up (a Corded
release unpacked next to it); then your `PATH`.

## Turning a bot off and on

Every bot made with the kit answers `!name off` and `!name on`, where name is
its username, from the owner or anyone with **Manage bots**. Off, it stays
connected but shows as offline, hears nothing except the command that wakes
it, and its timers rest. `!name status` says which it is. The choice is kept
across restarts. In your own bot, `@bot.on_power` is called with True or False
when it is switched. A file called `power` in the bot's folder holding `on` or
`off` does the same from the machine it runs on, which is how the host's page
does it.

When a bot starts, messages sent more than two minutes before are not
answered (pass `catch_up=True` to `Bot` if yours should work through them).

## Tests

```sh
python3 tests/kit_smoke.py /folder/with/cordedd/and/corded-cli
```

Part of [Corded](https://github.com/AndrewCromar/corded). Apache-2.0.

# Track

A discord bot focused on World Of Warships, written in Python.
A very special thank you to alpha#9432 and everyone else who participated in the creation of this bot.


# Setup

You can invite the bot [here](https://discordapp.com/oauth2/authorize?client_id=633110582865952799&scope=bot&permissions=388160). However, if you want to set up your own instance, follow the below steps:

1. Create a new Python 3.7.4 [venv](https://docs.python.org/3/library/venv.html), and install dependencies with `pip install -U -r requirements.txt`. Install `discord-ext-menus` with:
    ```
    python -m pip install -U git+https://github.com/Rapptz/discord-ext-menus
    ```

2. Obtain a copy of GameParams.data using the [WoWS unpacker tool](https://forum.worldofwarships.eu/topic/113847-all-wows-unpack-tool-unpack-game-client-resources/). After placing it in `/scripts/GameParams/`, run `dump.py`. Repeat this for each WoWS update.

3. Also unpack ship_bars, and place it in `/assets/private/`.

4. Obtain a copy of `global.mo` from your WoWS installation. Place it in `/assets/private/`. Repeat this for each WoWS update, and reload the WoWS cog to load the new values without restarting the bot.

5. Create a `config.py` file with `config_template.py` as a template. To obtain the `discord_token`, create a new discord application, make a bot user, and copy the token [here](https://discordapp.com/developers/applications/). For `wargaming_id`, create a new application (mobile) and copy the ID [here](https://developers.wargaming.net/applications/).

6. Create the necessary tables by running `scripts/setup.py`.

7. To start the bot, run `bot.py`!

# Have suggestions or need more help?
[Join the support discord!](https://discord.gg/dU39sjq)

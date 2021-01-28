This is a fork of Padtrack's wonderful and powerful WoWS Discord bot. I've made minor adjustments, but this is mostly just for my own learning, and for me to run my own instance for educational purposes, nothing more. I would suggest using Padtrack's bot, not running your own, unless you really like the challenge and want to learn.

# Track

A discord bot focused on World Of Warships, written in Python.
Contact @Trackpad#1234 for issues.


# Setup

You can invite the original version of the Padtrack's bot [here](https://discordapp.com/oauth2/authorize?client_id=633110582865952799&scope=bot&permissions=388160). The following instructions are only if you want to set up your own instance:

1. Create a new Python >3.6 [venv](https://docs.python.org/3/library/venv.html), and install dependencies with `pip install -U -r requirements.txt`. 
2. Populate `assets/private` with the following files using the [WoWS unpacker tool](https://forum.worldofwarships.eu/topic/113847-all-wows-unpack-tool-unpack-game-client-resources/):
    - GameParams.data, located in `res/content`. Use it with `scripts/GameParams/dump.py` to generate `gameparams.db`.
    - ship_bars, located in `res/gui`.
    - spaces, located in `res`.
    - big, located in `res/gui/crew_commander/skills`.

    Finally, copy global.mo for the language you intend to use.

3. Generate `rush.db` by running `scripts/dump.py` with `rush.txt` from [Michael Fogleman's](https://www.michaelfogleman.com/rush/) Rush Hour solution.

4. Create a `config.py` file with `config_template.py` as a template.

5. Run `scripts/setup.py`.

6. Install the `Trebuchet MS` font.

7. Start the bot by run `bot.py`!


# Dependencies

This uses a slightly modified version of replays_unpack by Monstrofil, available [here](https://github.com/Monstrofil/replays_unpack). The modifications were done primarily to the battle_controller.py file, and are available in the fork [here](https://github.com/Monstrofil/replays_unpack).

# Dockerfile

I made a Dockerfile that allows you to run an instance of this rather simply, please see the repo for that, [here](https://github.com/chemputer/track-docker). If you have any suggestions on how I can improve, please let me know.
# Have suggestions or need more help?
[Join the support discord!](https://discord.gg/dU39sjq)

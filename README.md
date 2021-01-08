# Track

A discord bot focused on World Of Warships, written in Python.
Contact @Trackpad#1234 for issues.


# Setup

You can invite the bot [here](https://discordapp.com/oauth2/authorize?client_id=633110582865952799&scope=bot&permissions=388160). The following instructions are only if you want to set up your own instance:

1. Create a new Python >3.6 [venv](https://docs.python.org/3/library/venv.html), and install dependencies with `pip install -U -r requirements.txt`. In addition, install `discord-ext-menus` with:
    ```
    python -m pip install -U git+https://github.com/Rapptz/discord-ext-menus
    ```

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

# Have suggestions or need more help?
[Join the support discord!](https://discord.gg/dU39sjq)

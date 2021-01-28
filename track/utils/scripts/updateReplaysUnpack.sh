#!/bin/sh
cd ..
for d in replays_unpack/replay_unpack/clients/wows/versions/*/; do
    cp utils/battle_controller.py $d/
done
cd ..
foreach ($d in (dir replays_unpack\replay_unpack\clients\wows\versions)){ if ($d -ne "__init__.py") {cp .\utils\battle_controller.py replays_unpack\replay_unpack\clients\wows\versions\$d\}}
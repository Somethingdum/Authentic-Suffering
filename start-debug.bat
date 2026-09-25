@echo off
set TALEMATE_DEBUG=1
start cmd /k "cd talemate_env\Scripts && activate && cd ../../ && python src\talemate\server\run.py runserver --host 127.0.0.1 --port 5050"
if "%TALEMATE_FRONTEND_PORT%"=="" set TALEMATE_FRONTEND_PORT=8082
set COREPACK_ENABLE_DOWNLOAD_PROMPT=0
start cmd /k "cd talemate_frontend && corepack pnpm run serve --host 127.0.0.1 --port %TALEMATE_FRONTEND_PORT%"
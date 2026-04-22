#!/bin/bash
# Starta dev-server med loggning till dev.log
# Användning: ./dev.sh [lösenord]
# Eller sätt ADMIN_PASSWORD_HASH i .env

set -a
[ -f .env ] && source .env
set +a

if [ -z "$ADMIN_PASSWORD_HASH" ]; then
  PASS="${1:-test}"
  export ADMIN_PASSWORD_HASH=$(python3 -c "import bcrypt; print(bcrypt.hashpw(b'$PASS', bcrypt.gensalt()).decode())")
  echo "Adminlösenord: $PASS"
fi

~/.local/bin/uv run uvicorn app.main:app --host 0.0.0.0 --reload 2>&1 | tee dev.log

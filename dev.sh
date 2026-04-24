#!/bin/bash
# Starta dev-server med loggning till dev.log
# Användning: ./dev.sh [-seed] [lösenord]
# Eller sätt ADMIN_PASSWORD_HASH i .env
# -seed: rensar databasen och skapar testdata vid uppstart

set -a
[ -f .env ] && source .env
set +a

SEED=false
ARGS=()
for arg in "$@"; do
  if [ "$arg" = "-seed" ]; then
    SEED=true
  else
    ARGS+=("$arg")
  fi
done

if [ -z "$ADMIN_PASSWORD_HASH" ]; then
  PASS="${ARGS[0]:-test}"
  export ADMIN_PASSWORD_HASH=$(python3 -c "import bcrypt; print(bcrypt.hashpw(b'$PASS', bcrypt.gensalt()).decode())")
  echo "Adminlösenord: $PASS"
fi

if [ "$SEED" = true ]; then
  export DEV_SEED=true
  echo "DEV_SEED aktiverat — databasen rensas och testdata skapas vid uppstart"
fi

~/.local/bin/uv run uvicorn app.main:app --host 0.0.0.0 --reload 2>&1 | tee dev.log

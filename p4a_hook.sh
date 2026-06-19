#!/bin/bash

if [ "$1" = "prebuild" ]; then
    RECIPE="$2"
    if [ "$RECIPE" = "reportlab" ]; then
        echo "[HOOK] reportlab prebuild: removing _rl_accel C extension"
        rm -rf src/rl_addons/rl_accel 2>/dev/null && echo "[HOOK] removed _rl_accel dir" || echo "[HOOK] _rl_accel dir not found"
        sed -i '/rl_accel/d' setup.py 2>/dev/null && echo "[HOOK] patched setup.py"
    fi
fi
exit 0

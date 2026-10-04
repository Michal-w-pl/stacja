#!/bin/sh
# Name: Stacja pogody
# Author: Ja

# ====== USTAWIENIA ======
URL="https://TWOJ-LOGIN.github.io/stacja/stacja.png"
CO_ILE=1800          # odświeżanie co 30 minut (w sekundach)
# ========================

FBINK=/mnt/us/libkh/bin/fbink
IMG=/tmp/stacja.png
LOG=/mnt/us/stacja.log

# --- 1. uruchomienie z biblioteki: odpal pętlę w tle i wyjdź ---
if [ "$1" != "run" ]; then
    echo "Uruchamiam stacje pogody..."
    echo "Wyjscie: przytrzymaj przycisk zasilania ok. 40 s"
    nohup sh "$0" run >/dev/null 2>&1 &
    sleep 3
    exit 0
fi

log() { echo "$(date '+%Y-%m-%d %H:%M:%S') $*" >> "$LOG"; }

wifi_on() {
    lipc-set-prop com.lab126.cmd wirelessEnable 1
    i=0
    while [ $i -lt 40 ]; do
        [ "$(lipc-get-prop com.lab126.wifid cmState 2>/dev/null)" = "CONNECTED" ] && return 0
        sleep 1
        i=$((i + 1))
    done
    return 1
}

wifi_off() { lipc-set-prop com.lab126.cmd wirelessEnable 0; }

pobierz() {
    rm -f "$IMG.new"
    if command -v curl >/dev/null 2>&1; then
        curl -fsSk -m 60 -o "$IMG.new" "$URL?t=$(date +%s)"
    else
        wget -q -T 60 -O "$IMG.new" "$URL?t=$(date +%s)"
    fi
    [ -s "$IMG.new" ] && mv "$IMG.new" "$IMG"
}

pokaz() {
    if [ -s "$IMG" ]; then
        $FBINK -q -c -f -g file="$IMG" || eips -f -g "$IMG"
    fi
    BAT=$(gasgauge-info -c 2>/dev/null)
    [ -n "$BAT" ] && $FBINK -q -y -2 -m "Bateria: $BAT" 2>/dev/null
    [ -n "$1" ] && $FBINK -q -y -1 -m "$1" 2>/dev/null
}

log "Start stacji"

# --- 2. wyłącz wygaszacz i interfejs Kindle'a, żeby nie zamalowywał obrazka ---
lipc-set-prop com.lab126.powerd preventScreenSaver 1
stop lab126_gui 2>/dev/null || /etc/init.d/framework stop 2>/dev/null
sleep 5

# --- 3. pętla główna ---
while true; do
    if wifi_on && pobierz; then
        log "OK"
        pokaz ""
    else
        log "Blad pobierania (wifi: $(lipc-get-prop com.lab126.wifid cmState 2>/dev/null))"
        pokaz "Brak polaczenia - sprobuje ponownie"
    fi
    wifi_off
    sleep "$CO_ILE"
done

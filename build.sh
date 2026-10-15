#!/bin/sh
# Snaplens.app (PyInstaller, snaplens.spec) -> installer/Snaplens-<version>.dmg (dmgbuild, dmg.py), and installed in
# /Applications (one running from there quits for it and starts again).
# Signed by this Mac's own "Snaplens Local Signing" certificate (made here the first time, kept in the login keychain):
# Screen Recording, granted once, holds for every build signed by it. No Developer ID: on another Mac the first open
# is right-click > Open.
set -e
cd "$(dirname "$0")"
SIGNER="Snaplens Local Signing"
VER=$(sed -n 's/^VERSION = "\(.*\)".*/\1/p' snaplens/config.py)

if ! security find-certificate -c "$SIGNER" >/dev/null 2>&1; then  # self-signed, for code signing; codesign alone may use it
    tmp=$(mktemp -d)
    printf '[req]\ndistinguished_name=dn\nx509_extensions=ext\nprompt=no\n[dn]\nCN=%s\n[ext]\nbasicConstraints=critical,CA:false\nkeyUsage=critical,digitalSignature\nextendedKeyUsage=critical,codeSigning\n' "$SIGNER" > "$tmp/cert.cnf"
    /usr/bin/openssl req -x509 -newkey rsa:2048 -nodes -keyout "$tmp/key.pem" -out "$tmp/cert.pem" -days 3650 -config "$tmp/cert.cnf" 2>/dev/null
    /usr/bin/openssl pkcs12 -export -inkey "$tmp/key.pem" -in "$tmp/cert.pem" -name "$SIGNER" -out "$tmp/id.p12" -passout pass:snaplens
    security import "$tmp/id.p12" -k ~/Library/Keychains/login.keychain-db -P snaplens -T /usr/bin/codesign
    rm -rf "$tmp"
fi
ID=$(security find-identity -p codesigning | awk -v s="\"$SIGNER\"" 'index($0, s) {print $2; exit}')  # (untrusted: by hash)

.venv/bin/python -c "from snaplens.ocr.engine import warmup; warmup()"  # the models into rapidocr/models, to be bundled
.venv/bin/pyinstaller --noconfirm --log-level WARN snaplens.spec
codesign --force --deep --sign "$ID" dist/Snaplens.app
mkdir -p installer
rm -f "installer/Snaplens-$VER.dmg"
.venv/bin/dmgbuild -s dmg.py -D app=dist/Snaplens.app Snaplens "installer/Snaplens-$VER.dmg"  # the app, a drag to Applications
echo "installer/Snaplens-$VER.dmg"

APP=/Applications/Snaplens.app
was=""
# by the executable it runs, not its argv (pkill -f): launchd's copy is plain "Snaplens --startup". 0.16.0: MacOS/smartshot
pids=$(lsof -t -a -d txt "$APP/Contents/MacOS/Snaplens" "$APP/Contents/MacOS/smartshot" 2>/dev/null || true)
if [ -n "$pids" ]; then  # its files are about to be replaced
    was=1
    kill $pids
    for p in $pids; do while kill -0 "$p" 2>/dev/null; do sleep .2; done; done
fi
rm -rf "$APP"
ditto dist/Snaplens.app "$APP"
[ -z "$was" ] || open "$APP"
echo "$APP"

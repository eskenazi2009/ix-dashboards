# -*- coding: utf-8 -*-
"""
"Buzon" cifrado entre la rutina de Claude en la nube y GitHub Actions.

La rutina (8 am Panama) lee por el conector de Microsoft 365 los correos
"Descargable de Ventas" del portal de IX y saca los enlaces .xlsx. No puede
bajar archivos ni tiene la clave del sitio, asi que deja los enlaces en
inbox/ix-<sello>.enc, cifrados con la LLAVE PUBLICA (cloud/inbox_pub.pem).
Solo GitHub Actions, que tiene la llave privada (secret INBOX_PRIV), los abre,
baja los Excel y actualiza los .enc del sitio (cloud/procesar_inbox.py).
Asi en el repo publico nunca queda un enlace en claro (los .xlsx traen ventas).

  python3 cloud/inbox.py encolar --rango 2026-09-26 2026-09-28 URL [URL ...]
      -> escribe inbox/ix-YYYYMMDD-HHMMSS.enc  (lo usa la rutina)
  python3 cloud/inbox.py abrir inbox/ix-....enc   -> imprime el JSON (requiere INBOX_PRIV)

Cifrado hibrido: llave AES-256 al azar, cifrada con RSA-OAEP(SHA-256); payload
con AES-GCM. Formato: [2 bytes len][llave RSA][12 iv][ciphertext].
"""
import datetime, json, os, secrets, struct, sys
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.dirname(HERE)
INBOX = os.path.join(SITE, "inbox")
OAEP = padding.OAEP(mgf=padding.MGF1(algorithm=hashes.SHA256()), algorithm=hashes.SHA256(), label=None)

def encolar(obj):
    pub = serialization.load_pem_public_key(open(os.path.join(HERE, "inbox_pub.pem"), "rb").read())
    k = AESGCM.generate_key(256); iv = secrets.token_bytes(12)
    ek = pub.encrypt(k, OAEP)
    ct = AESGCM(k).encrypt(iv, json.dumps(obj, ensure_ascii=False).encode("utf-8"), None)
    os.makedirs(INBOX, exist_ok=True)
    path = os.path.join(INBOX, "ix-%s.enc" % datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d-%H%M%S"))
    open(path, "wb").write(struct.pack(">H", len(ek)) + ek + iv + ct)
    return path

def abrir(path):
    pem = os.environ.get("INBOX_PRIV") or sys.exit("falta INBOX_PRIV")
    priv = serialization.load_pem_private_key(pem.encode() if isinstance(pem, str) else pem, password=None)
    b = open(path, "rb").read(); n = struct.unpack(">H", b[:2])[0]
    k = priv.decrypt(b[2:2 + n], OAEP); iv = b[2 + n:14 + n]
    return json.loads(AESGCM(k).decrypt(iv, b[14 + n:], None).decode("utf-8"))

if __name__ == "__main__":
    a = sys.argv[1:]
    if a[:1] == ["encolar"]:
        rango = None
        if "--rango" in a:
            i = a.index("--rango"); rango = [a[i + 1], a[i + 2]]; a = a[:i] + a[i + 3:]
        urls = [u for u in a[1:] if u.startswith("https://")]
        if not urls: sys.exit("no hay URLs")
        p = encolar({"urls": urls, "rango": rango, "ts": datetime.datetime.now(datetime.timezone.utc).isoformat()})
        print("encolado", os.path.relpath(p, SITE), "|", len(urls), "enlaces | rango", rango)
    elif a[:1] == ["abrir"]:
        print(json.dumps(abrir(a[1]), ensure_ascii=False, indent=1))
    else:
        sys.exit(__doc__)

# -*- coding: utf-8 -*-
"""
GitHub Actions: abre cada sobre de inbox/*.enc (enlaces .xlsx que dejo la rutina
de Claude), baja los exports, actualiza ventas-ix.enc y ventas-macro.enc y borra
el sobre. Requiere INBOX_PRIV (llave privada del buzon) e IX_CLAVE (clave del sitio).
"""
import glob, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); SITE = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import inbox, sync_ix

sobres = sorted(glob.glob(os.path.join(SITE, "inbox", "*.enc")))
if not sobres:
    print("inbox vacio"); sys.exit(0)
for p in sobres:
    try:
        d = inbox.abrir(p)
    except Exception as e:
        print("no pude abrir", os.path.basename(p), ":", e); continue
    print("sobre", os.path.basename(p), "|", len(d["urls"]), "enlaces | rango", d.get("rango"))
    ok = True
    try:
        sync_ix.cargar(d["urls"], tuple(d["rango"]) if d.get("rango") else None)
    except Exception as e:
        ok = False; print("  ERROR cargando:", e)
    if ok: os.remove(p); print("  sobre procesado y borrado")

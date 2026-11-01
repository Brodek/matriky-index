// Digitální badatelna Zemského archivu v Opavě (digi.archives.cz): zjištění cest k obrázkům snímků knihy.
// Katalog je za ochranou proti robotům, proto se cesty čtou v běžném prohlížeči. Postup: otevřít knihu, na záložce
// obrázků kliknout na první náhled (otevře se prohlížeč snímku), vložit tento soubor do konzole a zavolat
// `await zaoCesty(od, do)`. Výsledek {snímek: cesta} uložit jako JSON a stáhnout obrázky přes tools/scan/zaopava.py.

function zaoCesta() {
  const n = performance.getEntriesByType("resource").map(e => e.name).filter(u => u.includes("images.archives.cz"));
  const m = n.length ? new URL(n[n.length - 1]).pathname.match(/zoomify\/cz\/archives\/(.+?\.jpg)\//) : null;
  return m ? m[1] : null;
}

// Přejde v prohlížeči na snímek k (pole „Jdi na“) a vrátí cestu k jeho obrázku. Seznam načtených souborů se před
// skokem maže: prohlížeč jich jinak drží jen 150 a dlaždice ho rychle zaplní.
async function zaoJdi(k) {
  performance.setResourceTimingBufferSize(5000);
  performance.clearResourceTimings();
  const inp = document.getElementById("getScanInputSend");
  inp.focus();
  inp.value = String(k);
  for (const t of ["keydown", "keypress", "keyup"])
    inp.dispatchEvent(new KeyboardEvent(t, {key: "Enter", code: "Enter", keyCode: 13, which: 13, bubbles: true}));
  for (let i = 0; i < 40; i++) {
    await new Promise(r => setTimeout(r, 300));
    const p = zaoCesta();
    if (p) return p;
  }
  return null;
}

// Cesty snímků od–do; mezi snímky čeká 2 s, aby portál nezatěžoval.
async function zaoCesty(od, doKonce) {
  const out = {};
  for (let k = od; k <= doKonce; k++) {
    out[k] = await zaoJdi(k);
    await new Promise(r => setTimeout(r, 2000));
  }
  return out;
}

// Abre la página REAL de boe.es de una norma en Chrome headless (CDP), comprueba que el pasaje existe
// literalmente en su texto, lo subraya con <mark> en el DOM y captura la pantalla.
// Uso: node scripts/capturar_boe.mjs <BOE-A-xxxx> <ancla> "<pasaje literal>" <salida.png> [url-alternativa]
import { spawn } from "node:child_process";
import { mkdirSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";

const [id, ancla, pasaje, salida, urlAlt] = process.argv.slice(2);
const chrome = resolve("node_modules/.remotion/chrome-headless-shell/win64/chrome-headless-shell-win64/chrome-headless-shell.exe");
const port = 9333;
const proc = spawn(chrome, ["--no-sandbox", "--hide-scrollbars", `--remote-debugging-port=${port}`, "--window-size=1500,1000", "about:blank"], { stdio: "ignore" });
const espera = (ms) => new Promise((r) => setTimeout(r, ms));

try {
  let targets;
  for (let i = 0; i < 40; i++) {
    try { targets = await (await fetch(`http://127.0.0.1:${port}/json`)).json(); break; } catch { await espera(250); }
  }
  const ws = new WebSocket(targets.find((t) => t.type === "page").webSocketDebuggerUrl);
  await new Promise((r) => (ws.onopen = r));
  let n = 0;
  const pend = new Map();
  ws.onmessage = (m) => { const d = JSON.parse(m.data); if (d.id && pend.has(d.id)) { pend.get(d.id)(d); pend.delete(d.id); } };
  const cdp = (method, params = {}) => new Promise((res) => { const i = ++n; pend.set(i, res); ws.send(JSON.stringify({ id: i, method, params })); });

  await cdp("Page.enable");
  await cdp("Emulation.setDeviceMetricsOverride", { width: 1500, height: 1000, deviceScaleFactor: 1, mobile: false });
  const url = urlAlt ?? `https://www.boe.es/buscar/act.php?id=${id}`;
  await cdp("Page.navigate", { url });
  await espera(9000); // carga completa (CSS y JS de la propia página del BOE)

  const expr = `(function(a,p){
    const el = document.getElementById(a); if(!el) return 'sin-ancla';
    const w = document.createTreeWalker(el, NodeFilter.SHOW_TEXT); let n, hit=null;
    while((n=w.nextNode())){ const i=n.nodeValue.indexOf(p); if(i>=0){hit=[n,i];break;} }
    if(!hit) return 'sin-pasaje';
    const r=document.createRange(); r.setStart(hit[0],hit[1]); r.setEnd(hit[0],hit[1]+p.length);
    const m=document.createElement('mark'); m.style.cssText='background:#F1DC93;padding:2px 3px;border-radius:4px;color:#000';
    r.surroundContents(m); m.scrollIntoView({block:'center'}); return 'ok';
  })(${JSON.stringify(ancla)}, ${JSON.stringify(pasaje)})`;
  const sinMarca = expr.replace("background:#F1DC93;padding:2px 3px;border-radius:4px;color:#000", "background:transparent;color:inherit;padding:0");
  const r = await cdp("Runtime.evaluate", { expression: process.env.SIN_MARCA ? sinMarca : expr, returnByValue: true });
  const val = r.result?.result?.value;
  if (val !== "ok") throw new Error(`No se pudo subrayar el pasaje en la página real del BOE: ${val}`);
  await espera(800);
  const shot = await cdp("Page.captureScreenshot", { format: "png" });
  mkdirSync(dirname(resolve(salida)), { recursive: true });
  writeFileSync(resolve(salida), Buffer.from(shot.result.data, "base64"));
  console.log(`OK ${salida} · fuente ${url}#${ancla} · pasaje literal comprobado en el DOM real`);
  ws.close();
} finally {
  proc.kill();
}

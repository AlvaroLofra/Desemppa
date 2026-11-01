// Sintetiza la música (~58 s) y los efectos de Desemppa por código: sin bancos de sonido ni descargas.
// Los instantes de los efectos y las duraciones salen de src/linea.json (la misma fuente que usa Composition.tsx).
// Uso: node audio/generar_audio.mjs → escribe public/audio/*.wav y comprueba el pico de la mezcla simulada.
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const SR = 44100;
const aqui = dirname(fileURLToPath(import.meta.url));
const linea = JSON.parse(readFileSync(join(aqui, "..", "src", "linea.json"), "utf8"));
const out = join(aqui, "..", "public", "audio");
mkdirSync(out, { recursive: true });

const { fps, transicion, duraciones, sfx } = linea;
const inicios = duraciones.map((_, i) => duraciones.slice(0, i).reduce((a, b) => a + b, 0) - i * transicion);
const totalFrames = duraciones.reduce((a, b) => a + b, 0) - (duraciones.length - 1) * transicion;
const DUR = totalFrames / fps;

const buf = (s) => new Float32Array(Math.round(s * SR));
const hz = (midi) => 440 * 2 ** ((midi - 69) / 12);
const TAU = Math.PI * 2;
let seed = 12345;
const rnd = () => ((seed = (seed * 1664525 + 1013904223) >>> 0) / 4294967296) * 2 - 1;

function wav(name, data) {
  const pcm = Buffer.alloc(44 + data.length * 2);
  pcm.write("RIFF", 0); pcm.writeUInt32LE(36 + data.length * 2, 4); pcm.write("WAVEfmt ", 8);
  pcm.writeUInt32LE(16, 16); pcm.writeUInt16LE(1, 20); pcm.writeUInt16LE(1, 22);
  pcm.writeUInt32LE(SR, 24); pcm.writeUInt32LE(SR * 2, 28); pcm.writeUInt16LE(2, 32); pcm.writeUInt16LE(16, 34);
  pcm.write("data", 36); pcm.writeUInt32LE(data.length * 2, 40);
  for (let i = 0; i < data.length; i++) pcm.writeInt16LE(Math.round(Math.max(-1, Math.min(1, data[i])) * 32767), 44 + i * 2);
  writeFileSync(join(out, name), pcm);
}
const peak = (d) => d.reduce((m, v) => Math.max(m, Math.abs(v)), 0);
const normalize = (d, p) => { const k = p / peak(d); for (let i = 0; i < d.length; i++) d[i] *= k; return d; };
const fadeEnds = (d, a, b) => {
  for (let i = 0; i < d.length; i++) {
    const t = i / SR, T = d.length / SR;
    d[i] *= Math.min(1, t / a) * Math.min(1, (T - t) / b);
  }
  return d;
};

// ---------- Música: 96 BPM, Cmaj7 · Am7 · Fmaj7 · G6 en bucle y cadencia final ----------
function musica() {
  const d = buf(DUR), beat = 60 / 96, bar = 4 * beat;
  const acordes = [[48, 52, 55, 59], [45, 48, 52, 55], [41, 45, 48, 52], [43, 47, 50, 52]];
  const final = [48, 52, 55, 62];
  const nBars = Math.ceil(DUR / bar);
  const add = (t0, dur, f, amp, tipo) => {
    const i0 = Math.floor(t0 * SR), n = Math.floor(dur * SR);
    for (let k = 0; k < n && i0 + k < d.length; k++) {
      const t = k / SR;
      let env;
      if (tipo === "pad") env = Math.min(1, t / 0.7) * Math.min(1, (dur - t) / 0.9);
      else if (tipo === "pluck") env = Math.exp(-t * 7) * Math.min(1, t / 0.004);
      else env = Math.min(1, t / 0.03) * Math.exp(-t * 2.4);
      const ph = TAU * f * t;
      let v;
      if (tipo === "pad") v = (Math.sin(ph) + 0.5 * Math.sin(ph * 1.004) + 0.25 * Math.sin(ph * 2.003) + 0.12 * Math.sin(ph * 3)) / 1.9;
      else if (tipo === "pluck") v = Math.sin(ph) + 0.35 * Math.sin(2 * ph) + 0.1 * Math.sin(3 * ph);
      else v = Math.sin(ph);
      d[i0 + k] += v * env * amp;
    }
  };
  // la intensidad sube hasta el 70 % del vídeo y se suaviza al final
  const intensidad = (t) => Math.min(1, t / (DUR * 0.7)) * (t > DUR - 8 ? Math.max(0.55, (DUR - t) / 8 + 0.4) : 1);
  for (let b = 0; b < nBars; b++) {
    const t0 = b * bar;
    const ult = t0 + bar >= DUR - 3;
    const ac = ult ? final : acordes[b % 4];
    ac.forEach((m) => add(t0, bar + 0.6, hz(m), 0.11, "pad"));
    add(t0, bar, hz(ac[0] - 12), 0.28, "bass");
    for (let s = 0; s < 8; s++) {
      const t = t0 + (s * beat) / 2;
      if (t < 3 || t > DUR - 3 || ult) continue;
      const nota = ac[[0, 1, 2, 3, 2, 1, 3, 2][s]] + 24;
      add(t, 0.5, hz(nota), 0.04 + 0.07 * intensidad(t), "pluck");
    }
    for (let s = 0; s < 4; s++) {
      const t = t0 + s * beat;
      if (t < 8 || t > DUR - 4 || ult) continue;
      const i0 = Math.floor(t * SR);
      for (let k = 0; k < 0.18 * SR && i0 + k < d.length; k++) {
        const tt = k / SR;
        d[i0 + k] += Math.sin(TAU * (50 + 90 * Math.exp(-tt * 30)) * tt) * Math.exp(-tt * 18) * 0.18 * intensidad(t);
      }
    }
  }
  return fadeEnds(normalize(d, 0.4), 0.3, 2.6);
}

// ---------- Efectos ----------
function typing() {
  const d = buf(3.2), paso = 0.065;
  for (let c = 0; c < 46; c++) {
    const i0 = Math.floor((0.02 + c * paso) * SR), f = 1500 + 400 * ((c * 7) % 5);
    for (let k = 0; k < 0.03 * SR; k++) {
      const t = k / SR;
      d[i0 + k] += (rnd() * 0.5 + Math.sin(TAU * f * t)) * Math.exp(-t * 180) * 0.35;
    }
  }
  return normalize(d, 0.26);
}
function whoosh() {
  const d = buf(0.5); let lp = 0;
  for (let i = 0; i < d.length; i++) {
    const x = i / SR / 0.5;
    lp += (rnd() - lp) * Math.min(1, ((300 + 3500 * Math.sin(Math.PI * x) ** 1.5) / SR) * TAU);
    d[i] = lp * Math.sin(Math.PI * x) ** 2;
  }
  return normalize(d, 0.26);
}
function tono(dur, partes, decay, ataque = 0.002) {
  const d = buf(dur);
  for (let i = 0; i < d.length; i++) {
    const t = i / SR;
    let v = 0;
    for (const [f, a] of partes) v += Math.sin(TAU * f * t) * a;
    d[i] = v * Math.exp(-t * decay) * Math.min(1, t / ataque);
  }
  return d;
}
const tick = () => normalize(tono(0.12, [[1500, 1], [3000, 0.3]], 45), 0.26);
const chip = () => normalize(tono(0.16, [[660, 1], [990, 0.4]], 28, 0.006), 0.2);
const ding = () => fadeEnds(normalize(tono(1.0, [[1318.5, 1], [1975.5, 0.5], [2637, 0.2]], 4.2), 0.32), 0.001, 0.2);
function bell() {
  const d = tono(2.0, [[523.25, 1], [1046.5, 0.5], [1568, 0.35], [2093, 0.18], [1318, 0.12]], 2.6, 0.003);
  const thump = tono(0.4, [[110, 1]], 9, 0.004);
  for (let i = 0; i < thump.length; i++) d[i] += thump[i] * 0.6;
  return fadeEnds(normalize(d, 0.42), 0.001, 0.5);
}

const ficheros = { "musica.wav": musica(), "typing.wav": typing(), "whoosh.wav": whoosh(), "tick.wav": tick(), "chip.wav": chip(), "ding.wav": ding(), "bell.wav": bell() };
for (const [n, d] of Object.entries(ficheros)) wav(n, d);

// ---------- Comprobación de la mezcla (mismos instantes y volúmenes que Composition.tsx) ----------
const mix = new Float32Array(Math.ceil(DUR * SR));
ficheros["musica.wav"].forEach((v, i) => (mix[i] += v));
for (const s of sfx) {
  const f0 = inicios[s.e - 1] + s.f;
  ficheros[s.file].forEach((v, i) => { const j = Math.round((f0 / fps) * SR) + i; if (j < mix.length) mix[j] += v * s.vol; });
}
const p = peak(mix);
console.log(`Duración ${DUR.toFixed(2)} s · pico de la mezcla ${p.toFixed(3)} (${(20 * Math.log10(p)).toFixed(1)} dBFS)`);
for (const [n, d] of Object.entries(ficheros)) console.log(n.padEnd(12), (d.length / SR).toFixed(2) + " s", "pico", peak(d).toFixed(2));
if (p > 0.95) { console.error("CLIPPING: baja la ganancia"); process.exit(1); }
const colaFinal = peak(mix.subarray(mix.length - Math.round(0.05 * SR)));
console.log(`Nivel en los últimos 50 ms: ${colaFinal.toFixed(4)} (fade-out)`);

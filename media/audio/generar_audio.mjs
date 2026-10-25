// Sintetiza la música y los efectos de Desemppa (sin bancos de sonido ni descargas).
// Uso: node audio/generar_audio.mjs   → escribe public/audio/*.wav y comprueba el pico de la mezcla.
import { mkdirSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const SR = 44100;
const FPS = 30;
const out = join(dirname(fileURLToPath(import.meta.url)), "..", "public", "audio");
mkdirSync(out, { recursive: true });

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

// ---------- Música: 10 s, 96 BPM, Cmaj7 · Am7 · Fmaj7 · Cadd9 ----------
function musica() {
  const d = buf(10), beat = 60 / 96, bar = 4 * beat;
  const acordes = [[48, 52, 55, 59], [45, 48, 52, 55], [41, 45, 48, 52], [48, 52, 55, 62]];
  const add = (t0, dur, f, amp, tipo) => {
    const i0 = Math.floor(t0 * SR), n = Math.floor(dur * SR);
    for (let k = 0; k < n && i0 + k < d.length; k++) {
      const t = k / SR;
      let env;
      if (tipo === "pad") env = Math.min(1, t / 0.6) * Math.min(1, (dur - t) / 0.7);
      else if (tipo === "pluck") env = Math.exp(-t * 7) * Math.min(1, t / 0.004);
      else env = Math.min(1, t / 0.03) * Math.exp(-t * 3);
      const ph = TAU * f * t;
      let v;
      if (tipo === "pad") v = (Math.sin(ph) + 0.5 * Math.sin(ph * 1.004) + 0.25 * Math.sin(ph * 2.003) + 0.12 * Math.sin(ph * 3)) / 1.9;
      else if (tipo === "pluck") v = Math.sin(ph) + 0.35 * Math.sin(2 * ph) + 0.1 * Math.sin(3 * ph);
      else v = Math.sin(ph);
      d[i0 + k] += v * env * amp;
    }
  };
  acordes.forEach((ac, b) => {
    const t0 = b * bar;
    ac.forEach((m) => add(t0, bar + 0.5, hz(m), 0.12, "pad"));
    add(t0, bar, hz(ac[0] - 12), 0.3, "bass");
    // arpegio de corcheas una octava arriba; entra a partir del segundo 1,25 y crece hasta la placa 3
    for (let s = 0; s < 8; s++) {
      const t = t0 + s * beat / 2;
      if (t < 1.25 || t > 9.0) continue;
      const nota = ac[[0, 1, 2, 3, 2, 1, 3, 2][s]] + 24;
      add(t, 0.5, hz(nota), 0.06 + 0.07 * Math.min(1, t / 5), "pluck");
    }
    // pulso discreto en cada negra desde la placa 2
    for (let s = 0; s < 4; s++) {
      const t = t0 + s * beat;
      if (t < 2.0 || t > 9.0) continue;
      const i0 = Math.floor(t * SR);
      for (let k = 0; k < 0.18 * SR && i0 + k < d.length; k++) {
        const tt = k / SR;
        d[i0 + k] += Math.sin(TAU * (50 + 90 * Math.exp(-tt * 30)) * tt) * Math.exp(-tt * 18) * 0.22;
      }
    }
  });
  return fadeEnds(normalize(d, 0.42), 0.15, 0.9);
}

// ---------- Efectos ----------
function typing() {
  const d = buf(1.2), paso = 0.0967;
  for (let c = 0; c < 12; c++) {
    const i0 = Math.floor((0.02 + c * paso) * SR), f = 1500 + 400 * ((c * 7) % 5);
    for (let k = 0; k < 0.03 * SR; k++) {
      const t = k / SR;
      d[i0 + k] += (rnd() * 0.5 + Math.sin(TAU * f * t)) * Math.exp(-t * 180) * 0.35;
    }
  }
  return normalize(d, 0.3);
}
function whoosh() {
  const d = buf(0.45); let lp = 0;
  for (let i = 0; i < d.length; i++) {
    const t = i / SR, x = t / 0.45;
    const a = 0.02 + 0.5 * Math.sin(Math.PI * x) ** 2 * (1 - 0.3 * x);
    lp += (rnd() - lp) * Math.min(1, (300 + 3500 * Math.sin(Math.PI * x) ** 1.5) / SR * TAU);
    d[i] = lp * Math.sin(Math.PI * x) ** 2;
  }
  return normalize(d, 0.28);
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
const tick = () => normalize(tono(0.12, [[1500, 1], [3000, 0.3]], 45), 0.28);
const chip = () => normalize(tono(0.16, [[660, 1], [990, 0.4]], 28, 0.006), 0.22);
const ding = () => fadeEnds(normalize(tono(1.0, [[1318.5, 1], [1975.5, 0.5], [2637, 0.2]], 4.2), 0.34), 0.001, 0.2);
function bell() {
  const d = tono(1.05, [[523.25, 1], [1046.5, 0.5], [1568, 0.35], [2093, 0.18], [1318, 0.12]], 3.2, 0.003);
  const thump = tono(0.4, [[110, 1]], 9, 0.004);
  for (let i = 0; i < thump.length; i++) d[i] += thump[i] * 0.6;
  return fadeEnds(normalize(d, 0.45), 0.001, 0.25);
}

const ficheros = { "musica.wav": musica(), "typing.wav": typing(), "whoosh.wav": whoosh(), "tick.wav": tick(), "chip.wav": chip(), "ding.wav": ding(), "bell.wav": bell() };
for (const [n, d] of Object.entries(ficheros)) wav(n, d);

// ---------- Comprobación de la mezcla (mismos instantes que src/Composition.tsx) ----------
const SFX = [["typing.wav", 20], ["whoosh.wav", 54], ["tick.wav", 64], ["tick.wav", 75], ["tick.wav", 87], ["chip.wav", 98], ["chip.wav", 103],
  ["chip.wav", 108], ["whoosh.wav", 114], ["ding.wav", 160], ["whoosh.wav", 174], ["whoosh.wav", 219], ["tick.wav", 227], ["tick.wav", 237],
  ["whoosh.wav", 254], ["bell.wav", 268]];
const mix = new Float32Array(10 * SR);
ficheros["musica.wav"].forEach((v, i) => (mix[i] += v));
for (const [n, f] of SFX) ficheros[n].forEach((v, i) => { const j = Math.round((f / FPS) * SR) + i; if (j < mix.length) mix[j] += v; });
const p = peak(mix);
console.log(`Pico de la mezcla: ${p.toFixed(3)} (${(20 * Math.log10(p)).toFixed(1)} dBFS)`);
if (p > 0.95) { console.error("CLIPPING: baja la ganancia"); process.exit(1); }
for (const [n, d] of Object.entries(ficheros)) console.log(n.padEnd(12), (d.length / SR).toFixed(2) + " s", "pico", peak(d).toFixed(2));

import { AbsoluteFill, Sequence } from "remotion";
import { Audio } from "@remotion/media";
import { staticFile } from "remotion";
import { C, FPS } from "./theme";
import { Scene1 } from "./Scene1";
import { Scene2 } from "./Scene2";
import { Scene3 } from "./Scene3";
import { Scene4 } from "./Scene4";
import { Scene5 } from "./Scene5";
import { Scene6 } from "./Scene6";

// Placas: inicio y duración en frames (30 fps, 300 en total).
const PLACAS = [
  { n: 1, from: 0, d: 60, C: Scene1 },
  { n: 2, from: 60, d: 60, C: Scene2 },
  { n: 3, from: 120, d: 60, C: Scene3 },
  { n: 4, from: 180, d: 45, C: Scene4 },
  { n: 5, from: 225, d: 35, C: Scene5 },
  { n: 6, from: 260, d: 40, C: Scene6 },
];

// Efectos: fichero en public/audio/ y frame de inicio.
const SFX: { file: string; at: number; vol?: number }[] = [
  { file: "typing.wav", at: 20 },
  { file: "whoosh.wav", at: 54 },
  { file: "tick.wav", at: 64 },
  { file: "tick.wav", at: 75 },
  { file: "tick.wav", at: 87 },
  { file: "chip.wav", at: 98 },
  { file: "chip.wav", at: 103 },
  { file: "chip.wav", at: 108 },
  { file: "whoosh.wav", at: 114 },
  { file: "ding.wav", at: 160 },
  { file: "whoosh.wav", at: 174 },
  { file: "whoosh.wav", at: 219 },
  { file: "tick.wav", at: 227 },
  { file: "tick.wav", at: 237 },
  { file: "whoosh.wav", at: 254 },
  { file: "bell.wav", at: 268 },
];

export const Desemppa: React.FC = () => (
  <AbsoluteFill style={{ backgroundColor: C.bg }}>
    {PLACAS.map(({ n, from, d, C: Placa }) => (
      <Sequence key={n} name={`Placa ${n}`} from={from} durationInFrames={d}>
        <Placa />
      </Sequence>
    ))}
    <Audio src={staticFile("audio/musica.wav")} />
    {SFX.map((s, i) => (
      <Sequence key={i} name={`SFX ${s.file}`} from={s.at}>
        <Audio src={staticFile(`audio/${s.file}`)} volume={s.vol ?? 1} />
      </Sequence>
    ))}
  </AbsoluteFill>
);

export { FPS };

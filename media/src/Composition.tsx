import React from "react";
import { AbsoluteFill, Sequence, staticFile } from "remotion";
import { Audio } from "@remotion/media";
import { TransitionSeries, linearTiming } from "@remotion/transitions";
import { fade } from "@remotion/transitions/fade";

import { C } from "./theme";
import linea from "./linea.json";
import { Scene1 } from "./Scene1";
import { Scene2 } from "./Scene2";
import { Scene3 } from "./Scene3";
import { Scene4 } from "./Scene4";
import { Scene5 } from "./Scene5";
import { Scene6 } from "./Scene6";
import { Scene7 } from "./Scene7";
import { Scene8 } from "./Scene8";
import { Scene9 } from "./Scene9";
import { Scene10 } from "./Scene10";
import { Scene11 } from "./Scene11";

export const ESCENAS: React.FC[] = [Scene1, Scene2, Scene3, Scene4, Scene5, Scene6, Scene7, Scene8, Scene9, Scene10, Scene11];
export const DURACIONES: number[] = linea.duraciones;
export const TRANSICION = linea.transicion;

/** Frame global en el que empieza cada escena (las transiciones solapan escenas). */
export const INICIOS = DURACIONES.map((_, i) => DURACIONES.slice(0, i).reduce((a, b) => a + b, 0) - i * TRANSICION);
export const TOTAL = DURACIONES.reduce((a, b) => a + b, 0) - (DURACIONES.length - 1) * TRANSICION;

export const Desemppa: React.FC = () => (
  <AbsoluteFill style={{ backgroundColor: C.bg }}>
    <TransitionSeries>
      {ESCENAS.flatMap((E, i) => [
        <TransitionSeries.Sequence key={`s${i}`} durationInFrames={DURACIONES[i]}>
          <E />
        </TransitionSeries.Sequence>,
        ...(i < ESCENAS.length - 1
          ? [<TransitionSeries.Transition key={`t${i}`} presentation={fade()} timing={linearTiming({ durationInFrames: TRANSICION })} />]
          : []),
      ])}
    </TransitionSeries>

    <Audio src={staticFile("audio/musica.wav")} />
    {linea.sfx.map((s, i) => (
      <Sequence key={i} name={`SFX ${s.file} · escena ${s.e}`} from={INICIOS[s.e - 1] + s.f}>
        <Audio src={staticFile(`audio/${s.file}`)} volume={s.vol} />
      </Sequence>
    ))}
  </AbsoluteFill>
);

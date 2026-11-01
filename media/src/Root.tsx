import React from "react";
import { Composition, Folder } from "remotion";
import { Desemppa, DURACIONES, ESCENAS, TOTAL } from "./Composition";

export const RemotionRoot: React.FC = () => (
  <>
    <Composition id="Desemppa" component={Desemppa} durationInFrames={TOTAL} fps={30} width={1920} height={1080} />
    <Folder name="Placas">
      {ESCENAS.map((E, i) => (
        <Composition key={i} id={`Placa-${i + 1}`} component={E} durationInFrames={DURACIONES[i]} fps={30} width={1920} height={1080} />
      ))}
    </Folder>
  </>
);

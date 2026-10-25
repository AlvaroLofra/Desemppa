import { Composition } from "remotion";
import { Desemppa } from "./Composition";

export const RemotionRoot: React.FC = () => (
  <Composition id="Desemppa" component={Desemppa} durationInFrames={300} fps={30} width={1920} height={1080} />
);

import { Composition } from "remotion";
import { LoginBackground } from "./LoginBackground";

export const RemotionRoot = () => (
  <Composition
    id="LoginBackground"
    component={LoginBackground}
    durationInFrames={180}
    fps={30}
    width={1920}
    height={1080}
  />
);

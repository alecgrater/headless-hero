import React from "react";
import type { VisualCanvas } from "../types";

interface Props {
  canvas?: VisualCanvas | null;
}

export const StaticCanvas: React.FC<Props> = ({ canvas }) => {
  return (
    <div
      style={{
        position: "absolute",
        inset: 0,
        backgroundColor: canvas?.background_color ?? "#F6C54A",
      }}
    />
  );
};

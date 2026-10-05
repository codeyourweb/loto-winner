interface NumberBallProps {
  value: number;
  variant?: "default" | "chance" | "hit" | "chance-hit";
  size?: "sm" | "md" | "lg";
}

/** Number ball (played grid, draw, lucky number). */
export function NumberBall({ value, variant = "default", size = "md" }: NumberBallProps) {
  return (
    <span className={["ball", `ball-${variant}`, `ball-${size}`].join(" ")}>
      {value.toString().padStart(2, "0")}
    </span>
  );
}

export const motionTokens = {
  duration: { instant: 0, fast: 0.12, normal: 0.22, slow: 0.36 },
  easing: { standard: [0.2, 0, 0, 1] as const, emphasized: [0.16, 1, 0.3, 1] as const },
  spring: { snappy: { type: "spring" as const, stiffness: 480, damping: 38 }, smooth: { type: "spring" as const, stiffness: 260, damping: 32 } },
};
export const enter = { initial: { opacity: 0 }, animate: { opacity: 1 }, exit: { opacity: 0 } };

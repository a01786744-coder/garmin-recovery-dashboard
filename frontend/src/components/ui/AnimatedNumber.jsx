import React, { useEffect } from "react";
import { useMotionValue, useTransform, animate, motion, useReducedMotion } from "framer-motion";

// Counts up to `value` on mount/change. Renders DASH-like fallback when null.
export default function AnimatedNumber({ value, digits = 0, fallback = "—", className }) {
  const reduce = useReducedMotion();
  const mv = useMotionValue(0);
  const rounded = useTransform(mv, (v) =>
    digits ? Number(v).toFixed(digits) : String(Math.round(v))
  );

  useEffect(() => {
    if (value == null) return;
    if (reduce) {
      mv.set(value);
      return;
    }
    const controls = animate(mv, value, { duration: 0.9, ease: "easeOut" });
    return controls.stop;
  }, [value, reduce, mv]);

  if (value == null) return <span className={className}>{fallback}</span>;
  return <motion.span className={className}>{rounded}</motion.span>;
}

import React from "react";
import { motion } from "framer-motion";

// hex "#rrggbb" -> "r g b" triplet for the --tint CSS var.
function hexTriplet(hex) {
  const m = /^#([0-9a-f]{2})([0-9a-f]{2})([0-9a-f]{2})$/i.exec(hex || "");
  return m ? `${parseInt(m[1], 16)} ${parseInt(m[2], 16)} ${parseInt(m[3], 16)}` : null;
}

// `tint` (hex color) washes the card in a metric's own color + corner halo —
// used by the Overview hero gauges. Glass + hover-glow styles live in index.css.
export default function Card({ children, className = "", hover = true, tint, style, ...rest }) {
  const triplet = hexTriplet(tint);
  return (
    <motion.div
      variants={{
        hidden: { opacity: 0, y: 12 },
        show: { opacity: 1, y: 0, transition: { duration: 0.35, ease: "easeOut" } },
      }}
      whileHover={hover ? { y: -3, transition: { duration: 0.15 } } : undefined}
      className={
        "relative rounded-2xl border border-line/5 glass-card " +
        (hover ? "glass-hover " : "") +
        (triplet ? "card-tinted " : "") +
        "p-4 " +
        className
      }
      style={triplet ? { ...style, "--tint": triplet } : style}
      {...rest}
    >
      {children}
    </motion.div>
  );
}

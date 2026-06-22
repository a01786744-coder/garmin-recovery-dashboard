import React from "react";
import { motion } from "framer-motion";

export default function Card({ children, className = "", hover = true, ...rest }) {
  return (
    <motion.div
      variants={{
        hidden: { opacity: 0, y: 12 },
        show: { opacity: 1, y: 0, transition: { duration: 0.35, ease: "easeOut" } },
      }}
      whileHover={hover ? { y: -3, transition: { duration: 0.15 } } : undefined}
      className={
        "rounded-2xl border border-white/5 bg-neutral-900/60 backdrop-blur-sm " +
        "shadow-lg shadow-black/20 p-4 " +
        className
      }
      {...rest}
    >
      {children}
    </motion.div>
  );
}

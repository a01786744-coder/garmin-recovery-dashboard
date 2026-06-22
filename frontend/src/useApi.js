import { useEffect, useState } from "react";

// Generic async hook. Returns { data, loading, error }. Never throws to render.
export function useAsync(fn, deps = []) {
  const [state, setState] = useState({ data: null, loading: true, error: null });
  useEffect(() => {
    let alive = true;
    setState((s) => ({ ...s, loading: true }));
    Promise.resolve()
      .then(fn)
      .then((data) => alive && setState({ data, loading: false, error: null }))
      .catch((error) => alive && setState({ data: null, loading: false, error }));
    return () => {
      alive = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
  return state;
}

// Convert a Garmin [[ms, val], ...] array into recharts [{x, y}].
export function pairsToXY(arr) {
  if (!arr) return null;
  return arr.map(([x, y]) => ({ x, y: y == null || y < 0 ? null : y }));
}

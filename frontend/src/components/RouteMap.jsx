import React from "react";
import { MapContainer, TileLayer, Polyline, CircleMarker, Tooltip } from "react-leaflet";
import "leaflet/dist/leaflet.css";
import NoData from "./ui/NoData.jsx";

// Draws an activity's GPS route on a dark basemap.
//
// PRIVACY NOTE: this is the one place the app talks to a server other than
// Garmin Connect. Map tiles are fetched from CartoDB's public tile servers
// (basemaps.cartocdn.com). No health or account data is sent — only the
// standard {z}/{x}/{y} tile coordinates for the map area — but those requests
// do reveal the geographic region of your runs to the tile host. This was an
// explicit, approved trade-off for a real basemap under the route (see the v2
// design doc). To stay fully local instead, drop the <TileLayer> and render the
// polyline on a plain background.
export default function RouteMap({ polyline, height = 320 }) {
  const pts = (polyline || [])
    .filter((p) => p && p.lat != null && p.lon != null)
    .map((p) => [p.lat, p.lon]);

  if (pts.length < 2) {
    return (
      <div className="rounded-xl border border-dashed border-white/10 bg-neutral-950/40">
        <NoData label="No GPS route for this activity" height={height} />
      </div>
    );
  }

  const lats = pts.map((p) => p[0]);
  const lons = pts.map((p) => p[1]);
  const bounds = [
    [Math.min(...lats), Math.min(...lons)],
    [Math.max(...lats), Math.max(...lons)],
  ];
  const start = pts[0];
  const end = pts[pts.length - 1];

  return (
    <div className="overflow-hidden rounded-xl border border-white/5" style={{ height }}>
      <MapContainer
        bounds={bounds}
        boundsOptions={{ padding: [24, 24] }}
        scrollWheelZoom={false}
        style={{ height: "100%", width: "100%", background: "#0a0a0a" }}
        attributionControl={false}
      >
        <TileLayer
          url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
          subdomains={["a", "b", "c", "d"]}
          maxZoom={19}
        />
        <Polyline positions={pts} pathOptions={{ color: "#22c55e", weight: 4, opacity: 0.9 }} />
        <CircleMarker center={start} radius={6}
          pathOptions={{ color: "#22c55e", fillColor: "#22c55e", fillOpacity: 1 }}>
          <Tooltip>Start</Tooltip>
        </CircleMarker>
        <CircleMarker center={end} radius={6}
          pathOptions={{ color: "#ef4444", fillColor: "#ef4444", fillOpacity: 1 }}>
          <Tooltip>Finish</Tooltip>
        </CircleMarker>
      </MapContainer>
    </div>
  );
}

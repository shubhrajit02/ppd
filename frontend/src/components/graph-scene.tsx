"use client";
import { Canvas, useFrame } from "@react-three/fiber";
import { Component, useMemo, useRef, useState, type ReactNode } from "react";
import * as THREE from "three";
import { graphEdges, graphNodes, StaticGraph } from "./intelligence-graph";

class FallbackBoundary extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() { return { failed: true }; }
  render() { return this.state.failed ? <StaticGraph /> : this.props.children; }
}
function Topology({ moving, sequence, stage }: { moving: boolean; sequence: number; stage: string }) {
  const group = useRef<THREE.Group>(null);
  const pulse = useRef<THREE.Mesh>(null);
  const elapsed = useRef(0);
  const geometry = useMemo(() => new THREE.BufferGeometry().setFromPoints(graphEdges.flatMap(([a, b]) => [a, b].map(i => new THREE.Vector3(graphNodes[i].x, graphNodes[i].y, 0)))), []);
  useFrame(({ pointer, invalidate }, delta) => {
    if (!moving) return;
    elapsed.current += Math.min(delta, 0.05);
    if (group.current) { group.current.rotation.y = THREE.MathUtils.damp(group.current.rotation.y, pointer.x * 0.1, 5, delta); group.current.rotation.x = THREE.MathUtils.damp(group.current.rotation.x, -pointer.y * 0.06, 5, delta); }
    if (pulse.current) {
      const scope = stage === "SCANNING" ? [0] : stage === "PARSING" ? [1, 2] : stage === "STATIC_ANALYSIS" ? [2] : stage === "AI_ANALYSIS" ? [3, 4, 5, 6] : [7, 8, 9, 10];
      const edge = graphEdges[scope[(sequence + Math.floor(elapsed.current / 3)) % scope.length]];
      const a = graphNodes[edge[0]], b = graphNodes[edge[1]], t = (elapsed.current % 3) / 3;
      pulse.current.position.set(THREE.MathUtils.lerp(a.x, b.x, t), THREE.MathUtils.lerp(a.y, b.y, t), 0.04);
    }
    invalidate();
  });
  return <group ref={group} position={[-0.65, 0, 0]}>
    <lineSegments geometry={geometry}><lineBasicMaterial color="#4a5b50" transparent opacity={0.7} /></lineSegments>
    {graphNodes.map((n, i) => <group key={n.label} position={[n.x, n.y, 0]}><mesh rotation={[0, 0, n.kind === "file" ? 0 : Math.PI / 4]}><boxGeometry args={n.kind === "core" ? [0.46, 0.46, 0.32] : [0.16, 0.16, 0.12]} /><meshStandardMaterial color={n.color} roughness={0.55} metalness={0.3} /></mesh><mesh><ringGeometry args={[i === 0 ? 0.46 : 0.23, i === 0 ? 0.47 : 0.237, 48]} /><meshBasicMaterial color={n.color} transparent opacity={0.5} side={THREE.DoubleSide} /></mesh></group>)}
    <mesh ref={pulse} visible={moving}><sphereGeometry args={[0.045, 8, 8]} /><meshBasicMaterial color={stage === "VALIDATING" || stage === "SYNTHESIZING" ? "#c2ee85" : "#98bce8"} /></mesh>
  </group>;
}
export default function GraphScene(props: { moving: boolean; sequence: number; stage: string }) {
  const [lost, setLost] = useState(false);
  if (lost) return <StaticGraph />;
  return <FallbackBoundary><div className="graph-canvas" aria-hidden="true"><Canvas frameloop="demand" dpr={[1, 1.25]} camera={{ position: [0, 0, 8], fov: 43 }} gl={{ antialias: true, powerPreference: "low-power" }} fallback={<StaticGraph />} onCreated={({ gl }) => { gl.domElement.addEventListener("webglcontextlost", e => { e.preventDefault(); setLost(true); }, { once: true }); }}><ambientLight intensity={1.5} /><directionalLight position={[3, 4, 6]} intensity={2} /><Topology {...props} /></Canvas></div><div className="graph-labels" aria-label="Repository, files, symbols, Security, Bug and logic, Performance, Maintainability, Validated findings">{graphNodes.map(n => <span key={n.label} style={{ left: `calc(50% + ${(n.x - 0.65) * 0.1586} * var(--graph-height))`, top: `calc(50% - ${n.y * 0.1586} * var(--graph-height) + 24px)` }}>{n.label}</span>)}</div></FallbackBoundary>;
}

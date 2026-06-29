"use client";
// Fond 3D immersif — champ de particules réactif souris + scroll. Client-only (jamais SSR :
// importé via dynamic(ssr:false) dans LandingClient). Lean : three + fiber, sans drei.
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { useEffect, useMemo, useRef, useState } from "react";
import * as THREE from "three";

// Best practice perf : ne pas rendre la 3D quand l'onglet est caché (économie batterie/CPU).
function usePageVisible(): boolean {
  const [visible, setVisible] = useState(true);
  useEffect(() => {
    const on = () => setVisible(!document.hidden);
    document.addEventListener("visibilitychange", on);
    return () => document.removeEventListener("visibilitychange", on);
  }, []);
  return visible;
}

function Particles({ count }: { count: number }) {
  const ref = useRef<THREE.Points>(null!);
  const positions = useMemo(() => {
    const a = new Float32Array(count * 3);
    for (let i = 0; i < count; i++) {
      const r = 6.5 * Math.cbrt(Math.random());
      const theta = Math.random() * Math.PI * 2;
      const phi = Math.acos(2 * Math.random() - 1);
      a[i * 3] = r * Math.sin(phi) * Math.cos(theta);
      a[i * 3 + 1] = r * Math.sin(phi) * Math.sin(theta) * 0.62;
      a[i * 3 + 2] = r * Math.cos(phi);
    }
    return a;
  }, [count]);

  useFrame((state, dt) => {
    const m = ref.current;
    if (!m) return;
    const t = state.clock.elapsedTime;
    m.rotation.y += dt * 0.045;                                  // dérive lente
    const my = state.pointer.y * 0.25;                           // parallax souris
    const mx = state.pointer.x * 0.25;
    m.rotation.x += (my - m.rotation.x) * 0.03;
    m.rotation.z += (mx * 0.2 - m.rotation.z) * 0.03;
    m.scale.setScalar(1 + Math.sin(t * 0.4) * 0.03);            // respiration
  });

  return (
    <points ref={ref}>
      <bufferGeometry>
        <bufferAttribute attach="attributes-position" args={[positions, 3]} />
      </bufferGeometry>
      <pointsMaterial
        size={0.026}
        sizeAttenuation
        color="#5eead4"
        transparent
        opacity={0.82}
        depthWrite={false}
        blending={THREE.AdditiveBlending}
      />
    </points>
  );
}

function Rig() {
  const { camera } = useThree();
  useFrame(() => {
    const h = typeof window !== "undefined" ? window.innerHeight || 800 : 800;
    const p = typeof window !== "undefined" ? Math.min(1.5, window.scrollY / h) : 0;
    camera.position.z += (9 + p * 4 - camera.position.z) * 0.05;  // dolly arrière au scroll
    camera.lookAt(0, 0, 0);
  });
  return null;
}

export default function Scene() {
  const small = typeof window !== "undefined" && window.innerWidth < 768;
  const reduced =
    typeof window !== "undefined" &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const count = small ? 1500 : reduced ? 1200 : 3800;
  const visible = usePageVisible();
  return (
    <Canvas
      camera={{ position: [0, 0, 9], fov: 55 }}
      dpr={[1, 1.8]}
      gl={{ antialias: true, alpha: true, powerPreference: "high-performance" }}
      frameloop={reduced || !visible ? "demand" : "always"}
    >
      <Particles count={count} />
      {!reduced && <Rig />}
    </Canvas>
  );
}

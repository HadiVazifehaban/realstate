"use client";

import { useEffect, useRef } from "react";

type Particle = { x: number; y: number; vx: number; vy: number; radius: number };
const FRAME_INTERVAL = 1000 / 30;

/** Independently implemented network inspired by franky's LGMWPK demo.
 * No demo code, dependencies, image assets or touch handlers are imported.
 */
export function HeroAtmosphere() {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const context = canvas.getContext("2d");
    if (!context) return;
    const motion = window.matchMedia("(prefers-reduced-motion: reduce)");
    const hero = canvas.closest<HTMLElement>(".landing-hero");
    let width = 0;
    let height = 0;
    let particles: Particle[] = [];
    let frame: number | null = null;
    let lastTime = 0;
    let inView = true;
    let disposed = false;
    let pointer: { x: number; y: number } | null = null;
    let elapsed = 0;
    let ink = "255,216,190";

    const stop = () => {
      if (frame !== null) cancelAnimationFrame(frame);
      frame = null;
      lastTime = 0;
    };
    const draw = (seconds: number) => {
      elapsed += seconds;
      context.clearRect(0, 0, width, height);
      for (const particle of particles) {
        particle.x = Math.max(0, Math.min(width, particle.x + particle.vx * seconds));
        particle.y = Math.max(0, Math.min(height, particle.y + particle.vy * seconds));
        if (particle.x <= 0 || particle.x >= width) particle.vx *= -1;
        if (particle.y <= 0 || particle.y >= height) particle.vy *= -1;
      }
      const distanceLimit = Math.min(190, width * 0.28);
      const reveal = motion.matches ? 1 : Math.min(1, 0.25 + elapsed / 2);
      const connect = (a: { x: number; y: number }, b: { x: number; y: number }) => {
        const squaredDistance = (a.x - b.x) ** 2 + (a.y - b.y) ** 2;
        if (squaredDistance >= distanceLimit ** 2) return;
        const opacity = (1 - Math.sqrt(squaredDistance) / distanceLimit) * 0.24 * reveal;
        context.strokeStyle = `rgba(${ink},${opacity})`;
        context.lineWidth = 0.6;
        context.beginPath();
        context.moveTo(a.x, a.y);
        context.lineTo(b.x, b.y);
        context.stroke();
      };
      for (let i = 0; i < particles.length; i++) {
        const a = particles[i];
        for (let j = i + 1; j < particles.length; j++) {
          connect(a, particles[j]);
        }
        if (pointer && !motion.matches) connect(a, pointer);
        context.fillStyle = `rgba(${ink},${0.48 * reveal})`;
        context.beginPath();
        context.arc(a.x, a.y, a.radius, 0, Math.PI * 2);
        context.fill();
      }
    };
    const canAnimate = () =>
      !disposed && !motion.matches && !document.hidden && inView && width > 0 && height > 0;
    const tick = (time: number) => {
      frame = null;
      if (!canAnimate()) return;
      if (!lastTime || time - lastTime >= FRAME_INTERVAL) {
        draw(lastTime ? Math.min((time - lastTime) / 1000, 0.1) : 0);
        lastTime = time;
      }
      frame = requestAnimationFrame(tick);
    };
    const resume = () => {
      stop();
      if (motion.matches) {
        pointer = null;
        draw(0);
      }
      if (canAnimate()) frame = requestAnimationFrame(tick);
    };
    const resize = () => {
      stop();
      const bounds = canvas.getBoundingClientRect();
      width = bounds.width;
      height = bounds.height;
      // Cap resolution and particle count independently of large/retina displays.
      const ratio = Math.min(
        window.devicePixelRatio || 1,
        1.5,
        Math.sqrt(3_000_000 / Math.max(1, width * height))
      );
      canvas.width = Math.round(width * ratio);
      canvas.height = Math.round(height * ratio);
      context.setTransform(ratio, 0, 0, ratio, 0, 0);
      const count =
        width > 0 && height > 0
          ? Math.min(64, Math.max(12, Math.floor((width * height) / 22000)))
          : 0;
      particles = Array.from({ length: count }, () => {
        const angle = Math.random() * Math.PI * 2;
        const speed = 6 + Math.random() * 9;
        return {
          x: Math.random() * width,
          y: Math.random() * height,
          vx: Math.cos(angle) * speed,
          vy: Math.sin(angle) * speed,
          radius: 0.7 + Math.random() * 0.6
        };
      });
      draw(0);
      resume();
    };
    // Passive listeners on the Hero, not the overlay: links and scrolling retain ownership.
    const movePointer = (event: PointerEvent) => {
      if (event.pointerType !== "mouse" || motion.matches) return;
      const bounds = canvas.getBoundingClientRect();
      const x = event.clientX - bounds.left;
      const y = event.clientY - bounds.top;
      pointer = x >= 0 && x <= width && y >= 0 && y <= height ? { x, y } : null;
    };
    const clearPointer = () => {
      pointer = null;
    };
    const updateInk = () => {
      ink = document.documentElement.classList.contains("light") ? "146,91,57" : "255,216,190";
      draw(0);
    };
    const themeObserver = new MutationObserver(updateInk);
    themeObserver.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ["class"]
    });
    const resizeObserver = new ResizeObserver(resize);
    const intersectionObserver = new IntersectionObserver(([entry]) => {
      inView = entry.isIntersecting;
      if (!inView) clearPointer();
      resume();
    });
    resizeObserver.observe(canvas);
    intersectionObserver.observe(canvas);
    motion.addEventListener("change", resume);
    document.addEventListener("visibilitychange", resume);
    hero?.addEventListener("pointermove", movePointer, { passive: true });
    hero?.addEventListener("pointerleave", clearPointer);
    updateInk();
    resize();
    return () => {
      disposed = true;
      stop();
      resizeObserver.disconnect();
      intersectionObserver.disconnect();
      themeObserver.disconnect();
      hero?.removeEventListener("pointermove", movePointer);
      hero?.removeEventListener("pointerleave", clearPointer);
      motion.removeEventListener("change", resume);
      document.removeEventListener("visibilitychange", resume);
    };
  }, []);

  return (
    <div className="landing-atmosphere" aria-hidden="true">
      <div className="landing-hero-grid" />
      <div className="landing-hero-glow" />
      <canvas ref={canvasRef} className="landing-particles" />
    </div>
  );
}

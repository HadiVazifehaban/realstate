import * as React from "react";
import { cleanup, render } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { HeroAtmosphere } from "./components/hero-atmosphere";

describe("hero particle network", () => {
  let resize: () => void;
  let intersect: (entries: { isIntersecting: boolean }[]) => void;
  let motionChanged: () => void;
  let reduced: boolean;
  let hidden: boolean;
  let width: number;
  let height: number;
  let frames: Map<number, FrameRequestCallback>;
  let nextFrame: number;
  const resizeDisconnect = vi.fn();
  const intersectionDisconnect = vi.fn();
  const removeMotion = vi.fn();
  const context = {
    clearRect: vi.fn(),
    setTransform: vi.fn(),
    beginPath: vi.fn(),
    moveTo: vi.fn(),
    lineTo: vi.fn(),
    stroke: vi.fn(),
    arc: vi.fn(),
    fill: vi.fn(),
    strokeStyle: "",
    fillStyle: "",
    lineWidth: 0
  };
  function step(time: number) {
    const callbacks = [...frames.values()];
    frames.clear();
    callbacks.forEach((callback) => callback(time));
  }

  beforeEach(() => {
    reduced = false;
    hidden = false;
    width = 390;
    height = 800;
    nextFrame = 0;
    frames = new Map();
    vi.spyOn(document, "hidden", "get").mockImplementation(() => hidden);
    vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue(
      context as unknown as CanvasRenderingContext2D
    );
    vi.spyOn(HTMLCanvasElement.prototype, "getBoundingClientRect").mockImplementation(
      () => ({ width, height }) as DOMRect
    );
    vi.stubGlobal("devicePixelRatio", 3);
    vi.stubGlobal(
      "requestAnimationFrame",
      vi.fn((callback: FrameRequestCallback) => {
        frames.set(++nextFrame, callback);
        return nextFrame;
      })
    );
    vi.stubGlobal(
      "cancelAnimationFrame",
      vi.fn((id: number) => frames.delete(id))
    );
    vi.stubGlobal("matchMedia", () => ({
      get matches() {
        return reduced;
      },
      addEventListener: (_: string, callback: () => void) => {
        motionChanged = callback;
      },
      removeEventListener: removeMotion
    }));
    vi.stubGlobal(
      "ResizeObserver",
      class {
        constructor(callback: () => void) {
          resize = callback;
        }
        observe() {}
        disconnect = resizeDisconnect;
      }
    );
    vi.stubGlobal(
      "IntersectionObserver",
      class {
        constructor(callback: typeof intersect) {
          intersect = callback;
        }
        observe() {}
        disconnect = intersectionDisconnect;
      }
    );
  });
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it("sizes to the container, caps DPR/density, throttles drawing and cancels old frames on resize", () => {
    const { container, unmount } = render(<HeroAtmosphere />);
    const canvas = container.querySelector("canvas")!;
    expect(canvas.width).toBe(585);
    expect(canvas.height).toBe(1200);
    expect(context.arc).toHaveBeenCalledTimes(14);
    expect(container.firstElementChild?.getAttribute("aria-hidden")).toBe("true");
    context.clearRect.mockClear();
    step(100);
    step(110);
    expect(context.clearRect).toHaveBeenCalledTimes(1);
    step(140);
    expect(context.clearRect).toHaveBeenCalledTimes(2);
    width = 3840;
    height = 2160;
    context.arc.mockClear();
    resize();
    expect(context.arc).toHaveBeenCalledTimes(64);
    expect(canvas.width * canvas.height).toBeLessThanOrEqual(3_005_000);
    expect(frames.size).toBe(1);
    expect(cancelAnimationFrame).toHaveBeenCalled();
    unmount();
    expect(frames.size).toBe(0);
    expect(resizeDisconnect).toHaveBeenCalledOnce();
    expect(intersectionDisconnect).toHaveBeenCalledOnce();
    expect(removeMotion).toHaveBeenCalledWith("change", motionChanged);
  });

  it("draws a static network for reduced motion and handles preference changes", () => {
    reduced = true;
    render(<HeroAtmosphere />);
    expect(context.arc).toHaveBeenCalled();
    expect(frames.size).toBe(0);
    reduced = false;
    motionChanged();
    expect(frames.size).toBe(1);
    reduced = true;
    motionChanged();
    expect(frames.size).toBe(0);
  });

  it("pauses offscreen/in background and removes the visibility listener on unmount", () => {
    const removeListener = vi.spyOn(document, "removeEventListener");
    const { unmount } = render(<HeroAtmosphere />);
    intersect([{ isIntersecting: false }]);
    expect(frames.size).toBe(0);
    intersect([{ isIntersecting: true }]);
    expect(frames.size).toBe(1);
    hidden = true;
    document.dispatchEvent(new Event("visibilitychange"));
    expect(frames.size).toBe(0);
    hidden = false;
    document.dispatchEvent(new Event("visibilitychange"));
    expect(frames.size).toBe(1);
    unmount();
    expect(removeListener).toHaveBeenCalledWith("visibilitychange", expect.any(Function));
    document.dispatchEvent(new Event("visibilitychange"));
    expect(frames.size).toBe(0);
  });

  it("only connects nearby particles with thin, low-opacity lines", () => {
    reduced = true;
    const random = [0, 0, 0.1, 0.1, 0, 0, 0, 0.12, 0.1, 0];
    let index = 0;
    vi.spyOn(Math, "random").mockImplementation(() => random[index++] ?? 0.9);
    render(<HeroAtmosphere />);
    expect(context.lineTo).toHaveBeenCalledWith(390 * 0.12, 800 * 0.1);
    context.lineTo.mock.calls.forEach(([x, y], index) => {
      const [startX, startY] = context.moveTo.mock.calls[index];
      expect(Math.hypot(x - startX, y - startY)).toBeLessThan(390 * 0.28);
    });
    expect(context.lineWidth).toBe(0.6);
  });

  it("tracks only mouse movement inside the Hero without consuming touch or clicks", () => {
    const { container, unmount } = render(
      <section className="landing-hero">
        <HeroAtmosphere />
        <button>CTA</button>
      </section>
    );
    const hero = container.querySelector("section")!;
    const remove = vi.spyOn(hero, "removeEventListener");
    const dispatch = (pointerType: string) => {
      const event = new Event("pointermove", { bubbles: true, cancelable: true });
      Object.assign(event, { pointerType, clientX: 195, clientY: 400 });
      hero.dispatchEvent(event);
      expect(event.defaultPrevented).toBe(false);
    };
    context.lineTo.mockClear();
    dispatch("touch");
    step(100);
    expect(context.lineTo.mock.calls.some(([x, y]) => x === 195 && y === 400)).toBe(false);
    // Put all particles beside the pointer, independent of random placement.
    vi.spyOn(Math, "random").mockReturnValue(0.5);
    resize();
    context.lineTo.mockClear();
    dispatch("mouse");
    step(200);
    expect(context.lineTo.mock.calls.some(([x, y]) => x === 195 && y === 400)).toBe(true);
    hero.dispatchEvent(new Event("pointerleave"));
    context.lineTo.mockClear();
    step(240);
    expect(context.lineTo.mock.calls.some(([x, y]) => x === 195 && y === 400)).toBe(false);
    unmount();
    expect(remove).toHaveBeenCalledWith("pointermove", expect.any(Function));
    expect(remove).toHaveBeenCalledWith("pointerleave", expect.any(Function));
  });
});

import { useEffect, useRef, useState, type CSSProperties, type ElementType, type MouseEvent, type ReactNode } from "react";

export function prefersReducedMotion(): boolean {
  return typeof window !== "undefined" && typeof window.matchMedia === "function"
    ? window.matchMedia("(prefers-reduced-motion: reduce)").matches
    : false;
}

/** Fades content up when it scrolls into view. Renders visible immediately when
 *  IntersectionObserver is unavailable or the user prefers reduced motion. */
export function Reveal({
  children,
  delay = 0,
  as: Tag = "div",
  className = "",
}: {
  children: ReactNode;
  delay?: number;
  as?: ElementType;
  className?: string;
}) {
  const ref = useRef<HTMLElement>(null);
  const [visible, setVisible] = useState(() => typeof IntersectionObserver === "undefined" || prefersReducedMotion());

  useEffect(() => {
    if (visible || !ref.current) return;
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((e) => e.isIntersecting)) {
          setVisible(true);
          observer.disconnect();
        }
      },
      { rootMargin: "0px 0px -8% 0px", threshold: 0.05 },
    );
    observer.observe(ref.current);
    return () => observer.disconnect();
  }, [visible]);

  return (
    <Tag ref={ref} className={`reveal ${visible ? "is-visible" : ""} ${className}`} style={{ transitionDelay: `${delay}ms` }}>
      {children}
    </Tag>
  );
}

/** Subtle 3D tilt that follows the pointer. */
export function Tilt({ children, className = "", max = 6 }: { children: ReactNode; className?: string; max?: number }) {
  const [style, setStyle] = useState<CSSProperties>({});
  function onMove(e: MouseEvent<HTMLDivElement>) {
    if (prefersReducedMotion()) return;
    const r = e.currentTarget.getBoundingClientRect();
    const x = (e.clientX - r.left) / r.width - 0.5;
    const y = (e.clientY - r.top) / r.height - 0.5;
    setStyle({ transform: `perspective(900px) rotateX(${(-y * max).toFixed(2)}deg) rotateY(${(x * max).toFixed(2)}deg)` });
  }
  return (
    <div
      className={`transition-transform duration-300 ease-out will-change-transform ${className}`}
      style={style}
      onMouseMove={onMove}
      onMouseLeave={() => setStyle({})}
    >
      {children}
    </div>
  );
}

/** Animated number for percentages and counts. */
export function CountUp({ value, suffix = "", duration = 900 }: { value: number; suffix?: string; duration?: number }) {
  const [shown, setShown] = useState(() => (prefersReducedMotion() || typeof requestAnimationFrame === "undefined" ? value : 0));
  useEffect(() => {
    if (prefersReducedMotion() || typeof requestAnimationFrame === "undefined") {
      setShown(value);
      return;
    }
    let frame = 0;
    const start = performance.now();
    const tick = (now: number) => {
      const t = Math.min(1, (now - start) / duration);
      setShown(Math.round(value * (1 - Math.pow(1 - t, 3))));
      if (t < 1) frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [value, duration]);
  return (
    <span>
      {shown}
      {suffix}
    </span>
  );
}

/** A coloured pill with soft pulsing rings behind it (the "works" pill in the reference). */
export function GlowPill({ children, className = "bg-iris text-white", ring = "bg-iris" }: { children: ReactNode; className?: string; ring?: string }) {
  return (
    <span className="relative inline-flex">
      <span aria-hidden="true" className={`absolute inset-0 animate-ring rounded-full ${ring} opacity-40`} />
      <span aria-hidden="true" className={`absolute inset-0 animate-ring rounded-full ${ring} opacity-30 [animation-delay:1.2s]`} />
      <span className={`relative rounded-full px-5 py-1 ${className}`}>{children}</span>
    </span>
  );
}

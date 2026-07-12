'use client';

import { useEffect, useRef, useState } from 'react';

// Scroll-reveal wrapper. Content is VISIBLE by default (no attribute) so a
// no-JS or headless render never ships blank. On mount we only hide elements
// that are still below the fold — the user can't see that flash — then animate
// them in when they scroll into view. Above-the-fold content is never hidden.
export default function Reveal({ children, className = '', delay = 0, as: Tag = 'div' }) {
  const ref = useRef(null);
  const [state, setState] = useState(null); // null → visible, 'pre' → hidden, 'in' → animating

  useEffect(() => {
    const el = ref.current;
    if (!el || typeof IntersectionObserver === 'undefined') return;
    // Already in / near view → leave it visible, no reveal needed.
    if (el.getBoundingClientRect().top < window.innerHeight * 0.9) return;
    setState('pre');
    const io = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) { setState('in'); io.disconnect(); }
      },
      { threshold: 0.12, rootMargin: '0px 0px -6% 0px' },
    );
    io.observe(el);
    return () => io.disconnect();
  }, []);

  return (
    <Tag
      ref={ref}
      className={className}
      {...(state ? { 'data-reveal': state } : {})}
      style={delay ? { '--reveal-delay': `${delay}ms` } : undefined}
    >
      {children}
    </Tag>
  );
}

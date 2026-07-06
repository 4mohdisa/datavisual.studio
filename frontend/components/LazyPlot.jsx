'use client';

import dynamic from 'next/dynamic';

// Plotly.js is ~5MB and touches `window` at import time, so it must be loaded
// client-side only (ssr: false) and lazily — the heavy chunk is fetched the
// first time a chart actually renders.
const Plot = dynamic(() => import('react-plotly.js'), {
  ssr: false,
  loading: () => <div className="skeleton" style={{ width: '100%', height: '300px' }} />,
});

export default function LazyPlot(props) {
  return <Plot {...props} />;
}

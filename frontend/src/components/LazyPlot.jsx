import { lazy, Suspense } from 'react';

// Plotly.js is ~5MB. Loading it lazily means the heavy chunk is only fetched the
// first time a chart actually renders, rather than in the initial bundle (5.1).
const Plot = lazy(() => import('react-plotly.js'));

export default function LazyPlot(props) {
  const height = props.style?.height || '300px';
  return (
    <Suspense fallback={<div className="skeleton" style={{ width: '100%', height }} />}>
      <Plot {...props} />
    </Suspense>
  );
}

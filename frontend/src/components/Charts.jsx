import Plot from 'react-plotly.js';

export default function Charts({ charts }) {
  if (!charts || charts.length === 0) return null;

  return (
    <div className="flex flex-col gap-6">
      {charts.map((chart, i) => {
        const spec = chart.plotly_json || {};
        const data = spec.data || [];
        // Task 6: compact, column-friendly heights. Histograms/heatmaps shorter.
        const shortTypes = ['histogram', 'heatmap'];
        const height = shortTypes.includes(chart.type) ? 250 : 300;
        const layout = {
          ...(spec.layout || {}),
          paper_bgcolor: 'rgba(0,0,0,0)',
          plot_bgcolor: 'rgba(0,0,0,0)',
          font: { color: 'rgb(220,220,220)' },
          margin: { l: 50, r: 20, t: 30, b: 40 },
          height,
          autosize: true,
          width: undefined, // never pin a pixel width — fill the column
        };

        return (
          <div key={i}>
            <div className="text-[13px] font-semibold text-[var(--muted)] mb-2 capitalize">
              {chart.title}
            </div>
            <Plot
              data={data}
              layout={layout}
              style={{ width: '100%', height: `${height}px` }}
              useResizeHandler={true}
              config={{ displayModeBar: false, responsive: true }}
            />
          </div>
        );
      })}
    </div>
  );
}

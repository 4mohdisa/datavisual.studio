import { useState } from 'react';
import ReportSection from './ReportSection';
import Charts from './Charts';
import ComparisonTable from './ComparisonTable';
import DataFilters from './DataFilters';
import InternetFindings from './InternetFindings';
import CouncilOpinions from './CouncilOpinions';
import ChairmanSynthesis from './ChairmanSynthesis';
import PredictionSuite from './PredictionSuite';
import CombinedPrediction from './CombinedPrediction';
import AIAnalysis from './AIAnalysis';
import PredictionCharts from './PredictionCharts';
import ExportButton from './ExportButton';

export default function Report({ report, conversationId }) {
  const [chartsData, setChartsData] = useState(null);

  if (!report || report.type !== 'full_report') return null;

  const { sections = {}, mode } = report;
  const {
    dataset_overview,
    data_filters,
    visualisations,
    internet_research,
    council_opinions,
    chairman_synthesis,
  } = sections;

  const activeCharts = chartsData ? chartsData.charts : (visualisations?.charts || []);
  const activeDataSegments = chartsData ? chartsData.data_segments_table : (visualisations?.data_segments_table || []);

  const handleFiltersApplied = (result) => setChartsData(result);

  // Prediction data lives at the report top level (with the chairman_synthesis
  // section as a fallback for older shapes). When a suite exists we render the new
  // three-section layout; otherwise we fall back to the old combined display.
  const predictionSuite = report.prediction_suite || chairman_synthesis?.prediction_suite || null;
  const predictionCharts = report.prediction_charts || chairman_synthesis?.prediction_charts || [];
  const predictionMeta = report.prediction_meta || chairman_synthesis?.prediction_meta || {};
  const hasSuite = !!(predictionSuite && (predictionSuite.model_a?.length || predictionSuite.combined?.length));

  return (
    <div className="flex flex-col">
      {/* Section 1 — Dataset Overview (Mode A only) */}
      {mode === 'data' && dataset_overview && (
        <ReportSection title="Dataset Overview">
          <div className="flex gap-5 text-[22px] font-bold text-[var(--text)] mb-4">
            <span className="bg-[var(--active)] px-[18px] py-2.5 rounded-lg border border-[var(--border-2)]">
              {dataset_overview.data_summary?.row_count?.toLocaleString() || 0} rows
            </span>
            <span className="bg-[var(--active)] px-[18px] py-2.5 rounded-lg border border-[var(--border-2)]">
              {dataset_overview.data_summary?.column_count || 0} columns
            </span>
          </div>
          {dataset_overview.data_summary?.columns?.length > 0 && (
            <ComparisonTable
              rows={dataset_overview.data_summary.columns.map((c) => ({
                Column: c.name,
                Type: c.type,
                Nulls: c.null_count,
              }))}
              title="Column types"
            />
          )}
          {dataset_overview.quality_notes?.length > 0 && (
            <div className="mt-3">
              <div className="text-xs font-semibold text-[var(--muted)] uppercase tracking-wide mb-1.5">
                Quality notes
              </div>
              <ul className="m-0 pl-[18px] text-[var(--muted)] text-[13px] list-disc">
                {dataset_overview.quality_notes.map((n, i) => <li key={i}>{n}</li>)}
              </ul>
            </div>
          )}
        </ReportSection>
      )}

      {/* Section 2 — Data Filters (Mode A only) */}
      {mode === 'data' && data_filters && (
        <ReportSection title="Data Filters" defaultOpen={false}>
          <DataFilters
            availableFilters={data_filters.available_filters}
            conversationId={conversationId}
            onFiltersApplied={handleFiltersApplied}
          />
        </ReportSection>
      )}

      {/* Section 3 — Visualisations (Mode A only) */}
      {mode === 'data' && (activeCharts.length > 0 || activeDataSegments.length > 0) && (
        <ReportSection title="Visualisations">
          <Charts charts={activeCharts} />
          {activeDataSegments.length > 0 && (
            <ComparisonTable rows={activeDataSegments} title="Data segments" />
          )}
        </ReportSection>
      )}

      {/* Section 4 — Internet Research */}
      {internet_research && (
        <ReportSection title="Internet Research">
          <InternetFindings internetResearch={internet_research} />
        </ReportSection>
      )}

      {/* Section 5 — Council Opinions */}
      {council_opinions && (
        <ReportSection title="Council Opinions">
          <CouncilOpinions councilOpinions={council_opinions} />
        </ReportSection>
      )}

      {/* Sections 6–9 — predictions. New layout when a model suite exists, else
          a graceful fallback to the old combined ChairmanSynthesis display. */}
      {chairman_synthesis && (
        hasSuite ? (
          <>
            {/* 6 — Mathematical Model Predictions (Section 1) */}
            <ReportSection title="Mathematical Model Predictions">
              <PredictionSuite suite={predictionSuite} meta={predictionMeta} />
            </ReportSection>

            {/* 7 — Combined Prediction (Section 2) */}
            <ReportSection title="Combined Prediction">
              <CombinedPrediction suite={predictionSuite} />
            </ReportSection>

            {/* 8 — AI Analysis (Section 3) */}
            <ReportSection title="AI Analysis">
              <AIAnalysis chairmanSynthesis={chairman_synthesis} />
            </ReportSection>

            {/* 9 — How we got here (Section 4), collapsed by default */}
            {predictionCharts.length > 0 && (
              <ReportSection title="How we got here" defaultOpen={false}>
                <PredictionCharts charts={predictionCharts} />
              </ReportSection>
            )}
          </>
        ) : (
          /* Fallback (text-only mode / old conversations) — old combined display */
          <ReportSection title="AI Analysis">
            <ChairmanSynthesis chairmanSynthesis={chairman_synthesis} />
          </ReportSection>
        )
      )}

      {/* Section 10 — Export */}
      {conversationId && (
        <ReportSection title="Export" defaultOpen={false}>
          <ExportButton conversationId={conversationId} />
        </ReportSection>
      )}
    </div>
  );
}

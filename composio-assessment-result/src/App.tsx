import { useResearchData } from './hooks/useResearchData';
import TopBar from './components/TopBar';
import Headline from './components/Headline';
import AgentSummary from './components/AgentSummary';
import FindingsTable from './components/FindingsTable';
import SampleDesign from './components/SampleDesign';
import Verification from './components/Verification';
import Diagnostics from './components/Diagnostics';
import Footer from './components/Footer';

// The entire experience is one top-to-bottom page, sections in the graded order:
// 1 patterns → 2 agent → 3 sample design → 4 verification → 5 findings → 6 diagnostics → footer.
// Per-app tool-call traces live as raw log files (data/traces/*.jsonl), linked from the footer.
export default function App() {
  const { data, error, loading } = useResearchData();

  if (loading) {
    return <div className="center-msg">Loading research data…</div>;
  }
  if (error || !data) {
    return (
      <div className="center-msg">
        <div>Could not load the research data.</div>
        <div className="err">{error}</div>
      </div>
    );
  }

  return (
    <>
      <TopBar />
      <Headline patterns={data.patterns} gold={data.gold} apps={data.apps} />
      <AgentSummary patterns={data.patterns} automation={data.automation} />
      <SampleDesign apps={data.apps} accuracy={data.accuracy} gold={data.gold} patterns={data.patterns} />
      <Verification accuracy={data.accuracy} verification={data.verification} gold={data.gold} />
      <FindingsTable apps={data.apps} />
      <Diagnostics accuracy={data.accuracy} />
      <Footer />
    </>
  );
}

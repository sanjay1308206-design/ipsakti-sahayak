import "./App.css";
import { AnswerPanel } from "./components/AnswerPanel";
import { CitationsPanel } from "./components/CitationsPanel";
import { ClassificationJurisdictionPanel } from "./components/ClassificationJurisdictionPanel";
import { ErrorPanel } from "./components/ErrorPanel";
import { EvidencePanel } from "./components/EvidencePanel";
import { Header } from "./components/Header";
import { QueryForm, type QueryFormValues } from "./components/QueryForm";
import { QueryMetaPanel } from "./components/QueryMetaPanel";
import { ReviewPanel } from "./components/ReviewPanel";
import { StatusBanner } from "./components/StatusBanner";
import { useQueryLifecycle } from "./hooks/useQueryLifecycle";

/**
 * [ENGINEERING RECOMMENDATION] Presentation order follows the
 * evidence-first hierarchy from docs/PHASE_18_FRONTEND_PRODUCTIZATION.md
 * ("Evidence-First UX"): query -> classification/jurisdiction -> grounded
 * answer -> citations -> evidence -> safety/review status. The LLM
 * answer is never shown as an independent authority - it is always
 * accompanied by the status banner and, when present, the evidence and
 * review sections.
 */
function App() {
  const { status, response, error, submit, reset } = useQueryLifecycle();
  const isLoading = status === "LOADING";

  function handleSubmit(values: QueryFormValues) {
    submit({
      query: values.query,
      requested_language: values.requestedLanguage || null,
      jurisdiction: values.jurisdiction || null,
    });
  }

  return (
    <div className="app-shell">
      <Header />
      <main>
        <QueryForm isLoading={isLoading} onSubmit={handleSubmit} onReset={reset} />

        {isLoading && (
          <p className="loading-indicator" role="status" aria-live="polite">
            Consulting the regulatory knowledge pipeline...
          </p>
        )}

        {status === "ERROR" && error && <ErrorPanel error={error} />}

        {response && (status === "SUCCESS" || status === "ABSTAINED" || status === "ESCALATED") && (
          <div className="results" aria-live="polite">
            <StatusBanner response={response} outcome={status} />
            <ClassificationJurisdictionPanel response={response} />
            <AnswerPanel response={response} />
            <CitationsPanel response={response} />
            <EvidencePanel response={response} />
            <ReviewPanel response={response} />
            <QueryMetaPanel response={response} />
          </div>
        )}
      </main>
    </div>
  );
}

export default App;

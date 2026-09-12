import { useState, type FormEvent } from "react";

/**
 * [ENGINEERING RECOMMENDATION] The language/jurisdiction option lists
 * below are NOT invented by the frontend - they mirror vocabularies
 * already fixed by Phase 12 (`jurisdiction.models.REQUEST_JURISDICTION_VALUES`)
 * and Phase 14 (`multilingual.models.SUPPORTED_LANGUAGE_TAGS`). Offering
 * them as a picker is a UI usability convenience only; the backend
 * remains the sole authority on whether a value is actually valid - an
 * unsupported/malformed selection still round-trips through the real
 * Phase 12/14 logic and is reported honestly (e.g. UNSUPPORTED_LANGUAGE,
 * jurisdiction state UNKNOWN), never rejected or reinterpreted here.
 */
const LANGUAGE_OPTIONS: Array<{ value: string; label: string }> = [
  { value: "", label: "Not specified (deliver in original language)" },
  { value: "en", label: "English" },
  { value: "hi", label: "Hindi (हिन्दी)" },
  { value: "ta", label: "Tamil (தமிழ்)" },
];

const JURISDICTION_OPTIONS: Array<{ value: string; label: string }> = [
  { value: "", label: "Not specified" },
  { value: "INDIA", label: "India" },
  { value: "INTERNATIONAL", label: "International" },
  { value: "BOTH", label: "Both" },
  { value: "UNSPECIFIED", label: "Unspecified" },
];

/**
 * [OUR ENHANCEMENT] Mirrors the backend's own coarse wire-level bound
 * (`api.schemas._WIRE_MAX_LENGTH = 20000`) as a UI usability guard only -
 * the real, authoritative business limit is enforced server-side and is
 * not exposed to the client (docs/PHASE_18_FRONTEND_PRODUCTIZATION.md,
 * "Known Limitations").
 */
const QUERY_WIRE_MAX_LENGTH = 20_000;

export interface QueryFormValues {
  query: string;
  requestedLanguage: string;
  jurisdiction: string;
}

interface QueryFormProps {
  isLoading: boolean;
  onSubmit: (values: QueryFormValues) => void;
  onReset: () => void;
}

export function QueryForm({ isLoading, onSubmit, onReset }: QueryFormProps) {
  const [query, setQuery] = useState("");
  const [requestedLanguage, setRequestedLanguage] = useState("");
  const [jurisdiction, setJurisdiction] = useState("");
  const [validationError, setValidationError] = useState<string | null>(null);

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmed = query.trim();
    if (!trimmed) {
      setValidationError("Please enter a question before submitting.");
      return;
    }
    setValidationError(null);
    onSubmit({ query: trimmed, requestedLanguage, jurisdiction });
  }

  function handleReset() {
    setQuery("");
    setRequestedLanguage("");
    setJurisdiction("");
    setValidationError(null);
    onReset();
  }

  return (
    <form className="query-form" onSubmit={handleSubmit} aria-label="Ask IP-SAKTI Sahayak a question">
      <div className="form-field">
        <label htmlFor="query-input">Your question</label>
        <textarea
          id="query-input"
          name="query"
          rows={4}
          maxLength={QUERY_WIRE_MAX_LENGTH}
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="e.g. What IP protection is available for a new Ayurvedic formulation in India?"
          aria-required="true"
          aria-invalid={validationError !== null}
          aria-describedby={validationError ? "query-input-error" : undefined}
        />
        {validationError && (
          <p id="query-input-error" role="alert" className="field-error">
            {validationError}
          </p>
        )}
      </div>

      <div className="form-row">
        <div className="form-field">
          <label htmlFor="language-select">Preferred answer language</label>
          <select id="language-select" value={requestedLanguage} onChange={(event) => setRequestedLanguage(event.target.value)}>
            {LANGUAGE_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </div>

        <div className="form-field">
          <label htmlFor="jurisdiction-select">Jurisdiction</label>
          <select id="jurisdiction-select" value={jurisdiction} onChange={(event) => setJurisdiction(event.target.value)}>
            {JURISDICTION_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div className="form-actions">
        <button type="submit" disabled={isLoading} aria-busy={isLoading}>
          {isLoading ? "Asking..." : "Ask"}
        </button>
        <button type="button" onClick={handleReset} disabled={isLoading}>
          Clear
        </button>
      </div>
    </form>
  );
}

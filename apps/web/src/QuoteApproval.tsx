import { useRef, useState } from "react";
import { Api, objectPath, stepUpHash, type Goal, type Quote } from "./api";

export function QuoteApproval({
  api,
  quote,
  goal,
  stepId,
  approve,
}: {
  api: Api;
  quote: Quote;
  goal: Goal;
  stepId: string;
  approve: (work: (api: Api) => Promise<unknown>) => Promise<void>;
}) {
  const [challenge, setChallenge] = useState<{
    id: string;
    nonce: string;
    expiresAt: number;
  } | null>(null);
  const [proof, setProof] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const grant = useRef("");
  const approval = useRef("");
  async function prepare() {
    setBusy(true);
    setError("");
    try {
      setChallenge(
        await api.request("auth/step-up", "POST", {
          operation: "POST /v1/approvals",
          requestHash: await stepUpHash({
            quoteId: quote.id,
            schemaVersion: "1.0",
          }),
        }),
      );
      setProof("");
      grant.current = "";
    } catch (error) {
      setError(
        error instanceof Error ? error.message : "Vérification indisponible.",
      );
    } finally {
      setBusy(false);
    }
  }
  return (
    <div>
      <p>
        L’approbation nécessite une authentification récente auprès de votre
        émetteur d’identité.
      </p>
      {error && (
        <p role="alert" className="form-error">
          {error}
        </p>
      )}
      {!challenge ? (
        <button
          className="primary-button"
          disabled={busy}
          onClick={() => void prepare()}
        >
          Vérifier mon identité pour approuver
        </button>
      ) : (
        <>
          <p>
            Nonce à transmettre à votre émetteur :{" "}
            <code className="identity-nonce">{challenge.nonce}</code>
          </p>
          <label className="field-label" htmlFor="identity-proof">
            Preuve d’identité récente (jeton ID lié au nonce)
          </label>
          <input
            id="identity-proof"
            type="password"
            autoComplete="off"
            value={proof}
            onChange={(event) => setProof(event.target.value)}
          />
          <button
            className="primary-button"
            disabled={!proof.trim() && !grant.current && !approval.current}
            onClick={() =>
              void approve(async (client) => {
                if (!approval.current) {
                  if (!grant.current) {
                    const value = await client.request<{ grant: string }>(
                      `${objectPath("auth/step-up", challenge.id)}/complete`,
                      "POST",
                      { identityProof: proof.trim() },
                    );
                    grant.current = value.grant;
                    setProof("");
                  }
                  const value = await client.request<{ id: string }>(
                    "approvals",
                    "POST",
                    { quoteId: quote.id },
                    undefined,
                    grant.current,
                  );
                  approval.current = value.id;
                }
                // Preserve the successful first step if the decision response is lost.
                return client.request(
                  `${objectPath("goals", goal.id)}/decisions`,
                  "POST",
                  { stepId, approvalId: approval.current },
                  goal.rev,
                );
              })
            }
          >
            Approuver ce panier
          </button>
          {!approval.current && (
            <button
              className="text-button"
              disabled={busy}
              onClick={() => void prepare()}
            >
              Renouveler la vérification
            </button>
          )}
        </>
      )}
    </div>
  );
}

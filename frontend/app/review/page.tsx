"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { ApiError, api } from "../../lib/api";
import { useDatasetId } from "../../lib/current";
import { useI18n } from "../../lib/i18n";
import type { Dataset, Issue } from "../../lib/types";

function suggestionText(issue: Issue, t: (key: string, params?: Record<string, string | number>) => string) {
  return t(`kind.${issue.suggestion.kind}`, { v: issue.suggestion.value || "" });
}

function IssueCard({
  issue, status, editing, draft, setDraft, setEditing, onDecide, onUndo, t,
}: {
  issue: Issue;
  status: string;
  editing: number | null;
  draft: string;
  setDraft: (value: string) => void;
  setEditing: (id: number | null) => void;
  onDecide: (issue: Issue, action: "accept" | "ignore" | "edit", value?: string) => void;
  onUndo: (issue: Issue) => void;
  t: (key: string, params?: Record<string, string | number>) => string;
}) {
  return (
    <article className="issue">
      <header>
        <span className="tag">{t(`type.${issue.type}`)}</span>
        <span>{t("review.row", { n: issue.row + 1 })}</span>
        {issue.decision && <span className="badge">{t(`review.${issue.decision === "accept" ? "accept" : issue.decision}`)}</span>}
        {issue.learned && <span className="badge">{t("review.learned")}</span>}
      </header>
      {issue.col >= 0 && <div className="kv"><b>{t("review.field")}</b><span>{issue.field}</span></div>}
      <div className="kv"><b>{t("review.original")}</b><span className="mono">{issue.original || "—"}</span></div>
      <div className="kv"><b>{t("review.suggestion")}</b><span>{suggestionText(issue, t)}</span></div>
      <p><b>{t("review.why")}</b> {issue.explanation}</p>
      {status === "review" && (
        <div className="row">
          {issue.decision ? (
            <button className="btn" onClick={() => onUndo(issue)}>{t("review.undo")}</button>
          ) : (
            <>
              <button className="btn green" onClick={() => onDecide(issue, "accept")}>
                {issue.suggestion.kind === "reviewId" ? t("review.keep") : t("review.accept")}
              </button>
              {issue.type !== "duplicate" && (
                <button className="btn" onClick={() => { setEditing(issue.id); setDraft(issue.suggestion.value || ""); }}>{t("review.edit")}</button>
              )}
              <button className="btn" onClick={() => onDecide(issue, "ignore")}>{t("review.ignore")}</button>
            </>
          )}
        </div>
      )}
      {editing === issue.id && (
        <div className="row" style={{ marginTop: 8 }}>
          <input value={draft} onChange={(e) => setDraft(e.target.value)} />
          <button className="btn primary" onClick={() => onDecide(issue, "edit", draft)}>{t("review.editSave")}</button>
          <button className="btn" onClick={() => setEditing(null)}>{t("common.cancel")}</button>
        </div>
      )}
    </article>
  );
}

function ReviewInner() {
  const { id, ready, missing } = useDatasetId();
  const { t, lang } = useI18n();
  const router = useRouter();
  const [data, setData] = useState<Dataset | null>(null);
  const [editing, setEditing] = useState<number | null>(null);
  const [draft, setDraft] = useState("");
  const [error, setError] = useState("");

  function load() {
    if (!id) return;
    api<Dataset>(`/api/datasets/${id}?lang=${lang}`).then(setData).catch(() => router.replace("/"));
  }
  useEffect(load, [id, lang]);

  async function decide(issue: Issue, action: "accept" | "ignore" | "edit", value?: string) {
    if (!id) return;
    setError("");
    await api(`/api/datasets/${id}/anomalies/${issue.id}`, {
      method: "POST",
      body: JSON.stringify({ action, value }),
    });
    setEditing(null);
    load();
  }

  async function undo(issue: Issue) {
    if (!id) return;
    await api(`/api/datasets/${id}/anomalies/${issue.id}/undo`, { method: "POST" });
    load();
  }

  async function acceptAll() {
    if (!id) return;
    await api(`/api/datasets/${id}/accept-all`, { method: "POST" });
    load();
  }

  async function finish() {
    if (!id) return;
    setError("");
    try {
      await api(`/api/datasets/${id}/complete`, { method: "POST", body: JSON.stringify({ lang }) });
      router.push(`/report?id=${id}`);
    } catch (err) {
      setError(t(err instanceof ApiError ? `err.${err.code}` : "err.REQUEST_FAILED"));
    }
  }

  if (!ready || (!data && !missing)) return <p>{t("common.loading")}</p>;
  if (missing || !id) return <div className="page-head"><h1>{t("review.title")}</h1><p>{t("common.noRun")}</p><Link className="btn primary" href="/upload">{t("nav.upload")}</Link></div>;
  if (!data) return <p>{t("common.loading")}</p>;

  const issues = data.issues || [];
  const pending = issues.filter((issue) => !issue.decision);
  const auto = issues.filter((issue) => issue.auto && issue.decision === "accept");
  const yours = issues.filter((issue) => issue.decision && !(issue.auto && issue.decision === "accept"));
  const cardProps = { status: data.status, editing, draft, setDraft, setEditing, onDecide: decide, onUndo: undo, t };

  return (
    <>
      <div className="page-head"><h1>{t("review.title")}</h1><p>{data.name}. {t("review.desc")}</p></div>
      <div className="card">
        <div className="row" style={{ marginBottom: 10 }}>
          <strong>{t("review.pending", { n: pending.length })}</strong>
          {pending.length === 0 && <span className="badge done">{t("review.allDone")}</span>}
          {data.status === "review" && pending.length > 0 && (
            <button className="btn" onClick={acceptAll}>{t("review.acceptAll")}</button>
          )}
        </div>
        {pending.length === 0 && <p>{t("review.nonePending")}</p>}
        {pending.map((issue) => <IssueCard key={issue.id} issue={issue} {...cardProps} />)}
        {auto.length > 0 && (
          <details className="fold">
            <summary>{t("review.autoTitle", { n: auto.length })}</summary>
            <p className="sub">{t("review.autoHint")}</p>
            {auto.map((issue) => <IssueCard key={issue.id} issue={issue} {...cardProps} />)}
          </details>
        )}
        {yours.length > 0 && (
          <details className="fold">
            <summary>{t("review.yours", { n: yours.length })}</summary>
            {yours.map((issue) => <IssueCard key={issue.id} issue={issue} {...cardProps} />)}
          </details>
        )}
        {(data.cleanRows || []).length > 0 && (
          <details className="fold">
            <summary>{t("review.cleanTitle", { n: data.cleanRows?.length || 0 })}</summary>
            <p className="sub">{t("review.cleanHint")}</p>
            <div className="table-scroll">
              <table>
                <thead>
                  <tr>
                    <th>{t("review.rowNo")}</th>
                    {(data.headers || []).map((header) => <th key={header}>{header}</th>)}
                  </tr>
                </thead>
                <tbody>
                  {(data.cleanRows || []).map((row) => (
                    <tr key={row.row}>
                      <td>{row.row}</td>
                      {row.cells.map((cell, index) => <td key={index}>{cell}</td>)}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </details>
        )}
        <div className="error">{error}</div>
        {data.status === "review" ? (
          <button className="btn primary" disabled={pending.length > 0} onClick={finish}>{t("review.finish")}</button>
        ) : (
          <button className="btn primary" onClick={() => router.push(`/report?id=${data.id}`)}>{t("report.title")}</button>
        )}
      </div>
    </>
  );
}

export default function ReviewPage() {
  return <Suspense fallback={<p>…</p>}><ReviewInner /></Suspense>;
}

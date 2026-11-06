"use client";

import { useEffect, useState } from "react";
import { ApiError, api } from "../../lib/api";
import { useI18n } from "../../lib/i18n";
import type { Dataset, Usage } from "../../lib/types";

type Ask = { question: string; answer: string; source: string };

export default function AiPage() {
  const { t, lang } = useI18n();
  const [rows, setRows] = useState<Dataset[]>([]);
  const [datasetId, setDatasetId] = useState("");
  const [question, setQuestion] = useState("");
  const [asks, setAsks] = useState<Ask[]>([]);
  const [usage, setUsage] = useState<Usage | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    setQuestion(t("ai.default"));
  }, [lang, t]);

  useEffect(() => {
    api<Dataset[]>("/api/datasets?status=done").then((list) => {
      setRows(list);
      if (list[0]) setDatasetId(String(list[0].id));
    }).catch(() => setRows([]));
    api<Usage>("/api/usage").then(setUsage).catch(() => undefined);
  }, []);

  useEffect(() => {
    if (!datasetId) return;
    api<Ask[]>(`/api/ai/asks?dataset_id=${datasetId}`).then(setAsks).catch(() => setAsks([]));
  }, [datasetId]);

  async function send() {
    if (!datasetId) return;
    setBusy(true);
    setError("");
    try {
      const result = await api<Ask & { usage: Usage }>(`/api/ai/ask?dataset_id=${datasetId}`, {
        method: "POST",
        body: JSON.stringify({ question, lang }),
      });
      setAsks([result, ...asks]);
      setUsage(result.usage);
    } catch (err) {
      setError(t(err instanceof ApiError ? `err.${err.code}` : "err.REQUEST_FAILED"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <div className="page-head">
        <h1>{t("ai.page")}</h1>
        <p>{t("ai.lead")}</p>
      </div>
      <div className="card">
        {usage && <p>{t("ai.usage", { left: usage.remainingCalls, limit: usage.callLimit, used: usage.usedTokens, cap: usage.tokenLimit })}{usage.keyConfigured ? "" : ` · ${t("ai.noKey")}`}</p>}
        <label className="field"><span>{t("ai.pick")}</span>
          <select value={datasetId} onChange={(e) => setDatasetId(e.target.value)}>
            {rows.length === 0 && <option value="">{t("ai.empty")}</option>}
            {rows.map((row) => <option key={row.id} value={row.id}>{row.name}</option>)}
          </select>
        </label>
        <label className="field"><span>{t("ai.question")}</span><textarea value={question} onChange={(e) => setQuestion(e.target.value)} /></label>
        <div className="error">{error}</div>
        <button className="btn primary" disabled={!datasetId || busy} onClick={send}>{t("ai.ask")}</button>
      </div>
      {asks.map((item, index) => (
        <div className="card" key={index}>
          <b>{item.question}</b>
          <p className="sub">{item.source === "llm" ? t("ai.llm") : t("ai.rules")}</p>
          <div className="note">{item.answer}</div>
        </div>
      ))}
    </>
  );
}

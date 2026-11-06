"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { ApiError, api } from "../../lib/api";
import { useI18n } from "../../lib/i18n";
import type { Dataset, TemplateCard, TemplateRule, Usage } from "../../lib/types";

function TemplateInner() {
  const params = useSearchParams();
  const slug = params.get("slug") || "";
  const router = useRouter();
  const { t, lang } = useI18n();
  const [card, setCard] = useState<TemplateCard | null>(null);
  const [rules, setRules] = useState<TemplateRule[]>([]);
  const [source, setSource] = useState("");
  const [usage, setUsage] = useState<Usage | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [showDemo, setShowDemo] = useState(false);

  useEffect(() => {
    if (!slug) return;
    api<TemplateCard>(`/api/templates/${slug}?lang=${lang}`).then((next) => {
      setCard(next);
      setRules([]);
      setSource("");
      setShowDemo(false);
    }).catch(() => router.replace("/upload"));
    api<Usage>("/api/usage").then(setUsage).catch(() => undefined);
  }, [slug, lang, router]);

  async function analyze() {
    setBusy(true);
    setError("");
    try {
      const result = await api<{ rules: TemplateRule[]; source: string }>(`/api/templates/${slug}/analyze?lang=${lang}`, { method: "POST" });
      setRules(result.rules);
      setSource(result.source);
      const next = await api<Usage>("/api/usage");
      setUsage(next);
    } catch (err) {
      setError(t(err instanceof ApiError ? `err.${err.code}` : "err.REQUEST_FAILED"));
    } finally {
      setBusy(false);
    }
  }

  function toggle(index: number) {
    setRules(rules.filter((_, item) => item !== index));
  }

  async function run(kind: "sample" | "file") {
    if (!rules.length) return;
    setBusy(true);
    setError("");
    try {
      let created: Dataset;
      if (kind === "sample") {
        created = await api<Dataset>(`/api/datasets/sample/${slug}`, {
          method: "POST",
          body: JSON.stringify({ rules, lang }),
        });
      } else {
        if (!file || !card) return;
        const body = new FormData();
        body.set("file", file);
        body.set("name", card.name);
        body.set("template_name", card.name);
        body.set("rules", JSON.stringify(rules));
        created = await api<Dataset>("/api/datasets", { method: "POST", body });
      }
      sessionStorage.setItem("sheetwise_current", String(created.id));
      router.push(`/progress?id=${created.id}`);
    } catch (err) {
      setBusy(false);
      setError(t(err instanceof ApiError ? `err.${err.code}` : "err.REQUEST_FAILED"));
    }
  }

  if (!card) return <p>{t("common.loading")}</p>;
  const sourceLabel = source === "llm" ? t("tpl.fromLlm") : source === "builtin" ? t("tpl.fromBuiltin") : t("tpl.fromRules");

  return (
    <>
      <div className="page-head">
        <h1>{card.name}</h1>
        <p>{card.summary}</p>
      </div>
      <div className="card">
        <p>{card.note}</p>
        <div className="table-scroll">
          <table>
            <thead><tr>{card.headers.map((header) => <th key={header}>{header}</th>)}</tr></thead>
            <tbody>
              {card.sample.map((row, index) => <tr key={index}>{row.map((cell, cellIndex) => <td key={cellIndex}>{cell}</td>)}</tr>)}
            </tbody>
          </table>
        </div>
        <div className="row" style={{ marginTop: 12 }}>
          <button className="btn primary" disabled={busy} onClick={analyze}>{t("tpl.analyze")}</button>
          {usage && <span className="sub">{t("tpl.left", { used: usage.remainingCalls, limit: usage.callLimit })}{usage.keyConfigured ? "" : ` · ${t("tpl.noKey")}`}</span>}
        </div>
        <div className="error">{error}</div>
      </div>
      {!!rules.length && (
        <div className="card">
          <h3>{t("tpl.rules")} · {sourceLabel}</h3>
          {rules.map((rule, index) => (
            <div className="row" key={`${rule.type}-${rule.field}-${index}`} style={{ marginBottom: 8 }}>
              <span className="tag">{rule.type}</span>
              <span>{rule.text || rule.field}</span>
              <button className="btn" onClick={() => toggle(index)}>{t("tpl.remove")}</button>
            </div>
          ))}
          <div className="field" style={{ marginTop: 12 }}>
            <span>{t("tpl.real")}</span>
            <input type="file" accept=".csv,.xlsx,.xls" onChange={(e) => setFile(e.target.files?.[0] || null)} />
          </div>
          <div className="row">
            <button className="btn primary" disabled={!file || busy} onClick={() => run("file")}>{t("tpl.useFile")}</button>
            <button className="btn" onClick={() => setShowDemo((open) => !open)}>{showDemo ? t("tpl.hide") : t("tpl.preview")}</button>
          </div>
          {showDemo && (
            <>
              <p className="sub">{t("tpl.demoNote")}</p>
              <div className="table-scroll">
                <table>
                  <thead><tr>{card.headers.map((header) => <th key={header}>{header}</th>)}</tr></thead>
                  <tbody>
                    {(card.demo || []).map((row, index) => <tr key={index}>{row.map((cell, cellIndex) => <td key={cellIndex}>{cell}</td>)}</tr>)}
                  </tbody>
                </table>
              </div>
              <button className="btn primary" disabled={busy} onClick={() => run("sample")}>{t("tpl.useDemo")}</button>
            </>
          )}
        </div>
      )}
    </>
  );
}

export default function TemplatePage() {
  return <Suspense fallback={<p>…</p>}><TemplateInner /></Suspense>;
}

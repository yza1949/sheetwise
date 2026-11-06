"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { api } from "../../lib/api";
import { rememberDataset, useDatasetId } from "../../lib/current";
import { useI18n } from "../../lib/i18n";
import type { Dataset } from "../../lib/types";

const STEPS = 5;

function ProgressInner() {
  const { id, ready, missing } = useDatasetId();
  const router = useRouter();
  const { t, lang } = useI18n();
  const steps = [t("step.parse"), t("step.detect"), t("step.template"), t("step.suggest"), t("step.ready")];
  const [data, setData] = useState<Dataset | null>(null);
  const [shown, setShown] = useState(0);

  useEffect(() => {
    if (!id) return;
    rememberDataset(id);
    api<Dataset>(`/api/datasets/${id}?lang=${lang}`).then(setData).catch(() => router.replace("/upload"));
  }, [id, lang, router]);

  useEffect(() => {
    if (!data) return;
    const seen = sessionStorage.getItem(`sheetwise_seen_${data.id}`);
    if (seen) {
      setShown(STEPS);
      return;
    }
    setShown(0);
    const timer = window.setInterval(() => {
      setShown((value) => {
        if (value >= STEPS) {
          window.clearInterval(timer);
          sessionStorage.setItem(`sheetwise_seen_${data.id}`, "1");
          return value;
        }
        return value + 1;
      });
    }, 450);
    return () => window.clearInterval(timer);
  }, [data]);

  if (!ready || (!data && !missing)) return <p>{t("common.loading")}</p>;
  if (missing || !id) {
    return <div className="page-head"><h1>{t("progress.page")}</h1><p>{t("common.noRun")}</p><Link className="btn primary" href="/upload">{t("nav.upload")}</Link></div>;
  }
  if (!data) return <p>{t("common.loading")}</p>;
  const logs = data.log || [];
  const width = Math.round((Math.min(shown, steps.length) / steps.length) * 100);

  return (
    <>
      <div className="page-head">
        <h1>{t("progress.page")}</h1>
        <p>{t("progress.live")}</p>
      </div>
      <div className="card">
        <div className="progress-top">
          <span className="badge">{t("progress.engine")}</span>
          <span>{shown >= steps.length ? t("progress.done") : t("progress.working")}</span>
        </div>
        <div className="bar"><i style={{ width: `${width}%` }} /></div>
        <div className="steps">
          <div>
            {steps.map((step, index) => (
              <div className="check" key={step}><span className={index < shown ? "dot on" : "dot"}>{index < shown ? "✓" : ""}</span>{step}</div>
            ))}
            {shown >= steps.length && (
              <div className="row" style={{ marginTop: 12 }}>
                <Link className="btn primary" href={data.status === "done" ? `/report?id=${data.id}` : `/review?id=${data.id}`}>
                  {data.status === "done" ? t("progress.viewReport") : t("progress.viewReview")}
                </Link>
              </div>
            )}
          </div>
          <div>
            <div className="sub" style={{ marginBottom: 8 }}>{t("progress.log")}</div>
            <div className="log">
              {logs.slice(0, shown).map((line, index) => <p key={index}>{line.text}</p>)}
              {shown < logs.length && <p className="dim">…</p>}
            </div>
          </div>
        </div>
      </div>
    </>
  );
}

export default function ProgressPage() {
  return <Suspense fallback={<p>…</p>}><ProgressInner /></Suspense>;
}

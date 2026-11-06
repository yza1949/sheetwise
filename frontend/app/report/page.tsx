"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { api, downloadFile } from "../../lib/api";
import { useDatasetId } from "../../lib/current";
import { useI18n } from "../../lib/i18n";
import type { Dataset } from "../../lib/types";

type Report = {
  qualityScore: number;
  fixed: number;
  ignored: number;
  duplicatesRemoved: number;
  issuesFound: number;
  rows: number;
};

function ReportInner() {
  const { id, ready, missing } = useDatasetId();
  const { t, lang } = useI18n();
  const router = useRouter();
  const [data, setData] = useState<Dataset | null>(null);
  const [report, setReport] = useState<Report | null>(null);

  useEffect(() => {
    if (!id) return;
    api<Dataset>(`/api/datasets/${id}?lang=${lang}`).then((row) => {
      if (row.status !== "done") router.replace(`/review?id=${id}`);
      else setData(row);
    }).catch(() => router.replace("/"));
    api<Report>(`/api/datasets/${id}/report`).then(setReport).catch(() => undefined);
  }, [id, lang, router]);

  if (!ready || (!data && !missing)) return <p>{t("common.loading")}</p>;
  if (missing || !id) return <div className="page-head"><h1>{t("report.title")}</h1><p>{t("common.noRun")}</p><Link className="btn primary" href="/upload">{t("nav.upload")}</Link></div>;
  if (!data) return <p>{t("common.loading")}</p>;
  const types = Object.entries(data.byType).filter(([, count]) => count > 0);

  return (
    <>
      <div className="page-head"><h1>{t("report.title")}</h1><p>{data.name}. {t("report.desc")}</p></div>
      <div className="card">
        <div className="stats">
          <div className="stat"><b>{report?.qualityScore ?? "—"}</b><span>{t("report.score", { score: report?.qualityScore ?? "—" })}</span></div>
          <div className="stat"><b>{report?.rows ?? data.rowCount}</b><span>{t("progress.rows")}</span></div>
          <div className="stat"><b>{report?.fixed ?? 0}</b><span>{t("report.fixed")}</span></div>
          <div className="stat"><b>{report?.ignored ?? 0}</b><span>{t("report.ignored")}</span></div>
        </div>
        {report && report.duplicatesRemoved > 0 && <p>{t("report.dup", { n: report.duplicatesRemoved })}</p>}
        <div className="row" style={{ marginTop: 12 }}>
          <Link className="btn" href={`/review?id=${id}`}>{t("report.back")}</Link>
          <button className="btn primary" onClick={() => downloadFile(`/api/datasets/${id}/download`, `${data.name}_cleaned.csv`)}>{t("report.download")}</button>
          <button className="btn" onClick={() => downloadFile(`/api/datasets/${id}/report`, `${data.name}_report.json`)}>{t("report.json")}</button>
        </div>
      </div>
      <div className="card">
        <h3>{t("report.byType")}</h3>
        <div className="row">{types.map(([type, count]) => <span className="tag" key={type}>{t(`type.${type}`)} {count}</span>)}</div>
      </div>
    </>
  );
}

export default function ReportPage() {
  return <Suspense fallback={<p>…</p>}><ReportInner /></Suspense>;
}

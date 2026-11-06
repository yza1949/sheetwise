"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api } from "../lib/api";
import { useI18n } from "../lib/i18n";
import type { Dataset } from "../lib/types";

export default function HomePage() {
  const { t, lang } = useI18n();
  const router = useRouter();
  const [rows, setRows] = useState<Dataset[] | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api<Dataset[]>("/api/datasets").then(setRows).catch(() => setRows([]));
  }, []);

  async function sample() {
    setBusy(true);
    const created = await api<Dataset>("/api/datasets/sample", {
      method: "POST",
      body: JSON.stringify({
        question: lang === "en" ? "How many chairs sold in the North?" : "华北的椅子卖了多少",
        lang,
      }),
    });
    router.push(`/progress?id=${created.id}`);
  }

  const list = rows || [];
  const openIssues = list.reduce((sum, row) => sum + Math.max(0, row.issueCount - row.decidedCount), 0);

  return (
    <>
      <div className="page-head"><h1>{t("home.title")}</h1><p>{t("home.desc")}</p></div>
      <div className="stats">
        <div className="stat"><b>{list.length}</b><span>{t("home.total")}</span></div>
        <div className="stat"><b>{list.filter((row) => row.status === "review").length}</b><span>{t("home.review")}</span></div>
        <div className="stat"><b>{list.filter((row) => row.status === "done").length}</b><span>{t("home.done")}</span></div>
        <div className="stat"><b>{openIssues}</b><span>{t("home.issues")}</span></div>
      </div>
      <div className="row" style={{ marginBottom: 14 }}>
        <Link className="btn primary" href="/upload">{t("home.new")}</Link>
        <button className="btn" disabled={busy} onClick={sample}>{t("home.sample")}</button>
      </div>
      <div className="card">
        <h3>{t("home.recent")}</h3>
        {!rows ? <p>{t("common.loading")}</p> : list.length === 0 ? <p>{t("home.empty")}</p> : (
          <div className="table-scroll">
            <table>
              <tbody>
                {list.slice(0, 8).map((row) => (
                  <tr key={row.id}>
                    <td>{row.name}</td>
                    <td><span className={`badge ${row.status}`}>{t(`status.${row.status}`)}</span></td>
                    <td>{row.issueCount}</td>
                    <td><Link className="btn" href={row.status === "done" ? `/report?id=${row.id}` : `/review?id=${row.id}`}>{t("history.open")}</Link></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </>
  );
}

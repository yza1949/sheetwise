"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "../../lib/api";
import { useI18n } from "../../lib/i18n";
import type { Dataset, User } from "../../lib/types";

export default function HistoryPage() {
  const { t } = useI18n();
  const [rows, setRows] = useState<Dataset[]>([]);
  const [me, setMe] = useState<User | null>(null);
  const [q, setQ] = useState("");
  const [status, setStatus] = useState("all");

  function load(query = q, nextStatus = status) {
    const params = new URLSearchParams();
    if (query) params.set("q", query);
    if (nextStatus) params.set("status", nextStatus);
    api<Dataset[]>(`/api/datasets?${params.toString()}`).then(setRows).catch(() => setRows([]));
  }

  useEffect(() => {
    api<User>("/api/auth/me").then(setMe).catch(() => setMe(null));
    load();
  }, []);

  async function remove(id: number) {
    if (!window.confirm(t("common.confirm"))) return;
    await api(`/api/datasets/${id}`, { method: "DELETE" });
    load();
  }

  return (
    <>
      <div className="page-head"><h1>{t("history.title")}</h1><p>{t("history.desc")}</p></div>
      <div className="card">
        <div className="filters">
          <input placeholder={t("history.search")} value={q} onChange={(e) => { setQ(e.target.value); load(e.target.value, status); }} />
          <select value={status} onChange={(e) => { setStatus(e.target.value); load(q, e.target.value); }}>
            <option value="all">{t("history.all")}</option>
            <option value="review">{t("status.review")}</option>
            <option value="done">{t("status.done")}</option>
          </select>
        </div>
        {rows.length === 0 ? <p>{t("history.empty")}</p> : (
          <div className="table-scroll">
            <table>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.id}>
                    <td>{row.name}<div className="sub">{row.ownerName}</div></td>
                    <td>{row.createdAt.replace("T", " ")}</td>
                    <td>{row.rowCount}</td>
                    <td><span className={`badge ${row.status}`}>{t(`status.${row.status}`)}</span></td>
                    <td className="row">
                      <Link className="btn" href={row.status === "done" ? `/report?id=${row.id}` : `/review?id=${row.id}`}>{t("history.open")}</Link>
                      {me?.role === "admin" && <button className="btn danger" onClick={() => remove(row.id)}>{t("history.delete")}</button>}
                    </td>
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

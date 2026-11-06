"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "../../lib/api";
import { useI18n } from "../../lib/i18n";
import type { User } from "../../lib/types";

export default function UsersPage() {
  const { t } = useI18n();
  const router = useRouter();
  const [me, setMe] = useState<User | null>(null);
  const [rows, setRows] = useState<User[]>([]);

  function load() {
    api<User[]>("/api/users").then(setRows).catch(() => router.replace("/"));
  }
  useEffect(() => {
    api<User>("/api/auth/me").then((user) => {
      setMe(user);
      if (user.role !== "admin") router.replace("/");
      else load();
    }).catch(() => router.replace("/login"));
  }, []);

  async function remove(id: number) {
    if (!window.confirm(t("common.confirm"))) return;
    await api(`/api/users/${id}`, { method: "DELETE" });
    load();
  }

  return (
    <>
      <div className="page-head"><h1>{t("users.title")}</h1><p>{t("users.desc")}</p></div>
      <div className="card">
        <div className="table-scroll">
          <table>
            <thead>
              <tr><th>{t("auth.name")}</th><th>{t("auth.email")}</th><th>{t("users.role")}</th><th>{t("users.runs")}</th><th></th></tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.id}>
                  <td>{row.name} {me?.id === row.id && <span className="badge">{t("users.you")}</span>}</td>
                  <td>{row.email}</td>
                  <td><span className={row.role === "admin" ? "badge admin" : "badge"}>{t(row.role === "admin" ? "common.admin" : "common.member")}</span></td>
                  <td>{row.runs ?? 0}</td>
                  <td>{me?.id !== row.id && <button className="btn danger" onClick={() => remove(row.id)}>{t("users.delete")}</button>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </>
  );
}

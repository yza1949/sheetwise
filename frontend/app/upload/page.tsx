"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { ApiError, api } from "../../lib/api";
import { useI18n } from "../../lib/i18n";
import type { Dataset, TemplateCard } from "../../lib/types";

export default function UploadPage() {
  const { t, lang } = useI18n();
  const router = useRouter();
  const [templates, setTemplates] = useState<TemplateCard[]>([]);
  const [file, setFile] = useState<File | null>(null);
  const [name, setName] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    api<TemplateCard[]>(`/api/templates?lang=${lang}`).then(setTemplates).catch(() => setTemplates([]));
  }, [lang]);

  async function plain(event: React.FormEvent) {
    event.preventDefault();
    if (!file) return;
    setError("");
    const body = new FormData();
    body.set("file", file);
    body.set("name", name);
    body.set("rules", "[]");
    try {
      const created = await api<Dataset>("/api/datasets", { method: "POST", body });
      sessionStorage.setItem("sheetwise_current", String(created.id));
      router.push(`/progress?id=${created.id}`);
    } catch (err) {
      setError(t(err instanceof ApiError ? `err.${err.code}` : "err.REQUEST_FAILED"));
    }
  }

  return (
    <>
      <div className="page-head">
        <h1>{t("upload.page")}</h1>
        <p>{t("upload.lead")}</p>
      </div>
      <div className="cards">
        {templates.map((item) => (
          <Link className="choice" key={item.slug} href={`/template?slug=${item.slug}`}>
            <b>{item.name}</b>
            <span>{item.summary}</span>
          </Link>
        ))}
      </div>
      <form className="card" onSubmit={plain}>
        <h3>{t("upload.plain")}</h3>
        <label className="field"><span>{t("upload.nameLabel")}</span><input value={name} onChange={(e) => setName(e.target.value)} /></label>
        <label className="field"><span>CSV / XLSX / XLS</span><input type="file" accept=".csv,.xlsx,.xls" onChange={(e) => setFile(e.target.files?.[0] || null)} /></label>
        <div className="error">{error}</div>
        <button className="btn primary" disabled={!file}>{t("upload.go")}</button>
      </form>
    </>
  );
}

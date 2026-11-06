"use client";

import { useEffect, useState } from "react";
import { api } from "../../lib/api";
import { useI18n } from "../../lib/i18n";
import type { Usage, User } from "../../lib/types";

export default function SettingsPage() {
  const { t, lang, setLang } = useI18n();
  const [name, setName] = useState("");
  const [saved, setSaved] = useState(false);
  const [usage, setUsage] = useState<Usage | null>(null);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    api<User>("/api/auth/me").then((user) => setName(user.name)).catch(() => undefined);
    api<Usage>("/api/usage").then(setUsage).catch(() => undefined);
  }, []);

  async function save() {
    await api("/api/auth/me", { method: "PATCH", body: JSON.stringify({ name }) });
    setSaved(true);
  }

  return (
    <>
      <div className="page-head"><h1>{t("settings.title")}</h1><p>{t("settings.desc")}</p></div>
      <div className="card">
        <h3>{t("settings.usage")}</h3>
        {usage ? (
          <p>{t("settings.usageBody", { used: usage.usedCalls, limit: usage.callLimit, tokens: usage.usedTokens, cap: usage.tokenLimit })}</p>
        ) : <p>{t("common.loading")}</p>}
        <button className="btn" onClick={() => setOpen(true)}>{t("settings.recharge")}</button>
      </div>
      <div className="card">
        <label className="field"><span>{t("settings.name")}</span><input value={name} onChange={(e) => setName(e.target.value)} /></label>
        <button className="btn primary" onClick={save}>{t("settings.save")}</button>
        {saved && <p>{t("common.saved")}</p>}
      </div>
      <div className="card">
        <label className="field"><span>{t("settings.language")}</span>
          <select value={lang} onChange={(e) => setLang(e.target.value === "en" ? "en" : "zh")}>
            <option value="zh">中文</option>
            <option value="en">English</option>
          </select>
        </label>
        <p>{t("settings.note")}</p>
      </div>
      {open && (
        <div className="modal-back" onClick={() => setOpen(false)}>
          <div className="modal" onClick={(event) => event.stopPropagation()}>
            <h3>{t("settings.rechargeTitle")}</h3>
            <p>{t("settings.rechargeBody")}</p>
            <button className="btn primary" onClick={() => setOpen(false)}>{t("settings.ok")}</button>
          </div>
        </div>
      )}
    </>
  );
}

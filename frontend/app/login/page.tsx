"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { ApiError, api } from "../../lib/api";
import { useI18n } from "../../lib/i18n";

export default function LoginPage() {
  const { t, lang, setLang } = useI18n();
  const router = useRouter();
  const [mode, setMode] = useState<"in" | "up">("in");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState("");

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setError("");
    if (mode === "up" && password !== confirm) {
      setError(t("err.PASSWORD_MISMATCH"));
      return;
    }
    try {
      const path = mode === "in" ? "/api/auth/login" : "/api/auth/register";
      await api(path, {
        method: "POST",
        body: JSON.stringify(mode === "in" ? { email, password } : { name, email, password }),
      });
      router.replace("/");
    } catch (err) {
      setError(t(err instanceof ApiError ? `err.${err.code}` : "err.REQUEST_FAILED"));
    }
  }

  return (
    <div className="auth-wrap">
      <form className="card auth-card" onSubmit={submit}>
        <div className="logo"><span className="mark">S</span>{t("app.name")}</div>
        <p className="sub">{t("auth.title")}</p>
        <div className="tabs">
          <button type="button" className={mode === "in" ? "btn primary" : "btn"} onClick={() => setMode("in")}>{t("auth.signIn")}</button>
          <button type="button" className={mode === "up" ? "btn primary" : "btn"} onClick={() => setMode("up")}>{t("auth.signUp")}</button>
        </div>
        {mode === "up" && (
          <label className="field"><span>{t("auth.name")}</span><input value={name} onChange={(e) => setName(e.target.value)} /></label>
        )}
        <label className="field"><span>{t("auth.email")}</span><input type="email" value={email} onChange={(e) => setEmail(e.target.value)} /></label>
        <label className="field"><span>{t("auth.password")}</span><input type="password" value={password} onChange={(e) => setPassword(e.target.value)} /></label>
        {mode === "up" && (
          <label className="field"><span>{t("auth.confirm")}</span><input type="password" value={confirm} onChange={(e) => setConfirm(e.target.value)} /></label>
        )}
        <div className="error">{error}</div>
        <button className="btn primary" type="submit">{mode === "in" ? t("auth.submitIn") : t("auth.submitUp")}</button>
        <p className="sub">{t("auth.hint")}</p>
        <button type="button" className="btn" onClick={() => setLang(lang === "zh" ? "en" : "zh")}>{lang === "zh" ? "English" : "中文"}</button>
      </form>
    </div>
  );
}

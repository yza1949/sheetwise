"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api } from "../lib/api";
import { useI18n } from "../lib/i18n";
import type { User } from "../lib/types";

const ICONS = [
  ["/", "nav.home", "M4 10.5 12 4l8 6.5V20a1 1 0 0 1-1 1h-5v-6H10v6H5a1 1 0 0 1-1-1v-9.5Z"],
  ["/upload", "nav.upload", "M12 16V5m0 0 4 4M12 5 8 9M5 19h14"],
  ["/progress", "nav.progress", "M8 7h11M8 12h11M8 17h11M5 7h.01M5 12h.01M5 17h.01"],
  ["/review", "nav.review", "m5 12 4 4L19 6"],
  ["/report", "nav.report", "M7 3h7l5 5v13a1 1 0 0 1-1 1H7a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1Z"],
  ["/history", "nav.history", "M12 7v5l3 2M12 21a9 9 0 1 0-9-9"],
  ["/ai", "nav.ai", "M12 3v3M12 18v3M3 12h3M18 12h3M6 6l2 2M16 16l2 2M18 6l-2 2M8 16l-2 2"],
] as const;

export function Shell({ children }: { children: React.ReactNode }) {
  const path = usePathname();
  const router = useRouter();
  const { t, lang, setLang } = useI18n();
  const [user, setUser] = useState<User | null | undefined>(undefined);
  const [current, setCurrent] = useState("");

  useEffect(() => {
    if (path === "/login") return;
    let cancelled = false;
    api<User>("/api/auth/me").then((next) => { if (!cancelled) setUser(next); }).catch(() => { if (!cancelled) setUser(null); });
    return () => { cancelled = true; };
  }, [path]);

  useEffect(() => {
    if (user === undefined) return;
    if (!user && path !== "/login") router.replace("/login");
    if (user && path === "/login") router.replace("/");
  }, [user, path, router]);

  useEffect(() => {
    setCurrent(sessionStorage.getItem("sheetwise_current") || "");
  }, [path]);

  async function logout() {
    await api("/api/auth/logout", { method: "POST" });
    setUser(null);
    router.replace("/login");
  }

  if (path === "/login") return <>{children}</>;
  if (!user) return <div className="content">{t("common.loading")}</div>;

  const links = [
    ...ICONS,
    ...(user.role === "admin" ? [["/users", "nav.users", "M8 11a3 3 0 1 0 0-6 3 3 0 0 0 0 6ZM16 12a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5ZM4 19c0-2.5 2-4 4-4s4 1.5 4 4M14 19c.2-1.6 1.4-3 3.2-3 1.6 0 2.8 1 3.3 2.4"] as const] : []),
    ["/settings", "nav.settings", "M12 15.5a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7Z M12 3v2M12 19v2M3 12h2M19 12h2"] as const,
  ];

  return (
    <div className="layout">
      <aside className="sidebar">
        <div className="brand">
          <span className="mark">S</span>
          <div>
            <strong>{t("app.name")}</strong>
            <small>{t("app.sub")}</small>
          </div>
        </div>
        <nav className="nav">
          {links.map(([href, label, icon]) => {
            const withId = current && ["/progress", "/review", "/report"].includes(href) ? `${href}?id=${current}` : href;
            return (
            <Link key={href} href={withId} className={path === href ? "active" : ""}>
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d={icon} /></svg>
              {t(label)}
            </Link>
            );
          })}
        </nav>
        <div className="side-foot">Sheetwise<br />{t("app.foot")}</div>
      </aside>
      <div className="main">
        <header className="topbar">
          <button className="btn lang" onClick={() => setLang(lang === "zh" ? "en" : "zh")}>{lang === "zh" ? "English" : "中文"}</button>
          <div className="userchip">
            <span className="avatar">{user.name.slice(0, 1).toUpperCase()}</span>
            <strong>{user.name}</strong>
            <span className={user.role === "admin" ? "badge admin" : "badge"}>{t(user.role === "admin" ? "common.admin" : "common.member")}</span>
          </div>
          <button className="btn" onClick={logout}>{t("common.logout")}</button>
        </header>
        <div className="content">{children}</div>
      </div>
    </div>
  );
}

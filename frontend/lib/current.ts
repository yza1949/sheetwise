"use client";

import { useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import { api } from "./api";
import type { Dataset } from "./types";

export function rememberDataset(id: string | number) {
  sessionStorage.setItem("sheetwise_current", String(id));
}

export function useDatasetId() {
  const params = useSearchParams();
  const [id, setId] = useState<string | null>(null);
  const [missing, setMissing] = useState(false);

  useEffect(() => {
    const fromUrl = params.get("id");
    const saved = fromUrl || sessionStorage.getItem("sheetwise_current");
    if (saved) {
      rememberDataset(saved);
      setId(saved);
      setMissing(false);
      return;
    }
    api<Dataset[]>("/api/datasets")
      .then((list) => {
        if (list[0]) {
          rememberDataset(list[0].id);
          setId(String(list[0].id));
          setMissing(false);
        } else {
          setId("");
          setMissing(true);
        }
      })
      .catch(() => {
        setId("");
        setMissing(true);
      });
  }, [params]);

  return { id: id || "", ready: id !== null, missing };
}

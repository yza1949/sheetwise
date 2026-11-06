export type Role = "admin" | "member";

export type User = {
  id: number;
  name: string;
  email: string;
  role: Role;
  createdAt: string;
  runs?: number;
};

export type Suggestion = { kind: string; value: string; detail: string };

export type Issue = {
  id: number;
  key: string;
  type: string;
  row: number;
  col: number;
  field: string;
  original: string;
  suggestion: Suggestion;
  learned: boolean;
  auto?: boolean;
  decision: string | null;
  editedValue: string | null;
  explanation: string;
};

export type TextBlock = { text: string; source: "rules" | "llm" };

export type TemplateRule = {
  type: string;
  field: string;
  text: string;
  values?: string[];
  qty?: string;
  price?: string;
  min?: number | null;
  max?: number | null;
};

export type TemplateCard = {
  id: number;
  slug: string;
  name: string;
  summary: string;
  note: string;
  headers: string[];
  sample: string[][];
  rules: TemplateRule[];
  builtin: boolean;
  demo?: string[][];
};

export type Usage = {
  usedCalls: number;
  callLimit: number;
  remainingCalls: number;
  usedTokens: number;
  tokenLimit: number;
  remainingTokens: number;
  keyConfigured: boolean;
};

export type Dataset = {
  id: number;
  name: string;
  fileName: string;
  fileSize: number;
  status: "review" | "done" | "processing";
  createdAt: string;
  ownerId: number;
  ownerName: string;
  rowCount: number;
  colCount: number;
  truncated: boolean;
  question: string;
  plan: Partial<Record<"zh" | "en", TextBlock>>;
  answer: Partial<Record<"zh" | "en", TextBlock>>;
  byType: Record<string, number>;
  issueCount: number;
  decidedCount: number;
  engine?: string;
  templateName?: string;
  rules?: TemplateRule[];
  log?: { text: string }[];
  headers?: string[];
  preview?: string[][];
  cleanRows?: { row: number; cells: string[] }[];
  issues?: Issue[];
};

// Text utilities for H-MEM: deterministic hashed bag-of-words embeddings and
// lightweight enrichment heuristics. No network, no model calls — absolute
// retrieval scores are embedder-dependent and the conformance suite does not
// assert them (Meterless conformance/README.md).

const EMBED_DIM = 256;

const STOPWORDS = new Set([
  "a", "an", "and", "are", "as", "at", "be", "by", "do", "for", "from", "in",
  "is", "it", "of", "on", "or", "that", "the", "this", "to", "was", "we",
  "were", "with", "when", "what", "which", "who", "how", "why",
]);

export function tokenize(text: string): string[] {
  return (text.toLowerCase().match(/[a-z0-9']+/g) ?? []).filter((t) => t.length > 1);
}

export function contentTokens(text: string): string[] {
  return tokenize(text).filter((t) => !STOPWORDS.has(t));
}

export function jaccard(a: string[], b: string[]): number {
  if (a.length === 0 && b.length === 0) return 0;
  const sa = new Set(a);
  const sb = new Set(b);
  let inter = 0;
  for (const t of sa) if (sb.has(t)) inter++;
  const union = sa.size + sb.size - inter;
  return union === 0 ? 0 : inter / union;
}

export function topTokens(text: string, n: number): string[] {
  const seen = new Set<string>();
  const out: string[] = [];
  for (const t of tokenize(text)) {
    if (STOPWORDS.has(t) || seen.has(t)) continue;
    seen.add(t);
    out.push(t);
    if (out.length >= n) break;
  }
  return out;
}

// Signed feature hashing: deterministic, dependency-free.
export function embed(text: string): number[] {
  const vec = new Array<number>(EMBED_DIM).fill(0);
  for (const tok of tokenize(text)) {
    let h = 2166136261;
    for (let i = 0; i < tok.length; i++) {
      h ^= tok.charCodeAt(i);
      h = Math.imul(h, 16777619);
    }
    const idx = ((h >>> 0) % EMBED_DIM + EMBED_DIM) % EMBED_DIM;
    const sign = (h & 0x80000000) === 0 ? 1 : -1;
    vec[idx] += sign;
  }
  let norm = 0;
  for (const v of vec) norm += v * v;
  norm = Math.sqrt(norm) || 1;
  return vec.map((v) => v / norm);
}

export function cosine(a: number[], b: number[]): number {
  const n = Math.min(a.length, b.length);
  let dot = 0;
  for (let i = 0; i < n; i++) dot += a[i] * b[i];
  return dot;
}

const TECH_TERMS = new Set([
  "python", "typescript", "javascript", "rust", "docker", "kubernetes", "postgres",
  "sqlite", "redis", "react", "node", "api", "sql", "http", "grpc", "aws", "gcp",
  "azure", "linux", "git", "solana", "llm", "agent", "nemotron", "zetaris", "meterless",
]);

const DOMAIN_KEYWORDS: Array<[RegExp, string]> = [
  [/\b(python|typescript|javascript|rust|docker|kubernetes|api|sql|postgres|deploy|deploying)\b/, "tech:engineering"],
  [/\b(meeting|roadmap|quarterly|deadline|stakeholder|project|plan)\b/, "work:planning"],
  [/\b(prefer|preference|like|dislike|always|never)\b/, "personal:preferences"],
  [/\b(martin|user|profile|birthday|age)\b/, "personal:identity"],
];

// Multi-pass domain classification (spec section 5): explicit tags first,
// tech detection, then keyword scoring, then a general fallback.
export function inferDomain(text: string, tags: string[] = []): string {
  for (const t of tags) {
    if (t.includes(":")) return t;
  }
  const low = text.toLowerCase();
  for (const term of TECH_TERMS) {
    if (new RegExp(`\\b${term}\\b`).test(low) && !/roadmap|meeting/.test(low)) {
      return "tech:engineering";
    }
  }
  for (const [re, domain] of DOMAIN_KEYWORDS) {
    if (re.test(low)) return domain;
  }
  return "general";
}

export function inferNamespace(domain: string): string {
  return domain.includes(":") ? domain.replace(":", "/") : "general";
}

// Entity extraction heuristics (spec section 5): known tech terms, then
// Capitalized multiword names, normalized to lowercase slugs. Cap 10.
export function extractEntities(text: string): string[] {
  const out = new Set<string>();
  const low = text.toLowerCase();
  for (const term of TECH_TERMS) {
    if (new RegExp(`\\b${term}\\b`).test(low)) out.add(term);
  }
  const caps = text.match(/\b[A-Z][a-z]{2,}(?:\s+[A-Z][a-z]{2,})*\b/g) ?? [];
  for (const c of caps) {
    if (c.split(" ")[0].toLowerCase() === "the") continue;
    out.add(c.toLowerCase());
  }
  return [...out].slice(0, 10);
}

export function jaccardSets(a: string[], b: string[]): number {
  return jaccard(a, b);
}

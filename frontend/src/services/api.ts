const BASE = import.meta.env.VITE_API_URL ?? "http://localhost:8000/api";

export interface Finding {
  category: string;
  message: string;
}

export interface OnboardingReport {
  id: string;
  name: string;
  status: string;
  created_at: string;
  findings: Finding[];
}

export interface OnboardingRequest {
  name: string;
  repo_url?: string;
  description?: string;
}

export async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    let detail = `API error ${res.status}`;
    try {
      const body = await res.json();
      if (typeof body.detail === "string") detail = body.detail;
      else if (Array.isArray(body.detail))
        detail = body.detail.map((d: { msg: string }) => d.msg).join("; ");
    } catch {
      /* ignore non-JSON error bodies */
    }
    throw new Error(detail);
  }
  return res.json() as Promise<T>;
}

export interface RepositoryInput {
  source: string;
  branch?: string;
}

export interface CommitInfo {
  sha: string;
  message: string;
  author: string;
  date: string;
}

export interface RepositoryMetadata {
  id: string;
  source: string;
  source_type: "remote" | "local";
  local_path: string;
  branch: string;
  branches: string[];
  head: CommitInfo;
  commit_count: number;
  ingested_at: string;
}

export interface AnalysisRecord {
  id: string;
  base: RepositoryMetadata;
  enhancement: RepositoryMetadata;
  created_at: string;
}

export interface DiscoveryResult {
  applicationName: string;
  modules: { name: string; type: string; path: string }[];
  routes: {
    path: string;
    method?: string;
    component?: string;
    file: string;
    source: string;
  }[];
  apis: {
    method: string;
    route: string;
    controller?: string;
    action?: string;
    file: string;
    kind: string;
  }[];
  dependencies: {
    name: string;
    version?: string;
    ecosystem: string;
    scope: string;
    file: string;
  }[];
  pages: { name: string; type: string; route?: string; file: string }[];
  controllers: {
    name: string;
    route: string;
    isApi: boolean;
    actions: { name: string; httpMethod?: string; route: string }[];
    file: string;
  }[];
  services: { name: string; file: string; platform: string }[];
  repositories: { name: string; file: string; platform: string }[];
  components: { name: string; file: string; platform: string }[];
  hooks: { name: string; file: string; platform: string }[];
  views: { name: string; file: string; platform: string }[];
  layouts: { name: string; file: string; platform: string }[];
  warnings: string[];
}

export const discoveryApi = {
  run: (repositoryId: string) =>
    request<DiscoveryResult>("/discovery", {
      method: "POST",
      body: JSON.stringify({ repositoryId }),
    }),
};

export interface DiagramsResult {
  applicationName: string;
  moduleDiagram: string;
  dependencyDiagram: string;
  apiFlowDiagram: string;
  warnings: string[];
}

export const diagramApi = {
  generate: (target: { repositoryId?: string; path?: string }) =>
    request<DiagramsResult>("/diagrams", {
      method: "POST",
      body: JSON.stringify(target),
    }),
};

export const repositoryApi = {
  analyze: (base: RepositoryInput, enhancement: RepositoryInput) =>
    request<AnalysisRecord>("/repositories/analyze", {
      method: "POST",
      body: JSON.stringify({ base, enhancement }),
    }),
  list: () => request<RepositoryMetadata[]>("/repositories"),
};

export const api = {
  list: () => request<OnboardingReport[]>("/onboardings"),
  create: (body: OnboardingRequest) =>
    request<OnboardingReport>("/onboardings", {
      method: "POST",
      body: JSON.stringify(body),
    }),
};

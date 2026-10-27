import { useState } from "react";
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  CircularProgress,
  Grid,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import {
  AnalysisRecord,
  DiscoveryResult,
  RepositoryMetadata,
  discoveryApi,
  repositoryApi,
} from "../services/api";

const DISCOVERY_COUNTS: (keyof DiscoveryResult)[] = [
  "modules",
  "routes",
  "apis",
  "dependencies",
  "pages",
  "controllers",
  "services",
  "repositories",
  "components",
  "hooks",
  "views",
  "layouts",
];

function DiscoveryCard({
  title,
  data,
}: {
  title: string;
  data: DiscoveryResult;
}) {
  return (
    <Card variant="outlined">
      <CardContent>
        <Typography variant="h6" gutterBottom>
          {title} discovery: {data.applicationName}
        </Typography>
        <Box sx={{ mb: 1 }}>
          {DISCOVERY_COUNTS.map((k) => (
            <Chip
              key={k}
              size="small"
              variant="outlined"
              label={`${k}: ${(data[k] as unknown[]).length}`}
              sx={{ mr: 0.5, mb: 0.5 }}
            />
          ))}
        </Box>
        {data.warnings.map((w) => (
          <Alert key={w} severity="warning" sx={{ mb: 1 }}>
            {w}
          </Alert>
        ))}
        <details>
          <summary>View JSON</summary>
          <pre style={{ maxHeight: 400, overflow: "auto", fontSize: 12 }}>
            {JSON.stringify(data, null, 2)}
          </pre>
        </details>
      </CardContent>
    </Card>
  );
}

function RepoCard({
  title,
  repo,
}: {
  title: string;
  repo: RepositoryMetadata;
}) {
  return (
    <Card variant="outlined">
      <CardContent>
        <Typography variant="h6" gutterBottom>
          {title}
        </Typography>
        <Stack spacing={1}>
          <Typography variant="body2" sx={{ wordBreak: "break-all" }}>
            {repo.source}
          </Typography>
          <Stack direction="row" spacing={1}>
            <Chip size="small" label={repo.source_type} />
            <Chip
              size="small"
              color="primary"
              label={`branch: ${repo.branch}`}
            />
            <Chip size="small" label={`${repo.commit_count} commits`} />
          </Stack>
          <Typography variant="body2">
            Head: {repo.head.sha.slice(0, 8)} — {repo.head.message}
          </Typography>
          <Typography variant="caption">
            {repo.head.author} · {new Date(repo.head.date).toLocaleString()}
          </Typography>
          <Box>
            {repo.branches.map((b) => (
              <Chip
                key={b}
                size="small"
                variant="outlined"
                label={b}
                sx={{ mr: 0.5, mb: 0.5 }}
              />
            ))}
          </Box>
        </Stack>
      </CardContent>
    </Card>
  );
}

export default function RepositoryIngestionPage() {
  const [baseSource, setBaseSource] = useState("");
  const [baseBranch, setBaseBranch] = useState("main");
  const [enhSource, setEnhSource] = useState("");
  const [enhBranch, setEnhBranch] = useState("feature");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<AnalysisRecord | null>(null);
  const [discovery, setDiscovery] = useState<{
    base: DiscoveryResult;
    enhancement: DiscoveryResult;
  } | null>(null);

  const analyze = async () => {
    setLoading(true);
    setError(null);
    setResult(null);
    setDiscovery(null);
    try {
      const record = await repositoryApi.analyze(
        { source: baseSource, branch: baseBranch || undefined },
        { source: enhSource, branch: enhBranch || undefined },
      );
      setResult(record);
      const [base, enhancement] = await Promise.all([
        discoveryApi.run(record.base.id),
        discoveryApi.run(record.enhancement.id),
      ]);
      setDiscovery({ base, enhancement });
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <Typography variant="h5" gutterBottom>
        Repository Input
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        Enter a Git URL to clone, or a local repository path to load.
      </Typography>
      <Grid container spacing={2}>
        <Grid item xs={12} md={6}>
          <Typography variant="subtitle1">Base Repo</Typography>
          <Stack spacing={2}>
            <TextField
              label="Git URL or local path"
              value={baseSource}
              onChange={(e) => setBaseSource(e.target.value)}
              fullWidth
            />
            <TextField
              label="Branch"
              value={baseBranch}
              onChange={(e) => setBaseBranch(e.target.value)}
              fullWidth
            />
          </Stack>
        </Grid>
        <Grid item xs={12} md={6}>
          <Typography variant="subtitle1">Enhancement Repo</Typography>
          <Stack spacing={2}>
            <TextField
              label="Git URL or local path"
              value={enhSource}
              onChange={(e) => setEnhSource(e.target.value)}
              fullWidth
            />
            <TextField
              label="Branch"
              value={enhBranch}
              onChange={(e) => setEnhBranch(e.target.value)}
              fullWidth
            />
          </Stack>
        </Grid>
      </Grid>
      <Box sx={{ mt: 3 }}>
        <Button
          variant="contained"
          disabled={loading || !baseSource.trim() || !enhSource.trim()}
          onClick={analyze}
          startIcon={loading ? <CircularProgress size={18} /> : undefined}
        >
          Analyze
        </Button>
      </Box>
      {error && (
        <Alert severity="error" sx={{ mt: 2 }}>
          {error}
        </Alert>
      )}
      {result && (
        <Grid container spacing={2} sx={{ mt: 1 }}>
          <Grid item xs={12} md={6}>
            <RepoCard title="Base" repo={result.base} />
          </Grid>
          <Grid item xs={12} md={6}>
            <RepoCard title="Enhancement" repo={result.enhancement} />
          </Grid>
        </Grid>
      )}
      {discovery && (
        <Grid container spacing={2} sx={{ mt: 1 }}>
          <Grid item xs={12} md={6}>
            <DiscoveryCard title="Base" data={discovery.base} />
          </Grid>
          <Grid item xs={12} md={6}>
            <DiscoveryCard title="Enhancement" data={discovery.enhancement} />
          </Grid>
        </Grid>
      )}
    </>
  );
}

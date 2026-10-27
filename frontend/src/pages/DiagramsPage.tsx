import { useEffect, useState } from "react";
import {
  Alert,
  Box,
  Button,
  CircularProgress,
  MenuItem,
  Paper,
  Stack,
  Tab,
  Tabs,
  TextField,
  Typography,
} from "@mui/material";
import MermaidDiagram from "../diagrams/MermaidDiagram";
import {
  DiagramsResult,
  diagramApi,
  repositoryApi,
  RepositoryMetadata,
} from "../services/api";

export default function DiagramsPage() {
  const [repos, setRepos] = useState<RepositoryMetadata[]>([]);
  const [repoId, setRepoId] = useState("");
  const [path, setPath] = useState("");
  const [result, setResult] = useState<DiagramsResult | null>(null);
  const [tab, setTab] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    repositoryApi
      .list()
      .then(setRepos)
      .catch(() => undefined);
  }, []);

  const generate = async () => {
    setLoading(true);
    setError(null);
    try {
      setResult(
        await diagramApi.generate(
          path.trim() ? { path: path.trim() } : { repositoryId: repoId },
        ),
      );
    } catch (e) {
      setError((e as Error).message);
      setResult(null);
    } finally {
      setLoading(false);
    }
  };

  const diagrams = result
    ? [
        ["Module", result.moduleDiagram],
        ["Dependency", result.dependencyDiagram],
        ["API flow", result.apiFlowDiagram],
      ]
    : [];

  return (
    <Box>
      <Typography variant="h5" gutterBottom>
        Architecture diagrams
      </Typography>
      <Stack direction={{ xs: "column", md: "row" }} spacing={2} sx={{ mb: 2 }}>
        <TextField
          select
          size="small"
          label="Ingested repository"
          value={repoId}
          onChange={(e) => setRepoId(e.target.value)}
          sx={{ minWidth: 320 }}
        >
          {repos.map((r) => (
            <MenuItem key={r.id} value={r.id}>
              {r.source} ({r.branch})
            </MenuItem>
          ))}
        </TextField>
        <TextField
          size="small"
          label="…or local path"
          value={path}
          onChange={(e) => setPath(e.target.value)}
          sx={{ flexGrow: 1 }}
        />
        <Button
          variant="contained"
          onClick={generate}
          disabled={loading || (!repoId && !path.trim())}
        >
          {loading ? <CircularProgress size={20} /> : "Generate"}
        </Button>
      </Stack>
      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}
      {result && (
        <Paper sx={{ p: 2 }}>
          <Typography variant="subtitle1" gutterBottom>
            {result.applicationName}
          </Typography>
          {result.warnings.map((w) => (
            <Alert key={w} severity="warning" sx={{ mb: 1 }}>
              {w}
            </Alert>
          ))}
          <Tabs value={tab} onChange={(_, v) => setTab(v)}>
            {diagrams.map(([label]) => (
              <Tab key={label} label={label} />
            ))}
          </Tabs>
          <MermaidDiagram
            key={tab + diagrams[tab][1]}
            code={diagrams[tab][1]}
          />
        </Paper>
      )}
    </Box>
  );
}

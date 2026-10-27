import { useEffect, useState } from "react";
import {
  Alert,
  Box,
  Button,
  List,
  ListItem,
  ListItemText,
  TextField,
  Typography,
} from "@mui/material";
import { api, OnboardingReport } from "../services/api";

export default function OnboardingsPage() {
  const [reports, setReports] = useState<OnboardingReport[]>([]);
  const [name, setName] = useState("");
  const [repoUrl, setRepoUrl] = useState("");
  const [error, setError] = useState<string | null>(null);

  const load = () =>
    api
      .list()
      .then(setReports)
      .catch((e) => setError(e.message));
  useEffect(() => {
    load();
  }, []);

  const submit = async () => {
    try {
      setError(null);
      await api.create({ name, repo_url: repoUrl || undefined });
      setName("");
      setRepoUrl("");
      await load();
    } catch (e) {
      setError((e as Error).message);
    }
  };

  return (
    <>
      <Typography variant="h5" gutterBottom>
        Onboardings
      </Typography>
      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}
      <Box sx={{ display: "flex", gap: 2, mb: 3 }}>
        <TextField
          label="Application name"
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
        <TextField
          label="Repository URL"
          value={repoUrl}
          onChange={(e) => setRepoUrl(e.target.value)}
        />
        <Button variant="contained" disabled={!name} onClick={submit}>
          Start
        </Button>
      </Box>
      <List>
        {reports.map((r) => (
          <ListItem key={r.id} divider>
            <ListItemText
              primary={`${r.name} (${r.status})`}
              secondary={`${r.findings.length} findings`}
            />
          </ListItem>
        ))}
      </List>
    </>
  );
}

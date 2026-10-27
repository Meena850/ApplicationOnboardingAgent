import { useEffect, useMemo, useState } from "react";
import {
  Box,
  Button,
  Chip,
  Divider,
  Grid,
  List,
  ListItem,
  ListItemText,
  MenuItem,
  Paper,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  TextField,
  ToggleButton,
  ToggleButtonGroup,
  Typography,
  Accordion,
  AccordionDetails,
  AccordionSummary,
  LinearProgress,
} from "@mui/material";
import { repositoryApi, RepositoryMetadata } from "../services/api";
import {
  ArchitectureSummary,
  ComparisonResult,
  dashboardApi,
  FeatureResult,
  PlanResult,
  RecommendationResult,
  RepoRef,
} from "../services/dashboardApi";
import {
  idle,
  LevelChip,
  Metric,
  SectionCard,
  SectionState,
} from "../components/SectionCard";

type Side = "base" | "enhancement";

const errMsg = (e: unknown) => (e instanceof Error ? e.message : String(e));

function useSection<T>() {
  const [state, setState] = useState<SectionState<T>>(idle<T>());
  const run = (fn: () => Promise<T>) => {
    setState({ status: "loading" });
    return fn().then(
      (data) => setState({ status: "done", data }),
      (e) => setState({ status: "error", error: errMsg(e) }),
    );
  };
  return [state, run, () => setState(idle<T>())] as const;
}

function RepoPicker({
  label,
  repos,
  repoId,
  path,
  onRepo,
  onPath,
}: {
  label: string;
  repos: RepositoryMetadata[];
  repoId: string;
  path: string;
  onRepo: (v: string) => void;
  onPath: (v: string) => void;
}) {
  return (
    <Stack spacing={1} sx={{ flex: 1, minWidth: 0 }}>
      <Typography variant="subtitle2">{label}</Typography>
      <TextField
        select
        label="Ingested repository"
        value={repoId}
        onChange={(e) => onRepo(e.target.value)}
        fullWidth
      >
        <MenuItem value="">
          <em>None</em>
        </MenuItem>
        {repos.map((r) => (
          <MenuItem key={r.id} value={r.id}>
            {r.source.split(/[\\/]/).slice(-2).join("/")} ({r.branch})
          </MenuItem>
        ))}
      </TextField>
      <TextField
        label="…or local path (overrides)"
        value={path}
        onChange={(e) => onPath(e.target.value)}
        fullWidth
      />
    </Stack>
  );
}

function CategoryRow({
  name,
  c,
}: {
  name: string;
  c: ComparisonResult["modules"];
}) {
  return (
    <TableRow>
      <TableCell>{name}</TableCell>
      <TableCell align="right">{c.base}</TableCell>
      <TableCell align="right">{c.enhancement}</TableCell>
      <TableCell align="right">{c.common}</TableCell>
      <TableCell align="right">{c.onlyInEnhancement.length}</TableCell>
      <TableCell align="right">{c.modified.length}</TableCell>
    </TableRow>
  );
}

export default function DashboardPage() {
  const [repos, setRepos] = useState<RepositoryMetadata[]>([]);
  const [ids, setIds] = useState<Record<Side, string>>({
    base: "",
    enhancement: "",
  });
  const [paths, setPaths] = useState<Record<Side, string>>({
    base: "",
    enhancement: "",
  });
  const [side, setSide] = useState<Side>("base");
  const [running, setRunning] = useState(false);

  const [arch, runArch] = useSection<Record<Side, ArchitectureSummary>>();
  const [feat, runFeat] = useSection<Record<Side, FeatureResult>>();
  const [cmp, runCmp] = useSection<ComparisonResult>();
  const [rec, runRec] = useSection<RecommendationResult>();
  const [plan, runPlan] = useSection<PlanResult>();

  useEffect(() => {
    repositoryApi
      .list()
      .then(setRepos)
      .catch(() => undefined);
  }, []);

  const ref = (s: Side): RepoRef =>
    paths[s].trim() ? { path: paths[s].trim() } : { repositoryId: ids[s] };
  const ready = (s: Side) => Boolean(paths[s].trim() || ids[s]);
  const canRun = ready("base") && ready("enhancement") && !running;

  const selected = useMemo(
    () =>
      (["base", "enhancement"] as Side[]).map((s) => ({
        side: s,
        meta: repos.find((r) => r.id === ids[s]),
      })),
    [repos, ids],
  );

  const runAll = async () => {
    const b = ref("base");
    const e = ref("enhancement");
    setRunning(true);
    await Promise.all([
      runArch(async () => {
        const [base, enhancement] = await Promise.all([
          dashboardApi.architecture(b),
          dashboardApi.architecture(e),
        ]);
        return { base, enhancement };
      }),
      runFeat(async () => {
        const [base, enhancement] = await Promise.all([
          dashboardApi.features(b),
          dashboardApi.features(e),
        ]);
        return { base, enhancement };
      }),
      runCmp(() => dashboardApi.comparison(b, e)),
      runRec(() => dashboardApi.recommendation(b, e)),
      runPlan(() => dashboardApi.plan(b, e)),
    ]);
    setRunning(false);
  };

  const sideToggle = (
    <ToggleButtonGroup
      size="small"
      exclusive
      value={side}
      onChange={(_, v) => v && setSide(v)}
    >
      <ToggleButton value="base">Base</ToggleButton>
      <ToggleButton value="enhancement">Enhancement</ToggleButton>
    </ToggleButtonGroup>
  );

  return (
    <Box>
      <Stack
        direction="row"
        alignItems="center"
        spacing={2}
        sx={{ mb: 2 }}
        flexWrap="wrap"
      >
        <Box sx={{ flexGrow: 1 }}>
          <Typography variant="h5">Enterprise dashboard</Typography>
          <Typography variant="body2" color="text.secondary">
            Onboarding analysis of a base application and its enhancement.
          </Typography>
        </Box>
        <Button
          variant="contained"
          size="large"
          onClick={runAll}
          disabled={!canRun}
        >
          {running ? "Analyzing…" : "Run analysis"}
        </Button>
      </Stack>

      <Paper sx={{ p: 2, mb: 2 }}>
        <Stack direction={{ xs: "column", md: "row" }} spacing={3}>
          <RepoPicker
            label="Base application"
            repos={repos}
            repoId={ids.base}
            path={paths.base}
            onRepo={(v) => setIds({ ...ids, base: v })}
            onPath={(v) => setPaths({ ...paths, base: v })}
          />
          <Divider
            orientation="vertical"
            flexItem
            sx={{ display: { xs: "none", md: "block" } }}
          />
          <RepoPicker
            label="Enhancement application"
            repos={repos}
            repoId={ids.enhancement}
            path={paths.enhancement}
            onRepo={(v) => setIds({ ...ids, enhancement: v })}
            onPath={(v) => setPaths({ ...paths, enhancement: v })}
          />
        </Stack>
        {running && <LinearProgress sx={{ mt: 2 }} />}
      </Paper>

      <Grid container spacing={2}>
        {/* Repository status */}
        <Grid item xs={12} md={6} lg={4}>
          <SectionCard
            title="Repository Status"
            subtitle="Ingested repositories"
            state={{
              status: selected.some((s) => s.meta) ? "done" : "idle",
              data: selected,
            }}
          >
            {(items) => (
              <Stack spacing={2} divider={<Divider flexItem />}>
                {items.map(({ side: s, meta }) => (
                  <Box key={s}>
                    <Stack
                      direction="row"
                      spacing={1}
                      alignItems="center"
                      sx={{ mb: 0.5 }}
                    >
                      <Chip
                        size="small"
                        color={s === "base" ? "primary" : "secondary"}
                        label={s}
                      />
                      <Typography variant="subtitle2" noWrap>
                        {meta
                          ? meta.source.split(/[\\/]/).pop()
                          : paths[s] || "Not selected"}
                      </Typography>
                    </Stack>
                    {meta ? (
                      <Typography variant="body2" color="text.secondary">
                        Branch <b>{meta.branch}</b> · {meta.commit_count}{" "}
                        commits · {meta.source_type}
                        <br />
                        {meta.head.sha.slice(0, 7)} “{meta.head.message}” –{" "}
                        {meta.head.author}
                      </Typography>
                    ) : (
                      <Typography variant="body2" color="text.secondary">
                        {paths[s]
                          ? "Local path (not ingested)"
                          : "Select an ingested repository."}
                      </Typography>
                    )}
                  </Box>
                ))}
              </Stack>
            )}
          </SectionCard>
        </Grid>

        {/* Architecture */}
        <Grid item xs={12} md={6} lg={4}>
          <SectionCard
            title="Architecture Analysis"
            subtitle="Modules, routes, APIs and dependencies"
            state={arch}
            action={sideToggle}
          >
            {(d) => {
              const a = d[side];
              const s = a.summary;
              return (
                <Stack spacing={2}>
                  <Typography variant="subtitle2">
                    {a.applicationName}
                  </Typography>
                  <Stack direction="row" spacing={3} flexWrap="wrap" useFlexGap>
                    {Object.entries(s)
                      .slice(0, 8)
                      .map(([k, v]) => (
                        <Metric
                          key={k}
                          label={k.replace(/([A-Z])/g, " $1").toLowerCase()}
                          value={v}
                        />
                      ))}
                  </Stack>
                  <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
                    {a.moduleMap.nodes.map((n) => (
                      <Chip
                        key={n.name}
                        size="small"
                        variant="outlined"
                        label={`${n.name} · ${n.type} · ${n.fileCount} files`}
                      />
                    ))}
                  </Stack>
                </Stack>
              );
            }}
          </SectionCard>
        </Grid>

        {/* Features */}
        <Grid item xs={12} md={12} lg={4}>
          <SectionCard
            title="Feature Analysis"
            subtitle="AI-derived capabilities (Azure OpenAI)"
            state={feat}
            action={sideToggle}
          >
            {(d) => {
              const f = d[side];
              return (
                <Stack spacing={1.5}>
                  <Typography variant="body2">{f.summary}</Typography>
                  <Chip
                    size="small"
                    color="primary"
                    label={`Overall confidence ${f.overallConfidence}%`}
                    sx={{ alignSelf: "flex-start" }}
                  />
                  <Typography variant="subtitle2">Capabilities</Typography>
                  <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
                    {f.businessCapabilities.map((c) => (
                      <Chip
                        key={c.name}
                        size="small"
                        label={`${c.name} · ${c.confidence}%`}
                        title={c.description}
                      />
                    ))}
                  </Stack>
                  <Typography variant="subtitle2">Features</Typography>
                  <List dense disablePadding>
                    {f.features.slice(0, 8).map((x) => (
                      <ListItem key={x.name} disableGutters>
                        <ListItemText primary={x.name} secondary={x.summary} />
                      </ListItem>
                    ))}
                  </List>
                </Stack>
              );
            }}
          </SectionCard>
        </Grid>

        {/* Comparison */}
        <Grid item xs={12} lg={7}>
          <SectionCard
            title="Comparison Results"
            subtitle="Base vs. enhancement"
            state={cmp}
          >
            {(c) => (
              <Stack spacing={2}>
                <Box sx={{ overflowX: "auto" }}>
                  <Table size="small">
                    <TableHead>
                      <TableRow>
                        <TableCell>Category</TableCell>
                        <TableCell align="right">Base</TableCell>
                        <TableCell align="right">Enh.</TableCell>
                        <TableCell align="right">Common</TableCell>
                        <TableCell align="right">New</TableCell>
                        <TableCell align="right">Changed</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      <CategoryRow name="Modules" c={c.modules} />
                      <CategoryRow name="Routes" c={c.routes} />
                      <CategoryRow name="APIs" c={c.apis} />
                      <CategoryRow name="Services" c={c.services} />
                      <CategoryRow name="Entities" c={c.entities} />
                    </TableBody>
                  </Table>
                </Box>
                <Typography variant="subtitle2">
                  Integration candidates ({c.integrationCandidates.length})
                </Typography>
                <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
                  {c.integrationCandidates.slice(0, 12).map((i) => (
                    <Chip
                      key={`${i.kind}:${i.name}`}
                      size="small"
                      variant="outlined"
                      color={
                        i.risk === "high"
                          ? "error"
                          : i.risk === "medium"
                            ? "warning"
                            : "success"
                      }
                      label={`${i.order}. ${i.action} ${i.kind} ${i.name}`}
                    />
                  ))}
                </Stack>
              </Stack>
            )}
          </SectionCard>
        </Grid>

        {/* Recommendations */}
        <Grid item xs={12} lg={5}>
          <SectionCard
            title="Recommendations"
            subtitle="Where to integrate the enhancement"
            state={rec}
          >
            {(r) =>
              r.recommendations.length === 0 ? (
                <Typography variant="body2">
                  No integration points found.
                </Typography>
              ) : (
                <List disablePadding>
                  {r.recommendations.map((x) => (
                    <ListItem
                      key={x.rank}
                      disableGutters
                      divider
                      alignItems="flex-start"
                    >
                      <ListItemText
                        primary={
                          <Stack
                            direction="row"
                            spacing={1}
                            alignItems="center"
                          >
                            <Typography
                              variant="subtitle2"
                              sx={{ wordBreak: "break-all" }}
                            >
                              {x.rank}. {x.filePath}
                            </Typography>
                            <Chip
                              size="small"
                              color="primary"
                              label={x.confidenceLabel || `${x.confidence}%`}
                            />
                          </Stack>
                        }
                        secondary={`${x.action} – ${x.reason}`}
                      />
                    </ListItem>
                  ))}
                </List>
              )
            }
          </SectionCard>
        </Grid>

        {/* Plan */}
        <Grid item xs={12}>
          <SectionCard
            title="Implementation Plan"
            subtitle="Phased tasks with files, dependencies and validation"
            state={plan}
            minHeight={120}
          >
            {(p) => (
              <Stack spacing={2}>
                <Stack
                  direction="row"
                  spacing={4}
                  alignItems="center"
                  flexWrap="wrap"
                  useFlexGap
                >
                  <Metric
                    label="overall impact"
                    value={<LevelChip level={p.overallImpact} />}
                  />
                  <Metric
                    label="impact score"
                    value={`${p.overallScore}/100`}
                  />
                  <Metric label="tasks" value={p.taskCount} />
                </Stack>
                {p.phases.map((ph) => (
                  <Accordion
                    key={ph.number}
                    defaultExpanded={ph.number === 1}
                    disableGutters
                  >
                    <AccordionSummary expandIcon={<span>▾</span>}>
                      <Typography variant="subtitle2">
                        Phase {ph.number} – {ph.name} ({ph.tasks.length})
                      </Typography>
                    </AccordionSummary>
                    <AccordionDetails>
                      {ph.tasks.length === 0 && (
                        <Typography variant="body2">
                          No tasks in this phase.
                        </Typography>
                      )}
                      <Stack spacing={2} divider={<Divider flexItem />}>
                        {ph.tasks.map((t) => (
                          <Box key={t.id}>
                            <Stack
                              direction="row"
                              spacing={1}
                              alignItems="center"
                              flexWrap="wrap"
                              useFlexGap
                            >
                              <Typography variant="subtitle2">
                                {t.id}: {t.title}
                              </Typography>
                              <LevelChip level={t.level} />
                              <Chip
                                size="small"
                                label={`Effort ${t.effort}`}
                                variant="outlined"
                              />
                            </Stack>
                            <Typography
                              variant="body2"
                              color="text.secondary"
                              sx={{ my: 0.5 }}
                            >
                              {t.description.length > 240
                                ? `${t.description.slice(0, 240)}…`
                                : t.description}
                            </Typography>
                            <Typography variant="caption">
                              <b>Files:</b>{" "}
                              {t.files.length
                                ? t.files.join(", ")
                                : "repository-wide"}{" "}
                              · <b>Depends on:</b>{" "}
                              {t.dependsOn.length
                                ? t.dependsOn.join(", ")
                                : "none"}
                            </Typography>
                            <ul style={{ margin: "4px 0 0", paddingLeft: 20 }}>
                              {t.validation.map((v) => (
                                <li key={v}>
                                  <Typography variant="caption">{v}</Typography>
                                </li>
                              ))}
                            </ul>
                          </Box>
                        ))}
                      </Stack>
                    </AccordionDetails>
                  </Accordion>
                ))}
              </Stack>
            )}
          </SectionCard>
        </Grid>
      </Grid>
    </Box>
  );
}

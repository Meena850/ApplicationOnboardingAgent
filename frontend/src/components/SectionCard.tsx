import { ReactNode } from "react";
import {
  Alert,
  Box,
  Chip,
  LinearProgress,
  Paper,
  Typography,
} from "@mui/material";

export type Status = "idle" | "loading" | "done" | "error";

export interface SectionState<T> {
  status: Status;
  data?: T;
  error?: string;
}

export const idle = <T,>(): SectionState<T> => ({ status: "idle" });

export function SectionCard<T>({
  title,
  subtitle,
  state,
  children,
  action,
  minHeight = 220,
}: {
  title: string;
  subtitle?: string;
  state: SectionState<T>;
  children: (data: T) => ReactNode;
  action?: ReactNode;
  minHeight?: number;
}) {
  return (
    <Paper
      sx={{
        height: "100%",
        display: "flex",
        flexDirection: "column",
        overflow: "hidden",
      }}
    >
      <Box
        sx={{
          px: 2,
          py: 1.5,
          display: "flex",
          alignItems: "center",
          gap: 1,
          borderBottom: "1px solid",
          borderColor: "divider",
        }}
      >
        <Box sx={{ flexGrow: 1, minWidth: 0 }}>
          <Typography variant="h6">{title}</Typography>
          {subtitle && (
            <Typography variant="caption" color="text.secondary">
              {subtitle}
            </Typography>
          )}
        </Box>
        {action}
      </Box>
      {state.status === "loading" && <LinearProgress />}
      <Box sx={{ p: 2, flexGrow: 1, minHeight, overflow: "auto" }}>
        {state.status === "idle" && (
          <Typography color="text.secondary" variant="body2">
            Select repositories and run the analysis.
          </Typography>
        )}
        {state.status === "error" && (
          <Alert severity="error">{state.error}</Alert>
        )}
        {state.status === "done" &&
          state.data !== undefined &&
          children(state.data)}
      </Box>
    </Paper>
  );
}

export function Metric({
  label,
  value,
  color,
}: {
  label: string;
  value: ReactNode;
  color?: string;
}) {
  return (
    <Box sx={{ minWidth: 80 }}>
      <Typography
        variant="h5"
        sx={{ color: color ?? "primary.main", lineHeight: 1.1 }}
      >
        {value}
      </Typography>
      <Typography variant="caption" color="text.secondary">
        {label}
      </Typography>
    </Box>
  );
}

const LEVEL: Record<string, "success" | "warning" | "error" | "default"> = {
  low: "success",
  medium: "warning",
  high: "error",
};

export function LevelChip({ level }: { level: string }) {
  return (
    <Chip
      size="small"
      label={level}
      color={LEVEL[level.toLowerCase()] ?? "default"}
      variant="outlined"
    />
  );
}

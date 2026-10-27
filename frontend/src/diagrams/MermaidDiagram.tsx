import { useEffect, useRef, useState } from "react";
import { Alert, Box, Button, Collapse, Typography } from "@mui/material";
import mermaid from "mermaid";

mermaid.initialize({
  startOnLoad: false,
  securityLevel: "strict",
  theme: "default",
  // Render labels as native SVG <text>; HTML labels (foreignObject) were
  // invisible here, leaving empty boxes.
  htmlLabels: false,
  flowchart: { htmlLabels: false, useMaxWidth: false },
  themeVariables: { fontFamily: '"Segoe UI", Arial, sans-serif' },
});

let counter = 0;

export default function MermaidDiagram({ code }: { code: string }) {
  const ref = useRef<HTMLDivElement>(null);
  const [error, setError] = useState<string | null>(null);
  const [showCode, setShowCode] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setError(null);
    mermaid
      .render(`mmd-${++counter}`, code)
      .then(({ svg }) => {
        if (!cancelled && ref.current) ref.current.innerHTML = svg;
      })
      .catch((e) => !cancelled && setError(String(e?.message ?? e)));
    return () => {
      cancelled = true;
    };
  }, [code]);

  return (
    <Box>
      {error && (
        <Alert severity="error">Could not render diagram: {error}</Alert>
      )}
      <Box ref={ref} sx={{ overflow: "auto", py: 1 }} />
      <Button size="small" onClick={() => setShowCode((v) => !v)}>
        {showCode ? "Hide" : "Show"} Mermaid code
      </Button>
      <Button size="small" onClick={() => navigator.clipboard.writeText(code)}>
        Copy
      </Button>
      <Collapse in={showCode}>
        <Typography
          component="pre"
          variant="caption"
          sx={{ bgcolor: "grey.100", p: 1, overflow: "auto" }}
        >
          {code}
        </Typography>
      </Collapse>
    </Box>
  );
}

import { createTheme } from "@mui/material";

// Fluent-inspired: Segoe UI, Microsoft blue, neutral greys, small radii, soft depth.
export const fluentTheme = createTheme({
  palette: {
    primary: { main: "#0078d4", dark: "#106ebe", light: "#2b88d8" },
    secondary: { main: "#8764b8" },
    success: { main: "#107c10" },
    warning: { main: "#ffaa44" },
    error: { main: "#d13438" },
    background: { default: "#faf9f8", paper: "#ffffff" },
    text: { primary: "#323130", secondary: "#605e5c" },
    divider: "#edebe9",
  },
  shape: { borderRadius: 4 },
  typography: {
    fontFamily:
      '"Segoe UI", "Segoe UI Web", -apple-system, BlinkMacSystemFont, Roboto, "Helvetica Neue", sans-serif',
    h5: { fontWeight: 600 },
    h6: { fontWeight: 600, fontSize: "1rem" },
    subtitle2: { fontWeight: 600 },
    button: { textTransform: "none", fontWeight: 600 },
  },
  components: {
    MuiAppBar: {
      defaultProps: { elevation: 0 },
      styleOverrides: { root: { backgroundColor: "#0078d4" } },
    },
    MuiPaper: {
      defaultProps: { elevation: 0 },
      styleOverrides: {
        root: {
          border: "1px solid #edebe9",
          boxShadow:
            "0 1.6px 3.6px rgba(0,0,0,.13), 0 0.3px 0.9px rgba(0,0,0,.11)",
        },
      },
    },
    MuiButton: { defaultProps: { disableElevation: true } },
    MuiChip: { styleOverrides: { root: { borderRadius: 2, fontWeight: 600 } } },
    MuiTextField: { defaultProps: { size: "small" } },
  },
});

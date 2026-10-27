import { AppBar, Button, Toolbar, Typography } from "@mui/material";
import { Link } from "react-router-dom";

export default function NavBar() {
  return (
    <AppBar position="static">
      <Toolbar>
        <Typography variant="h6" sx={{ flexGrow: 1 }}>
          Application Onboarding Agent
        </Typography>
        <Button color="inherit" component={Link} to="/">
          Home
        </Button>
        <Button color="inherit" component={Link} to="/dashboard">
          Dashboard
        </Button>
        <Button color="inherit" component={Link} to="/repositories">
          Repositories
        </Button>
        <Button color="inherit" component={Link} to="/diagrams">
          Diagrams
        </Button>
        <Button color="inherit" component={Link} to="/onboardings">
          Onboardings
        </Button>
      </Toolbar>
    </AppBar>
  );
}

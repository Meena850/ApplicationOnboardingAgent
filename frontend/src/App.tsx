import { Route, Routes } from "react-router-dom";
import { Container } from "@mui/material";
import NavBar from "./components/NavBar";
import HomePage from "./pages/HomePage";
import DiagramsPage from "./pages/DiagramsPage";
import DashboardPage from "./pages/DashboardPage";
import OnboardingsPage from "./pages/OnboardingsPage";
import RepositoryIngestionPage from "./pages/RepositoryIngestionPage";

export default function App() {
  return (
    <>
      <NavBar />
      <Container sx={{ mt: 4 }}>
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/onboardings" element={<OnboardingsPage />} />
          <Route path="/repositories" element={<RepositoryIngestionPage />} />
          <Route path="/diagrams" element={<DiagramsPage />} />
          <Route path="/dashboard" element={<DashboardPage />} />
        </Routes>
      </Container>
    </>
  );
}

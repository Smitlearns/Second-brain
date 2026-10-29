import { StrictMode, useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, NavLink, Route, Routes, useLocation } from "react-router-dom";
import { getNotes } from "./api";
import { duePlans } from "./notes";
import AskPage from "./pages/AskPage";
import DashboardPage from "./pages/DashboardPage";
import NotePage from "./pages/NotePage";
import NotesPage from "./pages/NotesPage";
import { setTheme, useTheme } from "./theme";
import "./style.css";

function App() {
  const { pathname } = useLocation();
  const theme = useTheme();
  const [due, setDue] = useState(0);

  // checked on every page change, so ticking off or saving a plan updates the badge soon after
  useEffect(() => {
    getNotes().then((notes) => setDue(duePlans(notes).length), () => {});
  }, [pathname]);

  return (
    <>
      <nav className="nav">
        <NavLink to="/" end>Notes</NavLink>
        <NavLink to="/ask">Ask</NavLink>
        <NavLink to="/dashboard">
          Dashboard
          {due > 0 && <span className="badge" title={`${due} plan${due === 1 ? "" : "s"} due soon`}>{due}</span>}
        </NavLink>
        <button type="button" className="theme-toggle" onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
          aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} mode`}>
          {theme === "dark" ? "☀️ Light" : "🌙 Dark"}
        </button>
      </nav>
      <Routes>
        <Route path="/" element={<NotesPage />} />
        <Route path="/ask" element={<AskPage />} />
        <Route path="/ask/:chatId" element={<AskPage />} />
        <Route path="/dashboard" element={<DashboardPage />} />
        <Route path="/dashboard/notes/:noteId" element={<NotePage />} />
        <Route path="*" element={<main><h1>Page not found</h1></main>} />
      </Routes>
    </>
  );
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </StrictMode>,
);

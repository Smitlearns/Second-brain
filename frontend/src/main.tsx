import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, NavLink, Route, Routes } from "react-router-dom";
import AskPage from "./pages/AskPage";
import DashboardPage from "./pages/DashboardPage";
import NotePage from "./pages/NotePage";
import NotesPage from "./pages/NotesPage";
import "./style.css";

function App() {
  return (
    <>
      <nav className="nav">
        <NavLink to="/" end>Notes</NavLink>
        <NavLink to="/ask">Ask</NavLink>
        <NavLink to="/dashboard">Dashboard</NavLink>
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

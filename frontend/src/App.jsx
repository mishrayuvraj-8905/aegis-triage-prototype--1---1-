import { Routes, Route } from "react-router-dom";
import Nav from "./components/Nav.jsx";
import WaitingRoom from "./pages/WaitingRoom.jsx";
import Intake from "./pages/Intake.jsx";
import PatientDetail from "./pages/PatientDetail.jsx";

export default function App() {
  return (
    <div className="min-h-screen bg-bone font-body text-ink">
      <Nav />
      <main className="mx-auto max-w-7xl px-6 py-8">
        <Routes>
          <Route path="/" element={<WaitingRoom />} />
          <Route path="/intake" element={<Intake />} />
          <Route path="/patients/:id" element={<PatientDetail />} />
        </Routes>
      </main>
    </div>
  );
}

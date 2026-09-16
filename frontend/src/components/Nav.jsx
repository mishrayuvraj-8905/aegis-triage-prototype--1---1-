import { NavLink } from "react-router-dom";

const linkBase = "px-4 py-2 text-sm font-medium rounded-md transition-colors";

export default function Nav() {
  return (
    <header className="sticky top-0 z-40 border-b border-teal-700/40 bg-teal-950 text-bone">
      <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-3">
        <div className="flex items-center gap-3">
          <div className="flex h-8 w-8 items-center justify-center rounded-md bg-teal-700 font-display text-sm font-bold text-bone">
            AT
          </div>
          <div>
            <div className="font-display text-lg font-semibold leading-none tracking-tight">Aegis Triage</div>
            <div className="text-[11px] uppercase tracking-widest text-teal-400">AI co-pilot &middot; nurse decides</div>
          </div>
        </div>
        <nav className="flex items-center gap-1">
          <NavLink
            to="/"
            end
            className={({ isActive }) =>
              `${linkBase} ${isActive ? "bg-teal-700 text-bone" : "text-teal-400 hover:bg-teal-900 hover:text-bone"}`
            }
          >
            Waiting Room
          </NavLink>
          <NavLink
            to="/intake"
            className={({ isActive }) =>
              `${linkBase} ${isActive ? "bg-teal-700 text-bone" : "text-teal-400 hover:bg-teal-900 hover:text-bone"}`
            }
          >
            Intake
          </NavLink>
        </nav>
      </div>
    </header>
  );
}

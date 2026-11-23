// Small line icons for the portal sidebars (24x24, stroke follows the text colour).
const PATHS = {
  home: "M3 11l9-8 9 8M5 10v10h5v-6h4v6h5V10",
  list: "M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01",
  calendar: "M4 6h16v14H4zM4 10h16M8 3v4M16 3v4",
  wallet: "M3 7h16a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2zM3 7V6a2 2 0 012-2h12M16 14h2",
  bell: "M6 16V11a6 6 0 1112 0v5l2 2H4zM10 21h4",
  user: "M12 12a4 4 0 100-8 4 4 0 000 8zM4 21a8 8 0 0116 0",
  card: "M3 6h18v12H3zM3 10h18M7 15h4",
  logout: "M10 4H5v16h5M15 8l4 4-4 4M19 12H9",
  users: "M9 11a3.5 3.5 0 100-7 3.5 3.5 0 000 7zM2 20a7 7 0 0114 0M17 4a3.5 3.5 0 010 7M22 20a7 7 0 00-4-6.3",
  grid: "M4 4h7v7H4zM13 4h7v7h-7zM4 13h7v7H4zM13 13h7v7h-7z",
  tool: "M14 6a4 4 0 005 5l-9 9a2 2 0 01-3-3l9-9a4 4 0 00-2-2zM15 5l3 3",
  star: "M12 3l2.8 5.7 6.2.9-4.5 4.4 1 6.2L12 17.3 6.5 20.2l1-6.2L3 9.6l6.2-.9z",
  tag: "M3 12l9-9h8v8l-9 9zM16 8h.01",
  pin: "M12 21s7-6 7-11a7 7 0 10-14 0c0 5 7 11 7 11zM12 12a2 2 0 100-4 2 2 0 000 4z",
  settings: "M12 15a3 3 0 100-6 3 3 0 000 6zM19 12l2-1-2-4-2 .6-1.5-1L15 4H9l-.5 2.6-1.5 1L5 7l-2 4 2 1v1l-2 1 2 4 2-.6 1.5 1L9 20h6l.5-2.6 1.5-1 2 .6 2-4-2-1z",
  search: "M11 18a7 7 0 100-14 7 7 0 000 14zM20 20l-4-4",
  home2: "M4 11l8-7 8 7v9H4z",
};

export default function NavIcon({ name, size = 18 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d={PATHS[name] ?? PATHS.grid} />
    </svg>
  );
}

const paths = {
  file: "M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z M14 2v6h6 M8 13h8 M8 17h5",
  upload: "M12 16V3 M7 8l5-5 5 5 M3 15v5a1 1 0 0 0 1 1h16a1 1 0 0 0 1-1v-5",
  arrow: "M5 12h14 M13 6l6 6-6 6",
  check: "M5 12l4 4L19 6",
  shield: "M12 3l8 3v6c0 5-8 9-8 9S4 17 4 12V6z M8 12l3 3 5-6",
  chat: "M21 11a8 8 0 0 1-8 8H5l-3 3V11a9 9 0 0 1 19 0z M7 10h10 M7 14h6",
  close: "M6 6l12 12 M6 18L18 6",
  download: "M12 3v12 M7 10l5 5 5-5 M4 17v4h16v-4",
  trash: "M3 6h18 M9 6V3h6v3 M5 6l1 15h12l1-15 M10 10v7 M14 10v7",
  alert: "M12 3L2 21h20z M12 9v5 M12 17h.01",
  exit: "M9 3H4v18h5 M9 12h12 M16 7l5 5-5 5",
  book: "M3 3h7l2 2 2-2h7v17h-7l-2 2-2-2H3z M12 5v17",
  plus: "M12 5v14 M5 12h14"
  ,search: "M21 21l-5-5 M18 10a8 8 0 1 1-16 0 8 8 0 0 1 16 0"
  ,grid: "M3 3h7v7H3z M14 3h7v7h-7z M3 14h7v7H3z M14 14h7v7h-7z"
  ,menu: "M4 6h16 M4 12h16 M4 18h16"
  ,chevron: "M9 5l7 7-7 7"
  ,clock: "M12 8v5l3 2 M22 12a10 10 0 1 1-20 0 10 10 0 0 1 20 0"
  ,sparkles: "M12 3l2.5 6.5L21 12l-6.5 2.5L12 21l-2.5-6.5L3 12l6.5-2.5z M20 2v4 M18 4h4"
  ,eye: "M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7 M15 12a3 3 0 1 1-6 0 3 3 0 0 1 6 0"
  ,eyeOff: "M3 3l18 18 M10 5c6-1 10 5 12 7l-3 4 M6 6C4 8 2 12 2 12s3 7 10 7c2 0 4-1 5-2 M10 10a3 3 0 0 0 4 4"
};
export default function Icon({ name = "file", size = 20 }) {
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={paths[name] || paths.file} /></svg>;
}
export function Brand() { return <div className="brand"><span className="brand-symbol"><Icon name="book" size={22}/></span>SimplyDoc</div>; }

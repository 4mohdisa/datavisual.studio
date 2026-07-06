// Next.js re-mounts template.js on every route change (unlike layout.js, which
// persists). Wrapping page content here means the fade+lift in globals.css
// plays on each navigation, giving smooth page-to-page transitions.
export default function Template({ children }) {
  return <div className="page-transition">{children}</div>;
}

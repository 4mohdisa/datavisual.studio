// Shimmering placeholder block (animation defined in globals.css).
export default function Skeleton({ className = '', style }) {
  return <div className={`skeleton ${className}`} style={style} />;
}

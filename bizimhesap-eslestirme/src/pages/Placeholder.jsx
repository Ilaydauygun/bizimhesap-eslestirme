export default function Placeholder({ title, note }) {
  return <div className="bh-alert">{title}: {note || "Bu sayfa prototip kapsamı dışındadır."}</div>;
}

export default function AdminLoading() {
  return (
    <div style={{ padding: "24px 0", display: "flex", flexDirection: "column", gap: 14 }}>
      <Skeleton width="35%" height={26} />
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12, marginTop: 4 }}>
        <Skeleton height={88} />
        <Skeleton height={88} />
        <Skeleton height={88} />
        <Skeleton height={88} />
      </div>
      <Skeleton height={240} />
      <Skeleton height={120} />
    </div>
  );
}

function Skeleton({ width = "100%", height = 20 }: { width?: string | number; height?: number }) {
  return (
    <div
      style={{
        width,
        height,
        borderRadius: 10,
        background: "linear-gradient(90deg, #f1f5f9 25%, #e2e8f0 50%, #f1f5f9 75%)",
        backgroundSize: "200% 100%",
        animation: "shimmer 1.4s infinite",
      }}
    />
  );
}

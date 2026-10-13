export default function DashboardLoading() {
  return (
    <div style={{ padding: "32px 0", display: "flex", flexDirection: "column", gap: 16 }}>
      <Skeleton width="40%" height={28} />
      <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 16, marginTop: 8 }}>
        <Skeleton height={96} />
        <Skeleton height={96} />
        <Skeleton height={96} />
      </div>
      <Skeleton height={200} />
      <Skeleton height={140} />
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

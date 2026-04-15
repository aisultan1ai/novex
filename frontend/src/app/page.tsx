import type { CSSProperties } from "react";

export default function HomePage() {
  const cardStyle: CSSProperties = {
    border: "1px solid #e5e7eb",
    borderRadius: 16,
    padding: 20,
    background: "#ffffff",
    boxShadow: "0 8px 24px rgba(15, 23, 42, 0.06)",
  };

  const badgeStyle: CSSProperties = {
    display: "inline-block",
    padding: "6px 10px",
    borderRadius: 999,
    background: "#eff6ff",
    color: "#1d4ed8",
    fontSize: 12,
    fontWeight: 700,
  };

  const buttonPrimary: CSSProperties = {
    background: "#0f172a",
    color: "#ffffff",
    border: "none",
    borderRadius: 12,
    padding: "12px 18px",
    fontSize: 14,
    fontWeight: 600,
    cursor: "pointer",
  };

  const buttonSecondary: CSSProperties = {
    background: "#ffffff",
    color: "#0f172a",
    border: "1px solid #cbd5e1",
    borderRadius: 12,
    padding: "12px 18px",
    fontSize: 14,
    fontWeight: 600,
    cursor: "pointer",
  };

  const inputStyle: CSSProperties = {
    width: "100%",
    padding: "12px 14px",
    borderRadius: 12,
    border: "1px solid #cbd5e1",
    fontSize: 14,
    outline: "none",
    boxSizing: "border-box",
  };

  const labelStyle: CSSProperties = {
    display: "block",
    fontSize: 13,
    fontWeight: 600,
    marginBottom: 8,
    color: "#334155",
  };

  return (
    <main
      style={{
        minHeight: "100vh",
        background:
          "linear-gradient(180deg, #f8fafc 0%, #eef2ff 100%)",
        padding: "32px 20px 64px",
        color: "#0f172a",
        fontFamily:
          "Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
      }}
    >
      <div style={{ maxWidth: 1200, margin: "0 auto" }}>
        <header
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            gap: 16,
            marginBottom: 40,
            flexWrap: "wrap",
          }}
        >
          <div>
            <div style={badgeStyle}>Novex MVP</div>
            <h1
              style={{
                margin: "16px 0 8px",
                fontSize: 40,
                lineHeight: 1.1,
                fontWeight: 800,
              }}
            >
              Агрегатор курьерских служб
            </h1>
            <p
              style={{
                margin: 0,
                maxWidth: 760,
                fontSize: 16,
                lineHeight: 1.6,
                color: "#475569",
              }}
            >
              Единый интерфейс для расчёта тарифа, выбора службы доставки,
              оформления отправления, оплаты и дальнейшего трекинга заказа.
            </p>
          </div>

          <div style={{ display: "flex", gap: 12 }}>
            <a href="/login" style={{ textDecoration: "none" }}>
              <button style={buttonSecondary}>Войти</button>
            </a>
            <a href="/register" style={{ textDecoration: "none" }}>
              <button style={buttonPrimary}>Регистрация</button>
            </a>
          </div>
        </header>

        <section
          style={{
            display: "grid",
            gridTemplateColumns: "1.3fr 0.7fr",
            gap: 24,
            alignItems: "start",
          }}
        >
          <div style={cardStyle}>
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                gap: 16,
                flexWrap: "wrap",
                alignItems: "center",
                marginBottom: 24,
              }}
            >
              <div>
                <h2 style={{ margin: "0 0 8px", fontSize: 24 }}>
                  Короткая форма отправления
                </h2>
                <p
                  style={{
                    margin: 0,
                    color: "#64748b",
                    fontSize: 14,
                    lineHeight: 1.6,
                  }}
                >
                  Это будущая стартовая форма для расчёта тарифов. На следующем
                  этапе сюда подключим backend endpoint расчёта и выдачу
                  предложений по службам.
                </p>
              </div>
              <span style={badgeStyle}>Skeleton stage</span>
            </div>

            <form
              onSubmit={(e) => e.preventDefault()}
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(2, minmax(0, 1fr))",
                gap: 16,
              }}
            >
              <div>
                <label style={labelStyle}>Откуда: страна</label>
                <input style={inputStyle} placeholder="Казахстан" />
              </div>

              <div>
                <label style={labelStyle}>Откуда: город</label>
                <input style={inputStyle} placeholder="Алматы" />
              </div>

              <div>
                <label style={labelStyle}>Куда: страна</label>
                <input style={inputStyle} placeholder="Казахстан" />
              </div>

              <div>
                <label style={labelStyle}>Куда: город</label>
                <input style={inputStyle} placeholder="Астана" />
              </div>

              <div>
                <label style={labelStyle}>Тип отправления</label>
                <select style={inputStyle} defaultValue="parcel">
                  <option value="parcel">Посылка</option>
                  <option value="document">Документ</option>
                </select>
              </div>

              <div>
                <label style={labelStyle}>Вес, кг</label>
                <input style={inputStyle} placeholder="2.5" />
              </div>

              <div>
                <label style={labelStyle}>Количество</label>
                <input style={inputStyle} placeholder="1" />
              </div>

              <div>
                <label style={labelStyle}>Ширина, см</label>
                <input style={inputStyle} placeholder="20" />
              </div>

              <div>
                <label style={labelStyle}>Высота, см</label>
                <input style={inputStyle} placeholder="15" />
              </div>

              <div>
                <label style={labelStyle}>Глубина, см</label>
                <input style={inputStyle} placeholder="10" />
              </div>

              <div style={{ gridColumn: "1 / -1", marginTop: 8 }}>
                <button style={buttonPrimary} type="submit">
                  Рассчитать тарифы
                </button>
              </div>
            </form>
          </div>

          <aside style={{ display: "grid", gap: 16 }}>
            <div style={cardStyle}>
              <h3 style={{ marginTop: 0, marginBottom: 12, fontSize: 18 }}>
                Что уже заложено
              </h3>
              <ul style={{ margin: 0, paddingLeft: 20, lineHeight: 1.8, color: "#475569" }}>
                <li>Frontend + Backend + Nginx</li>
                <li>PostgreSQL и Redis</li>
                <li>S3-compatible storage через MinIO</li>
                <li>Worker контейнер под фоновые задачи</li>
                <li>Health endpoint для backend</li>
              </ul>
            </div>

            <div style={cardStyle}>
              <h3 style={{ marginTop: 0, marginBottom: 12, fontSize: 18 }}>
                Следующий этап
              </h3>
              <p style={{ margin: 0, color: "#475569", lineHeight: 1.7 }}>
                Дальше подключаем auth/profile, затем quote flow и только потом
                полноценный order flow, оплату, документы и трекинг.
              </p>
            </div>
          </aside>
        </section>
      </div>
    </main>
  );
}
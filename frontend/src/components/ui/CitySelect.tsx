"use client";

import { useEffect, useRef, useState } from "react";
import { KZ_CITIES } from "@/lib/cities";

interface CitySelectProps {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
}

export default function CitySelect({ value, onChange, placeholder = "Выберите город" }: CitySelectProps) {
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState("");
  const searchRef = useRef<HTMLInputElement>(null);

  const filtered = KZ_CITIES.filter((c) =>
    c.label.toLowerCase().includes(search.toLowerCase()),
  );
  const regional = filtered.filter((c) => c.type === "regional");
  const district = filtered.filter((c) => c.type === "district");

  useEffect(() => {
    if (open) {
      setTimeout(() => searchRef.current?.focus(), 10);
    } else {
      setSearch("");
    }
  }, [open]);

  function select(val: string) {
    onChange(val);
    setOpen(false);
  }

  return (
    <div style={{ position: "relative" }}>
      <div
        style={{ position: "relative", cursor: "pointer" }}
        onClick={() => setOpen((o) => !o)}
      >
        <input
          readOnly
          value={value}
          placeholder={placeholder}
          style={{
            border: `1px solid ${open ? "#0f172a" : "#e5e7eb"}`,
            borderRadius: 12,
            padding: "12px 40px 12px 14px",
            background: open ? "#ffffff" : "#f8fafc",
            fontSize: 15,
            width: "100%",
            boxSizing: "border-box",
            cursor: "pointer",
            outline: "none",
            color: value ? "#0f172a" : "#94a3b8",
            fontFamily: "inherit",
            transition: "border-color 0.15s, background 0.15s",
          }}
        />
        <span
          style={{
            position: "absolute",
            right: 14,
            top: "50%",
            transform: `translateY(-50%) rotate(${open ? "180deg" : "0deg"})`,
            color: "#94a3b8",
            fontSize: 12,
            pointerEvents: "none",
            transition: "transform 0.2s",
            lineHeight: 1,
          }}
        >
          ▾
        </span>
      </div>

      {open && (
        <>
          <div
            style={{
              position: "fixed",
              inset: 0,
              zIndex: 99,
            }}
            onClick={() => setOpen(false)}
          />
          <div
            style={{
              position: "absolute",
              top: "calc(100% + 4px)",
              left: 0,
              right: 0,
              background: "#ffffff",
              border: "1px solid #e5e7eb",
              borderRadius: 12,
              boxShadow: "0 8px 24px rgba(0,0,0,0.10)",
              zIndex: 100,
              maxHeight: 280,
              overflowY: "auto",
            }}
          >
            <input
              ref={searchRef}
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Поиск города..."
              style={{
                width: "100%",
                padding: "10px 14px",
                fontSize: 14,
                outline: "none",
                border: "none",
                borderBottom: "1px solid #f1f5f9",
                borderRadius: "12px 12px 0 0",
                boxSizing: "border-box",
                fontFamily: "inherit",
                background: "#ffffff",
              }}
            />

            {filtered.length === 0 ? (
              <div
                style={{
                  padding: 20,
                  textAlign: "center",
                  fontSize: 14,
                  color: "#94a3b8",
                }}
              >
                Город не найден
              </div>
            ) : (
              <>
                {regional.length > 0 && (
                  <>
                    <div style={groupLabelStyle}>Областные центры</div>
                    {regional.map((c) => (
                      <CityItem
                        key={c.value}
                        label={c.label}
                        active={c.value === value}
                        onSelect={() => select(c.value)}
                      />
                    ))}
                  </>
                )}
                {district.length > 0 && (
                  <>
                    <div style={groupLabelStyle}>Другие города</div>
                    {district.map((c) => (
                      <CityItem
                        key={c.value}
                        label={c.label}
                        active={c.value === value}
                        onSelect={() => select(c.value)}
                      />
                    ))}
                  </>
                )}
              </>
            )}
          </div>
        </>
      )}
    </div>
  );
}

const groupLabelStyle: React.CSSProperties = {
  padding: "6px 14px 4px",
  fontSize: 11,
  fontWeight: 700,
  color: "#94a3b8",
  textTransform: "uppercase",
  letterSpacing: "0.05em",
};

function CityItem({
  label,
  active,
  onSelect,
}: {
  label: string;
  active: boolean;
  onSelect: () => void;
}) {
  return (
    <div
      onClick={onSelect}
      style={{
        padding: "10px 14px",
        fontSize: 14,
        color: "#0f172a",
        cursor: "pointer",
        background: active ? "#f1f5f9" : "transparent",
        fontWeight: active ? 600 : 400,
      }}
      onMouseEnter={(e) => {
        if (!active) (e.currentTarget as HTMLDivElement).style.background = "#f8fafc";
      }}
      onMouseLeave={(e) => {
        (e.currentTarget as HTMLDivElement).style.background = active ? "#f1f5f9" : "transparent";
      }}
    >
      {label}
    </div>
  );
}

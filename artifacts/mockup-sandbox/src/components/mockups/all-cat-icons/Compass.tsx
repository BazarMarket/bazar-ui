export function Compass() {
  const gridStyle: React.CSSProperties = {
    display: "grid",
    gridTemplateColumns: "repeat(3, 1fr)",
    gap: "10px",
    padding: "16px",
    background: "#f5f5f5",
    maxWidth: "340px",
    margin: "0 auto",
  };
  const itemStyle: React.CSSProperties = {
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    justifyContent: "center",
    gap: "10px",
    padding: "16px 8px",
    background: "#fff",
    border: "1px solid #e4e4e4",
    borderRadius: "16px",
    boxShadow: "0 0 10px rgba(0,0,0,.07)",
    textDecoration: "none",
    color: "#1a1a1a",
    minHeight: "100px",
  };
  const highlightStyle: React.CSSProperties = {
    ...itemStyle,
    border: "2px solid #ff9138",
  };
  const titleStyle: React.CSSProperties = {
    fontFamily: "Poppins, sans-serif",
    fontSize: "11px",
    fontWeight: 500,
    textAlign: "center",
    lineHeight: 1.3,
    margin: 0,
    color: "#1a1a1a",
  };

  const categories = [
    { label: "Property\nfor Sale", icon: <HouseIcon /> },
    { label: "Property\nto Rent", icon: <HouseRentIcon /> },
    { label: "Motors\nfor Sale", icon: <CarIcon /> },
    { label: "Motors\nto Rent", icon: <CarRentIcon /> },
    { label: "Mobile\nPhones", icon: <PhoneIcon /> },
  ];

  return (
    <div style={{ minHeight: "100vh", display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", background: "#f5f5f5", fontFamily: "Poppins, sans-serif" }}>
      <p style={{ fontSize: "12px", color: "#888", marginBottom: "8px" }}>Вариант 2 — Компас / Explore</p>
      <div style={gridStyle}>
        {categories.map((cat, i) => (
          <a key={i} href="#" style={itemStyle}>
            <div style={{ width: 40, height: 40, display: "flex", alignItems: "center", justifyContent: "center" }}>{cat.icon}</div>
            <span style={titleStyle}>{cat.label}</span>
          </a>
        ))}
        <a href="#" style={highlightStyle}>
          <div style={{ width: 44, height: 44, display: "flex", alignItems: "center", justifyContent: "center" }}>
            <svg width="40" height="40" viewBox="0 0 40 40" fill="none">
              <circle cx="20" cy="20" r="17" stroke="#e4e4e4" strokeWidth="2"/>
              <polygon points="20,5 15,20 20,26 25,20" fill="#ff9138"/>
              <polygon points="20,35 15,20 20,14 25,20" fill="#ccc"/>
              <circle cx="20" cy="20" r="2.5" fill="#fff"/>
            </svg>
          </div>
          <span style={titleStyle}>All Categories</span>
        </a>
      </div>
    </div>
  );
}

function HouseIcon() {
  return (
    <svg width="36" height="36" viewBox="0 0 36 36" fill="none">
      <path d="M4 16L18 4L32 16V32H23V22H13V32H4V16Z" fill="#ff9138" opacity=".15" stroke="#ff9138" strokeWidth="2" strokeLinejoin="round"/>
    </svg>
  );
}
function HouseRentIcon() {
  return (
    <svg width="36" height="36" viewBox="0 0 36 36" fill="none">
      <path d="M4 16L18 4L32 16V32H23V22H13V32H4V16Z" fill="#4a90d9" opacity=".15" stroke="#4a90d9" strokeWidth="2" strokeLinejoin="round"/>
    </svg>
  );
}
function CarIcon() {
  return (
    <svg width="36" height="36" viewBox="0 0 36 36" fill="none">
      <rect x="4" y="14" width="28" height="14" rx="4" fill="#ff9138" opacity=".15" stroke="#ff9138" strokeWidth="2"/>
      <path d="M8 14L11 8H25L28 14" stroke="#ff9138" strokeWidth="2"/>
      <circle cx="10" cy="28" r="3" fill="#ff9138"/>
      <circle cx="26" cy="28" r="3" fill="#ff9138"/>
    </svg>
  );
}
function CarRentIcon() {
  return (
    <svg width="36" height="36" viewBox="0 0 36 36" fill="none">
      <rect x="4" y="14" width="28" height="14" rx="4" fill="#4a90d9" opacity=".15" stroke="#4a90d9" strokeWidth="2"/>
      <path d="M8 14L11 8H25L28 14" stroke="#4a90d9" strokeWidth="2"/>
      <circle cx="10" cy="28" r="3" fill="#4a90d9"/>
      <circle cx="26" cy="28" r="3" fill="#4a90d9"/>
    </svg>
  );
}
function PhoneIcon() {
  return (
    <svg width="36" height="36" viewBox="0 0 36 36" fill="none">
      <rect x="10" y="3" width="16" height="30" rx="4" fill="#ff9138" opacity=".15" stroke="#ff9138" strokeWidth="2"/>
      <circle cx="18" cy="29" r="2" fill="#ff9138"/>
    </svg>
  );
}

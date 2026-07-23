import "./globals.css";

export const metadata = {
  title: "Fuel Demand Forecast",
  description: "Daily fuel demand forecasting with safety-stock quantiles for the ROVER replenishment planner",
};

export default function RootLayout({ children }) {
  return (
    <html lang="vi">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link
          href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap"
          rel="stylesheet"
        />
        <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
        <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js" />
        <script src="/chart.umd.min.js" />
      </head>
      <body>{children}</body>
    </html>
  );
}

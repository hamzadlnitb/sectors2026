/** Permanent, on every page (rendered from the root layout) — the compliance
 *  line PANTAU must always show. [K5] */
export default function SiteDisclaimer() {
  return (
    <div className="site-disclaimer">
      <div className="disclaimer">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true">
          <circle cx="12" cy="12" r="9.5" />
          <path d="M12 8v5" strokeLinecap="round" />
          <circle cx="12" cy="16.4" r="0.4" fill="currentColor" stroke="none" />
        </svg>
        PANTAU adalah alat informasi dan analisis, bukan saran investasi.
      </div>
    </div>
  );
}

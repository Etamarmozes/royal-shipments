import { useEffect, useState } from "react";
import { fetchAuthedBlob } from "../utils/fileAccess";

/**
 * <img>-replacement that loads the source via authenticated fetch + Blob URL.
 *
 * Use for any image served by an endpoint that requires the JWT
 * (e.g. /shipments/{id}/product-image). A plain <img src=...> won't
 * include the Authorization header, so the browser would request the
 * URL anonymously and get a 401.
 */
export default function AuthedImage({
  path,
  alt,
  className,
  fallback,
}: {
  /** API path (will be prefixed with apiBase). e.g. "/shipments/12/product-image" */
  path: string;
  alt?: string;
  className?: string;
  fallback?: React.ReactNode;
}) {
  const [src, setSrc] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    let blobUrl: string | null = null;

    setError(null);
    setSrc(null);

    fetchAuthedBlob(path)
      .then(({ blob }) => {
        if (cancelled) return;
        blobUrl = URL.createObjectURL(blob);
        setSrc(blobUrl);
      })
      .catch((err: Error) => {
        if (cancelled) return;
        setError(err.message);
      });

    return () => {
      cancelled = true;
      if (blobUrl) URL.revokeObjectURL(blobUrl);
    };
  }, [path]);

  if (error) {
    return <>{fallback ?? <span className="text-xs text-slate-400">תמונה לא זמינה</span>}</>;
  }
  if (!src) {
    return <>{fallback ?? <span className="text-xs text-slate-400">טוען...</span>}</>;
  }
  return <img src={src} alt={alt || ""} className={className} />;
}

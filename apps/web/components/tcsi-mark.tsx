import Image from "next/image";

export function TCSIMark({ compact = false }: { compact?: boolean }) {
  return (
    <Image
      className={`landing-mark${compact ? " landing-mark--compact" : ""}`}
      src="/logos/tcsi-logo.png"
      alt=""
      aria-hidden="true"
      width={512}
      height={512}
      unoptimized
    />
  );
}
